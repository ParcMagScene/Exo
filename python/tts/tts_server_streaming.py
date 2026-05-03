"""
tts_server_streaming.py — serveur WebSocket TTS EXO **stateless, sans cache**.

Différences vs tts_server.py historique:
  - AUCUN cache audio (PhraseCache supprimé) → impossible que 2 textes
    différents partagent le même buffer audio.
  - AUCUN état global mutable conservant la dernière synthèse.
  - Streaming "true real-time": chaque chunk PCM produit par l'engine est
    envoyé immédiatement sur le WebSocket (pas d'accumulation).
  - Métriques first_chunk / total / RTF loggées par requête.

Protocole WS:
  → JSON: {"type": "synthesize", "text": "...",
           "voice": "exo_default", "lang": "fr", "rate": 1.0}
          {"type": "cancel"}
          {"type": "ping"}
  ← JSON: {"type": "ready", "sample_rate": 24000}
  ← JSON: {"type": "start", "text": "..."}
  ← Binary: PCM16 chunks (24 kHz mono LE)
  ← JSON: {"type": "end", "duration": float, "first_chunk_ms": int,
           "total_ms": int, "chunks": int, "rtf": float}
  ← JSON: {"type": "error", "message": "..."}
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
import logging
import os
import sys
import time
from pathlib import Path

import websockets

# Permet d'exécuter le module directement (PYTHONPATH=python).
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from audio_streamer import OUTPUT_SAMPLE_RATE, DEFAULT_WS_CHUNK_BYTES, pcm_duration_seconds
from cosyvoice_streaming_engine import (
    CosyVoiceStreamingEngine,
    get_providers,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [TTS-STREAM] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("exo.tts.server")


# ---------------------------------------------------------------------------
# Session WebSocket — stateless par requête
# ---------------------------------------------------------------------------

class Session:
    """Une connexion client. Pas d'état audio entre 2 requêtes."""

    # Un unique exécuteur partagé pour appeler l'engine (sync) sans bloquer
    # la boucle asyncio. Plusieurs sessions peuvent s'enchaîner; l'engine
    # sérialise lui-même via son propre lock.
    _executor: "concurrent.futures.ThreadPoolExecutor | None" = None

    def __init__(self, engine: CosyVoiceStreamingEngine) -> None:
        self.engine = engine
        self._cancel = False
        if Session._executor is None:
            Session._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=2, thread_name_prefix="exo-tts-stream"
            )

    async def handle(self, ws) -> None:
        await ws.send(json.dumps({
            "type": "ready",
            "phase": "ready_online",
            "sample_rate": OUTPUT_SAMPLE_RATE,
            "backend": "cosyvoice2-streaming",
        }))
        try:
            async for raw in ws:
                if not isinstance(raw, str):
                    continue
                try:
                    msg = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                t = msg.get("type")
                if t == "synthesize":
                    self._cancel = False
                    await self._do_synthesize(ws, msg)
                elif t == "cancel":
                    self._cancel = True
                elif t == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                elif t == "list_voices":
                    voices = self.engine.list_voices()
                    await ws.send(json.dumps({
                        "type": "voices",
                        "available": voices,
                        "current": self.engine.speaker_id,
                    }))
                elif t == "set_voice":
                    new_voice = (msg.get("voice") or "").strip()
                    if new_voice and new_voice in self.engine.list_voices():
                        self.engine.speaker_id = new_voice
                        await ws.send(json.dumps({
                            "type": "voice_set",
                            "voice": new_voice,
                        }))
                    else:
                        await ws.send(json.dumps({
                            "type": "error",
                            "message": f"unknown voice: {new_voice!r}",
                        }))
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception:
            logger.exception("Session erreur")

    async def _do_synthesize(self, ws, msg: dict) -> None:
        text = (msg.get("text") or "").strip()
        if not text:
            await ws.send(json.dumps({"type": "error", "message": "Empty text"}))
            return

        rate = float(msg.get("rate", 1.0))
        voice = (msg.get("voice") or "").strip() or None
        await ws.send(json.dumps({"type": "start", "text": text}))

        loop = asyncio.get_event_loop()
        # Une queue locale à la requête → impossible qu'un autre appel
        # s'invite dans le flux audio courant.
        queue: asyncio.Queue = asyncio.Queue(maxsize=16)
        SENTINEL = object()

        def _producer() -> None:
            try:
                for chunk in self.engine.generate_stream(text, speed=rate, voice=voice):
                    if self._cancel:
                        break
                    asyncio.run_coroutine_threadsafe(
                        queue.put(chunk), loop
                    ).result()
            except Exception as exc:
                logger.exception("Engine erreur: %s", exc)
                asyncio.run_coroutine_threadsafe(
                    queue.put(("error", str(exc))), loop
                ).result()
            finally:
                asyncio.run_coroutine_threadsafe(
                    queue.put(SENTINEL), loop
                ).result()

        t0 = time.monotonic()
        fut = loop.run_in_executor(Session._executor, _producer)

        first_chunk_ms = None
        total_bytes = 0
        chunks_sent = 0
        err_msg: "str | None" = None

        while True:
            item = await queue.get()
            if item is SENTINEL:
                break
            if isinstance(item, tuple) and item[0] == "error":
                err_msg = item[1]
                break
            if self._cancel:
                continue
            await ws.send(item)
            total_bytes += len(item)
            chunks_sent += 1
            if first_chunk_ms is None:
                first_chunk_ms = (time.monotonic() - t0) * 1000.0
                logger.info("[ws] first_chunk_ms=%.0f", first_chunk_ms)
            # Yield au loop pour ne pas saturer le canal.
            if chunks_sent % 8 == 0:
                await asyncio.sleep(0)

        await fut

        if err_msg:
            await ws.send(json.dumps({"type": "error", "message": err_msg}))
            return

        total_ms = (time.monotonic() - t0) * 1000.0
        audio_s = pcm_duration_seconds(total_bytes)
        rtf = (total_ms / 1000.0) / audio_s if audio_s > 0 else float("inf")
        logger.info(
            "[ws] DONE first=%.0fms total=%.0fms chunks=%d audio=%.2fs RTF=%.2f",
            first_chunk_ms or -1, total_ms, chunks_sent, audio_s, rtf,
        )
        await ws.send(json.dumps({
            "type": "end",
            "duration": round(audio_s, 3),
            "first_chunk_ms": int(first_chunk_ms or 0),
            "total_ms": int(total_ms),
            "chunks": chunks_sent,
            "rtf": round(rtf, 3),
        }))


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _resolve_model_dir() -> str:
    env = os.environ.get("EXO_COSYVOICE_MODELS")
    if env and os.path.isdir(env):
        return env
    for cand in (r"D:\EXO\models\cosyvoice_fr", r"D:\EXO\models\cosyvoice"):
        if os.path.isdir(cand):
            return cand
    raise FileNotFoundError(
        "Aucun dossier modèle CosyVoice trouvé. "
        "Définir EXO_COSYVOICE_MODELS ou installer dans D:\\EXO\\models\\cosyvoice_fr."
    )


