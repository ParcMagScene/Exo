"""Orpheus 3B FR (GGUF) -- serveur WebSocket compatible EXO TTS streaming.

Drop-in replacement pour python/tts/tts_server_streaming.py (CosyVoice2).
Protocole WebSocket identique :

    -> JSON  {"type":"synthesize","text":"...","voice":"pierre","rate":1.0}
             {"type":"cancel"} | {"type":"ping"} | {"type":"list_voices"}
             {"type":"set_voice","voice":"amelie"}
    <- JSON  {"type":"ready","sample_rate":24000,"backend":"orpheus-gguf"}
    <- JSON  {"type":"start","text":"..."}
    <- bytes PCM16 24 kHz mono LE  (chunks)
    <- JSON  {"type":"end","duration":..,"first_chunk_ms":..,"total_ms":..,"chunks":..,"rtf":..}
    <- JSON  {"type":"voices"|"voice_set"|"pong"|"error",...}

HTTP /health multiplexe sur le meme port.

Variables d'environnement :
    ORPHEUS_GGUF_PATH       chemin du .gguf
    ORPHEUS_N_CTX           taille de contexte (defaut: 4096)
    ORPHEUS_N_GPU_LAYERS    nb couches GPU (-1 = toutes)
    ORPHEUS_DEFAULT_VOICE   voix par defaut (pierre)
    ORPHEUS_VOICES          liste csv (pierre,amelie,marie)
    ORPHEUS_WS_HOST         host bind (defaut: 0.0.0.0)
    ORPHEUS_WS_PORT         port (defaut: 8767)
    ORPHEUS_WS_CHUNK_BYTES  taille chunk WS PCM16 (defaut: 480)
"""
from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
import logging
import os
import sys
import threading
import time
from typing import Iterator, List, Optional

import numpy as np
import torch
import websockets

# Reutilise toute la machinerie GGUF + SNAC du serveur HTTP.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from server_gguf import (  # type: ignore
    CUSTOM_TOKEN_PREFIX,
    N_CODEBOOKS,
    SAMPLE_RATE,
    STATE,
    STOP_TOKEN_STRINGS,
    _decode_window,
    _turn_token_into_id,
    load_models,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Orpheus-WS] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("orpheus.ws")


OUTPUT_BYTES_PER_SAMPLE = 2  # PCM16 mono


# Alias des voix EXO/CosyVoice -> voix Orpheus reelles.
# Toute voix inconnue retombe sur STATE.default_voice (cf _resolve_voice).
VOICE_ALIASES = {
    "exo_default":   "pierre",
    "default":       "pierre",
    "fr_male_01":    "pierre",
    "fr_male":       "pierre",
    "male":          "pierre",
    "fr_female_01":  "amelie",
    "fr_female_02":  "marie",
    "fr_female":     "amelie",
    "female":        "amelie",
}


def _resolve_voice(voice: Optional[str]) -> str:
    """Normalise et valide une voix demandee.

    - vide / None -> default_voice
    - exact match dans STATE.voices -> renvoyee telle quelle
    - alias connu -> voix Orpheus correspondante
    - sinon -> default_voice (jamais la voix brute, qui crasherait CUDA
      si elle produit des tokens degeneres)
    """
    raw = (voice or "").strip().lower()
    if not raw:
        return STATE.default_voice
    valid = {v.lower() for v in STATE.voices}
    if raw in valid:
        return raw
    aliased = VOICE_ALIASES.get(raw)
    if aliased and aliased.lower() in valid:
        log.info("voice alias '%s' -> '%s'", raw, aliased)
        return aliased
    log.warning("voice inconnue '%s' -> fallback '%s'", raw, STATE.default_voice)
    return STATE.default_voice


# ---------------------------------------------------------------------------
# Conversion audio
# ---------------------------------------------------------------------------
def _float_to_pcm16(wave: np.ndarray) -> bytes:
    if wave.size == 0:
        return b""
    if wave.dtype not in (np.float32, np.float64):
        wave = wave.astype(np.float32)
    # IMPORTANT : NE PAS normaliser au peak du segment ! En streaming on
    # appelle cette fonction par chunk de ~2048 samples : normaliser chaque
    # segment a son propre peak introduit des sauts d'amplitude entre
    # segments -> craquements/pops a chaque jonction de frame SNAC.
    # On se contente d'un clip dur (les samples SNAC sont deja dans [-1,1]).
    pcm = np.clip(wave * 32767.0, -32768.0, 32767.0).astype(np.int16)
    return pcm.tobytes()


def _pcm_duration_seconds(pcm_bytes: int) -> float:
    samples = pcm_bytes // OUTPUT_BYTES_PER_SAMPLE
    return samples / float(SAMPLE_RATE)