def _resolve_prompt(model_dir: str) -> "tuple[str | None, str | None]":
    """Resout le prompt zero-shot a utiliser au demarrage.

    Priorite (la 1ere source qui marche gagne) :
      1. EXO_TTS_DEFAULT_VOICE = id (ex: fr_male_01) ou legacy_id (ex: fr_henri)
         resolu via voices.json du modele.
      2. Premiere voix listee dans voices.json (typiquement une voix FR).
      3. prompt.wav + prompt.txt du dossier modele (legacy / fallback).

    Sans (1) ou (2), CosyVoice2 utilise inference_cross_lingual avec le prompt
    par defaut (souvent une voix anglaise) -> accent anglais sur du francais.
    On force donc un prompt FR pour rester en inference_zero_shot.
    """
    voices_json = os.path.join(model_dir, "voices.json")
    requested = (os.environ.get("EXO_TTS_DEFAULT_VOICE") or "").strip()

    if os.path.isfile(voices_json):
        try:
            voices = json.loads(Path(voices_json).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.exception("voices.json illisible: %s", voices_json)
            voices = []

        def _match(v: dict) -> bool:
            if not requested:
                return False
            return requested in {
                str(v.get("id", "")),
                str(v.get("legacy_id", "")),
                str(v.get("name", "")),
            }

        chosen = None
        if requested:
            chosen = next((v for v in voices if _match(v)), None)
            if not chosen:
                logger.warning(
                    "EXO_TTS_DEFAULT_VOICE=%r introuvable dans voices.json", requested
                )
        if not chosen and voices:
            chosen = voices[0]

        if chosen:
            voice_file = chosen.get("file") or ""
            wav_path = os.path.join(model_dir, "voices", voice_file)
            text = (chosen.get("prompt_text") or "").strip() or None
            if os.path.isfile(wav_path) and text:
                logger.info(
                    "Prompt FR voices.json: id=%s file=%s",
                    chosen.get("id"), voice_file,
                )
                return wav_path, text
            logger.warning(
                "voices.json[%s]: wav ou prompt_text manquant (wav=%s)",
                chosen.get("id"), wav_path,
            )

    # Fallback historique: prompt.wav + prompt.txt a la racine du modele.
    p_wav = os.path.join(model_dir, "prompt.wav")
    p_txt = os.path.join(model_dir, "prompt.txt")
    wav = p_wav if os.path.isfile(p_wav) else None
    text = None
    if os.path.isfile(p_txt):
        try:
            text = Path(p_txt).read_text(encoding="utf-8").strip() or None
        except OSError:
            text = None
    if wav and not text:
        logger.warning(
            "Prompt sans texte associe (prompt.txt manquant) - CosyVoice basculera "
            "en inference_cross_lingual et la voix risque d'avoir un accent etranger."
        )
    return wav, text


async def _serve(host: str, port: int, engine: CosyVoiceStreamingEngine) -> None:
    # Pré-calcule la liste de providers (pour /health). Pas de side-effect.
    try:
        _providers_active = [p[0] for p in get_providers(engine.model_dir)]
    except Exception:
        _providers_active = []

    # Body de health pré-encodé (perf : <1ms pénalité JSON par appel inutile).
    health_body = json.dumps({
        "status": "ok",
        "engine": "cosyvoice2",
        "providers": _providers_active,
        "sample_rate": OUTPUT_SAMPLE_RATE,
        "port": port,
    }).encode("utf-8")

    # API moderne websockets (v13+): process_request(connection, request) ->
    # Response | None. Si None : upgrade WS normal. Sinon : on répond HTTP.
    from websockets.http11 import Response  # local import (évite top-level coupling)
    from websockets.datastructures import Headers

    def process_request(connection, request):
        """Multiplexe HTTP /health sur le même port que le WebSocket."""
        try:
            raw_path = request.path  # ex: "/health" ou "/health?x=1"
        except AttributeError:
            return None
        clean = raw_path.split("?", 1)[0]
        if clean == "/health":
            headers = Headers([
                ("Content-Type", "application/json"),
                ("Cache-Control", "no-store"),
                ("Content-Length", str(len(health_body))),
            ])
            return Response(200, "OK", headers, health_body)
        return None  # → upgrade WebSocket normal

    async def handler(ws):
        sess = Session(engine)
        await sess.handle(ws)

    # Dual-stack IPv4 + IPv6 si host == 0.0.0.0 (sinon Windows resout
    # `localhost` en ::1 et la connexion echoue cote client Qt).
    bind_host = host
    if host in ("0.0.0.0", "*", ""):
        bind_host = ["0.0.0.0", "::"]
    logger.info("WebSocket TTS streaming sur ws://%s:%d (health: http://127.0.0.1:%d/health)",
                host, port, port)
    async with websockets.serve(
        handler,
        bind_host,
        port,
        max_size=None,
        process_request=process_request,
    ):
        await asyncio.Future()  # run forever


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=8767)
    ap.add_argument("--speaker", default="exo_default")
    ap.add_argument(
        "--ws-chunk-bytes", type=int, default=DEFAULT_WS_CHUNK_BYTES,
        help="Taille cible d'un chunk WebSocket (octets PCM16).",
    )
    args = ap.parse_args()

    model_dir = _resolve_model_dir()
    prompt_wav, prompt_text = _resolve_prompt(model_dir)
    logger.info("Modèle: %s", model_dir)
    logger.info("Prompt: wav=%s text=%r", prompt_wav, (prompt_text or "")[:40])

    engine = CosyVoiceStreamingEngine(
        model_dir=model_dir,
        speaker_id=args.speaker,
        prompt_wav=prompt_wav,
        prompt_text=prompt_text,
        ws_chunk_bytes=args.ws_chunk_bytes,
    )
    engine.load()  # blocking, une seule fois.

    # Warmup synthèse — première inférence CosyVoice2 = ~2-3 s (JIT CUDA,
    # allocations ONNX, init providers). On la paye au boot plutôt que sur la
    # toute première phrase utilisateur. Le résultat est jeté.
    try:
        t_warm = time.monotonic()
        n = 0
        for chunk in engine.generate_stream("Bonjour.", speed=1.0):
            n += len(chunk) if isinstance(chunk, (bytes, bytearray)) else 0
        logger.info("[warmup] première synthèse drainée en %.0f ms (%d octets PCM)",
                    (time.monotonic() - t_warm) * 1000.0, n)
    except Exception as exc:  # pragma: no cover — warmup est best-effort
        logger.warning("[warmup] échec (non fatal): %s", exc)

    asyncio.run(_serve(args.host, args.port, engine))


if __name__ == "__main__":
    main()