# ---------------------------------------------------------------------------
# Generateur streaming : llama.cpp -> SNAC fenetre glissante -> PCM16 chunks
# ---------------------------------------------------------------------------
def _stream_pcm(
    text: str,
    voice: str,
    speed: float,
    chunk_bytes: int,
    cancel_flag: "threading.Event",
) -> Iterator[bytes]:
    """Genere du PCM16 24kHz mono au fil de la generation Orpheus.

    Strategie de decodage SNAC alignee sur Lex-au/Orpheus-FastAPI :
      - on attend 28 ids (4 frames) avant la 1re emission
      - puis fenetres glissantes de 28 ids (pas 7) -> on garde la
        seconde moitie du decode SNAC = 1 frame audio nouveau
      - les segments sont contigus : pas de chevauchement ni de gap
        => evite craquements/clics aux jonctions.

    On accumule le PCM dans un buffer et on yield des chunks de `chunk_bytes`
    octets pour minimiser la latence cote client.
    """
    voice = _resolve_voice(voice)
    text_norm = text.strip().replace("\n", " ")
    prompt = f"<|audio|>{voice}: {text_norm}<|eot_id|>"
    max_tokens = min(2600, max(400, int(len(text_norm) * 28)))

    log.info("stream voice=%s len=%d max_tokens=%d", voice, len(text_norm), max_tokens)

    out = STATE.llm.create_completion(
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=0.6,
        top_p=0.9,
        repeat_penalty=1.1,
        stream=True,
        stop=STOP_TOKEN_STRINGS,
    )

    audio_ids: List[int] = []
    index = 0
    last_decoded_count = 0
    first_done = False
    pcm_buf = bytearray()
    target = chunk_bytes if chunk_bytes % 2 == 0 else chunk_bytes - 1
    if target < 240:
        target = 240

    speed_factor = float(speed) if abs(speed - 1.0) > 1e-3 else None

    def _emit(seg_np: np.ndarray) -> Iterator[bytes]:
        nonlocal pcm_buf
        if seg_np.size == 0:
            return
        if speed_factor is not None:
            n_out = max(1, int(len(seg_np) / speed_factor))
            idx = np.linspace(0, len(seg_np) - 1, n_out).astype(np.int64)
            seg_np = seg_np[idx]
        pcm_buf.extend(_float_to_pcm16(seg_np))
        while len(pcm_buf) >= target:
            yield bytes(pcm_buf[:target])
            del pcm_buf[:target]

    for chunk in out:
        if cancel_flag.is_set():
            log.info("stream annule (cancel)")
            break
        choices = chunk.get("choices") or []
        if not choices:
            continue
        token_text = choices[0].get("text", "")
        if not token_text:
            continue
        for piece in token_text.split(">"):
            if not piece:
                continue
            piece_full = piece + ">"
            tid = _turn_token_into_id(piece_full, index)
            if tid is None or tid <= 0:
                continue
            audio_ids.append(tid)
            index += 1

            count = len(audio_ids)
            # Reproduit fidelement _convert_frames_to_audio (server_gguf.py) :
            #   - amorcage : count==7 -> decode [0:7], garde [len/4:len/2]
            #   - regime : count>=28 et (count-7)%7==0 -> fenetre glissante
            #     de 28 ids (4 frames), pas de 7 ids (1 frame), on garde
            #     SAMPLES [2048:4096] (= deuxieme quart du decode 4-frames).
            # En batch ces slices se concatenent en un PCM continu propre :
            # on fait pareil ici, sans overlap ni gap -> pas de saccades.
            if not first_done and count == 7:
                ah = _decode_window(audio_ids[:7])
                first_done = True
                last_decoded_count = 7
                if ah is not None:
                    slice_len = ah.shape[-1]
                    seg = ah[:, :, slice_len // 4 : slice_len // 2]
                    seg_np = seg.squeeze().detach().cpu().float().numpy()
                    yield from _emit(seg_np)
            elif first_done and count >= 28 and ((count - 7) % 7) == 0 and count > last_decoded_count:
                window = audio_ids[count - 28 : count]
                ah = _decode_window(window)
                last_decoded_count = count
                if ah is None:
                    continue
                # Slice fixe samples [2048:4096] comme la reference Lex-au.
                seg = ah[:, :, 2048:4096]
                seg_np = seg.squeeze().detach().cpu().float().numpy()
                yield from _emit(seg_np)

    # Drain : tout ce qui reste dans pcm_buf
    if pcm_buf and not cancel_flag.is_set():
        yield bytes(pcm_buf)
        pcm_buf.clear()


# ---------------------------------------------------------------------------
# Session WebSocket
# ---------------------------------------------------------------------------
class Session:
    _executor: "concurrent.futures.ThreadPoolExecutor | None" = None

    def __init__(self, chunk_bytes: int) -> None:
        self.chunk_bytes = chunk_bytes
        self._cancel = threading.Event()
        if Session._executor is None:
            Session._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=2, thread_name_prefix="orpheus-ws"
            )

    async def handle(self, ws) -> None:
        await ws.send(json.dumps({
            "type": "ready",
            "phase": "ready_online",
            "sample_rate": SAMPLE_RATE,
            "backend": "orpheus-gguf",
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
                    self._cancel.clear()
                    await self._do_synthesize(ws, msg)
                elif t == "cancel":
                    self._cancel.set()
                elif t == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                elif t == "list_voices":
                    await ws.send(json.dumps({
                        "type": "voices",
                        "available": list(STATE.voices),
                        "current": STATE.default_voice,
                    }))
                elif t == "set_voice":
                    new_voice = (msg.get("voice") or "").strip().lower()
                    if new_voice and new_voice in STATE.voices:
                        STATE.default_voice = new_voice
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
            log.exception("Session erreur")

    async def _do_synthesize(self, ws, msg: dict) -> None:
        text = (msg.get("text") or "").strip()
        if not text:
            await ws.send(json.dumps({"type": "error", "message": "Empty text"}))
            return

        rate = float(msg.get("rate", 1.0))
        voice = (msg.get("voice") or "").strip().lower() or STATE.default_voice
        await ws.send(json.dumps({"type": "start", "text": text}))

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        SENTINEL = object()

        def _producer() -> None:
            try:
                for pcm_chunk in _stream_pcm(
                    text=text,
                    voice=voice,
                    speed=rate,
                    chunk_bytes=self.chunk_bytes,
                    cancel_flag=self._cancel,
                ):
                    if self._cancel.is_set():
                        break
                    asyncio.run_coroutine_threadsafe(
                        queue.put(pcm_chunk), loop
                    ).result()
            except Exception as exc:
                log.exception("Engine erreur: %s", exc)
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
            if self._cancel.is_set():
                continue
            await ws.send(item)
            total_bytes += len(item)
            chunks_sent += 1
            if first_chunk_ms is None:
                first_chunk_ms = (time.monotonic() - t0) * 1000.0
                log.info("[ws] first_chunk_ms=%.0f", first_chunk_ms)
            if chunks_sent % 8 == 0:
                await asyncio.sleep(0)

        await fut

        if err_msg:
            await ws.send(json.dumps({"type": "error", "message": err_msg}))
            return

        total_ms = (time.monotonic() - t0) * 1000.0
        audio_s = _pcm_duration_seconds(total_bytes)
        rtf = (total_ms / 1000.0) / audio_s if audio_s > 0 else float("inf")
        log.info(
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
async def _serve(host: str, port: int, chunk_bytes: int) -> None:
    health_body = json.dumps({
        "status": "ok",
        "engine": "orpheus-gguf",
        "providers": ["cuda"] if torch.cuda.is_available() else ["cpu"],
        "sample_rate": SAMPLE_RATE,
        "port": port,
        "voices": list(STATE.voices),
        "default_voice": STATE.default_voice,
    }).encode("utf-8")

    from websockets.http11 import Response
    from websockets.datastructures import Headers

    def process_request(connection, request):
        try:
            raw_path = request.path
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
        return None

    async def handler(ws):
        sess = Session(chunk_bytes=chunk_bytes)
        await sess.handle(ws)

    bind_host = host
    if host in ("0.0.0.0", "*", ""):
        bind_host = ["0.0.0.0", "::"]
    log.info(
        "WebSocket Orpheus sur ws://%s:%d (health: http://127.0.0.1:%d/health, chunk=%dB)",
        host, port, port, chunk_bytes,
    )
    async with websockets.serve(
        handler,
        bind_host,
        port,
        max_size=None,
        process_request=process_request,
    ):
        await asyncio.Future()


def _warmup() -> None:
    """Premiere generation jetee : evite la latence sur la 1re requete client."""
    try:
        t0 = time.monotonic()
        cancel = threading.Event()
        n = 0
        for chunk in _stream_pcm("Bonjour.", STATE.default_voice, 1.0, 480, cancel):
            n += len(chunk)
        log.info("[warmup] %d octets PCM en %.0f ms", n, (time.monotonic() - t0) * 1000.0)
    except Exception as exc:
        log.warning("[warmup] echec (non fatal): %s", exc)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("ORPHEUS_WS_HOST", "0.0.0.0"))
    ap.add_argument("--port", type=int,
                    default=int(os.environ.get("ORPHEUS_WS_PORT", "8767")))
    ap.add_argument("--ws-chunk-bytes", type=int,
                    default=int(os.environ.get("ORPHEUS_WS_CHUNK_BYTES", "480")))
    ap.add_argument("--no-warmup", action="store_true")
    args = ap.parse_args()

    load_models()
    if not args.no_warmup:
        _warmup()
    asyncio.run(_serve(args.host, args.port, args.ws_chunk_bytes))


if __name__ == "__main__":
    main()
