from __future__ import annotations
def profile_block(label, threshold_ms=10):
    import time
    from functools import wraps
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                t0 = time.monotonic()
                result = await func(*args, **kwargs)
                dt = (time.monotonic() - t0) * 1000
                if dt > threshold_ms:
                    log.warning(f"[PERF] {label}: {dt:.1f} ms")
                return result
            return wrapper
        else:
            @wraps(func)
            def wrapper(*args, **kwargs):
                t0 = time.monotonic()
                result = func(*args, **kwargs)
                dt = (time.monotonic() - t0) * 1000
                if dt > threshold_ms:
                    log.warning(f"[PERF] {label}: {dt:.1f} ms")
                return result
            return wrapper
    return decorator
"""Orpheus 3B FR (GGUF) -- serveur WebSocket TTS EXO (streaming PCM16 24 kHz).

Protocole WebSocket :

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
import argparse
import asyncio
import concurrent.futures
try:
    import ujson as json  # v6.0 perf : 3-5x plus rapide que stdlib (audit perf)
except ImportError:
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
CHANNELS = 1                 # mono obligatoire (Orpheus WS protocol)

# Tailles de chunk WebSocket autorisees (samples mono @ 24 kHz)
#   480 samples = 20 ms = 960 octets PCM16
#   960 samples = 40 ms = 1920 octets PCM16
# 40 ms est le sweet-spot : grand assez pour amortir la jitter du pump C++,
# petit assez pour rester sub-perceptible en latence.
ALLOWED_CHUNK_SAMPLES = (480, 960)
DEFAULT_CHUNK_SAMPLES = 960
DEFAULT_CHUNK_BYTES   = DEFAULT_CHUNK_SAMPLES * OUTPUT_BYTES_PER_SAMPLE  # 1920

# v6.0 perf audit : silence pad pre-alloue (1 chunk max) pour eviter une
# allocation `b"\x00" * pad` a chaque drain final de _stream_pcm.
_SILENCE_PAD = bytes(max(ALLOWED_CHUNK_SAMPLES) * OUTPUT_BYTES_PER_SAMPLE)

# ---------------------------------------------------------------------------
# Phase de readiness globale (v5.1 supervisor)
#   ready_loading : port ouvert, modèle pas encore chargé
#   ready_warmup  : modèle chargé, warmup en cours
#   ready_online  : pleinement opérationnel
# ---------------------------------------------------------------------------
READY_PHASE: str = "ready_loading"
LOAD_DONE: "asyncio.Event | None" = None       # set quand passe à ready_online
CONNECTED_CLIENTS: "set" = set()                # ws clients à notifier au switch


def _normalize_chunk_bytes(raw: int) -> int:
    """Force la taille de chunk a 960 ou 1920 octets (480 ou 960 samples).

    Toute autre valeur est snappee sur la plus proche autorisee, avec un log.
    """
    samples = max(1, int(raw)) // OUTPUT_BYTES_PER_SAMPLE
    if samples in ALLOWED_CHUNK_SAMPLES:
        return samples * OUTPUT_BYTES_PER_SAMPLE
    snapped = min(ALLOWED_CHUNK_SAMPLES, key=lambda s: abs(s - samples))
    log.warning(
        "chunk_bytes=%d (=%d samples) hors specs ; snap -> %d samples (%d B)",
        raw, samples, snapped, snapped * OUTPUT_BYTES_PER_SAMPLE,
    )
    return snapped * OUTPUT_BYTES_PER_SAMPLE


# Alias des voix EXO -> voix Orpheus reelles.
# Toute voix inconnue retombe sur STATE.default_voice (cf _resolve_voice).
# NOTE : EXO expose UNE SEULE voix logique "orpheus" cote client (anti-XTTS
# patch). En interne, le modele GGUF requiert un token de voix reel
# (pierre/amelie/marie) ; "orpheus" alias -> STATE.default_voice (pierre).
VOICE_ALIASES = {
    "orpheus":       "pierre",
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


# Patch anti-XTTS : les anciens IDs de voix XTTS exposes par la GUI sont
# remappes vers la voix logique unique "orpheus" (qui retombe sur le token
# GGUF reel via VOICE_ALIASES). Le modele continue d'utiliser pierre/amelie/
# marie en interne mais aucun client ne doit plus pouvoir les selectionner.
LEGACY_XTTS_VOICES = {"pierre", "amelie", "marie"}


def _resolve_voice(voice: Optional[str]) -> str:
    """Normalise et valide une voix demandee.

    - vide / None -> default_voice
    - voix XTTS heritee (pierre/amelie/marie) -> remappee vers 'orpheus'
    - exact match dans STATE.voices -> renvoyee telle quelle
    - alias connu -> voix Orpheus correspondante
    - sinon -> default_voice (jamais la voix brute, qui crasherait CUDA
      si elle produit des tokens degeneres)
    """
    raw = (voice or "").strip().lower()
    if not raw:
        return STATE.default_voice
    if raw in LEGACY_XTTS_VOICES:
        log.info("voice legacy XTTS '%s' remappee -> 'orpheus'", raw)
        raw = "orpheus"
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
    """Convertit un buffer float -> PCM16 mono little-endian.

    Garanties :
      - dtype d'entree force en float32
      - mono : si stereo (shape (N,2) ou (2,N)), on rabat sur le canal 0
      - clip dur dans [-1,1] *avant* multiplication (evite tout overflow)
      - pas de normalisation par segment (cause de craquements en streaming)
      - sortie en int16 little-endian ("<i2") explicite, contigue
    """
    if wave is None or wave.size == 0:
        return b""
    arr = np.asarray(wave)
    # Mono
    if arr.ndim > 1:
        if arr.shape[0] in (1, 2):
            arr = arr[0]
        elif arr.shape[-1] in (1, 2):
            arr = arr[..., 0]
        else:
            arr = arr.reshape(-1)
    # Float32 contigu (writeable)
    if arr.dtype != np.float32 or not arr.flags.writeable:
        arr = arr.astype(np.float32, copy=True)
    # Clip dans [-1,1] PUIS scale -> evite tout overflow int16
    np.clip(arr, -1.0, 1.0, out=arr)
    pcm = (arr * 32767.0).astype("<i2", copy=False)
    return np.ascontiguousarray(pcm).tobytes()


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
    target = _normalize_chunk_bytes(chunk_bytes)

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

    # Drain final : on PAD avec du silence pour emettre un dernier chunk
    # exactement aligne sur `target` octets. Cela garantit cote client une
    # taille constante sur tous les chunks (evite la mini-frame finale qui
    # decalait le pump du ring buffer).
    # AVANT le drain : decode des audio_ids restants apres la derniere fenetre
    # complete (cause des mots coupes en fin : jusqu'a 6 ids ~75 ms perdus).
    if first_done and len(audio_ids) > last_decoded_count and len(audio_ids) >= 28 and not cancel_flag.is_set():
        extra = len(audio_ids) - last_decoded_count  # 1..6 ids non decodes
        window = audio_ids[len(audio_ids) - 28 : len(audio_ids)]
        ah = _decode_window(window)
        if ah is not None:
            # La fenetre precedente a emis [2048:4096]. Cette fenetre est
            # decalee de `extra` ids vers la droite : ses samples [2048:4096]
            # se chevauchent partiellement avec la precedente. On emet
            # uniquement la portion *nouvelle* a la fin.
            samples_per_id = (4096 - 2048) // 7  # ~293 samples par id
            tail_samples = samples_per_id * extra
            seg = ah[:, :, 4096 - tail_samples : 4096]
            seg_np = seg.squeeze().detach().cpu().float().numpy()
            yield from _emit(seg_np)

    if pcm_buf and not cancel_flag.is_set():
        remaining = len(pcm_buf)
        # Force alignement 2 octets (sample boundary)
        if remaining % OUTPUT_BYTES_PER_SAMPLE != 0:
            log.warning("drain final non aligne (%d B), troncature 1 octet", remaining)
            remaining -= 1
            del pcm_buf[remaining:]
        pad = target - (remaining % target)
        if pad and pad != target:
            # v6.0 perf audit : silence pre-alloue (cf. _SILENCE_PAD) pour eviter
            # une allocation `b"\x00" * pad` a chaque drain.
            pcm_buf.extend(_SILENCE_PAD[:pad])
        # Yield en chunks plein-target
        for off in range(0, len(pcm_buf), target):
            yield bytes(pcm_buf[off:off + target])
        pcm_buf.clear()


# ---------------------------------------------------------------------------
# Session WebSocket
# ---------------------------------------------------------------------------
class Session:
    _executor: "concurrent.futures.ThreadPoolExecutor | None" = None

    def __init__(self, chunk_bytes: int) -> None:
        self.chunk_bytes = _normalize_chunk_bytes(chunk_bytes)
        self._cancel = threading.Event()
        if Session._executor is None:
            Session._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=2, thread_name_prefix="orpheus-ws"
            )

    @profile_block("Orpheus handle (ws mainloop)", threshold_ms=10)
    async def handle(self, ws) -> None:
        # v5.1 : envoie la phase courante (ready_loading / ready_warmup / ready_online)
        await ws.send(json.dumps({
            "type": "ready",
            "phase": READY_PHASE,
            "sample_rate": SAMPLE_RATE,
            "backend": "orpheus-gguf",
        }))
        # Enregistre le client pour broadcast de transition de phase
        CONNECTED_CLIENTS.add(ws)
        # v5.2 FSM/WS audit : on dispatche la synthèse dans une Task pour
        # que le `async for raw in ws` puisse continuer à lire les messages
        # (notamment `cancel`) pendant la génération. Avant : cancel était
        # ignoré jusqu'à la fin de _do_synthesize (5–60 s de retard).
        synth_task: "asyncio.Task | None" = None
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
                    if READY_PHASE != "ready_online":
                        await ws.send(json.dumps({
                            "type": "error",
                            "message": f"orpheus not ready (phase={READY_PHASE})",
                        }))
                        continue
                    # Si une synthèse précédente est encore en cours, on l'annule
                    # avant de lancer la nouvelle (sémantique : un seul stream
                    # actif par session).
                    if synth_task and not synth_task.done():
                        self._cancel.set()
                        try:
                            await synth_task
                        except Exception:
                            log.exception("synth_task précédent err")
                    self._cancel.clear()
                    synth_task = asyncio.create_task(self._do_synthesize(ws, msg))
                elif t == "cancel":
                    self._cancel.set()
                elif t == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                elif t == "list_voices":
                    # Patch anti-XTTS : on n'expose qu'une seule voix logique
                    # cote client ("orpheus"). Le mapping vers le token GGUF
                    # reel est fait par _resolve_voice.
                    await ws.send(json.dumps({
                        "type": "voices",
                        "available": ["orpheus"],
                        "current": "orpheus",
                    }))
                elif t == "set_voice":
                    # Patch anti-XTTS : on resout via _resolve_voice pour
                    # accepter "orpheus" (et remapper les anciens IDs XTTS).
                    requested = (msg.get("voice") or "").strip().lower()
                    resolved = _resolve_voice(requested)
                    if resolved in STATE.voices:
                        STATE.default_voice = resolved
                        await ws.send(json.dumps({
                            "type": "voice_set",
                            "voice": "orpheus",
                        }))
                    else:
                        await ws.send(json.dumps({
                            "type": "error",
                            "message": f"unknown voice: {requested!r}",
                        }))
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception:
            log.exception("Session erreur")
        finally:
            # Annule toute synth en vol avant de fermer
            if synth_task and not synth_task.done():
                self._cancel.set()
                try:
                    await asyncio.wait_for(synth_task, timeout=2.0)
                except (asyncio.TimeoutError, Exception):
                    synth_task.cancel()
            CONNECTED_CLIENTS.discard(ws)

    @profile_block("Orpheus _do_synthesize (synth)", threshold_ms=20)
    async def _do_synthesize(self, ws, msg: dict) -> None:
        text = (msg.get("text") or "").strip()
        if not text:
            await ws.send(json.dumps({"type": "error", "message": "Empty text"}))
            return

        # Rate par defaut : env ORPHEUS_DEFAULT_RATE > fallback 0.93.
        try:
            _env_rate = float(os.environ.get("ORPHEUS_DEFAULT_RATE", "0.93"))
        except ValueError:
            _env_rate = 0.93
        rate = float(msg.get("rate", _env_rate))

        # Pauses de pacing inter-phrase / inter-virgule (silence PCM16 zero).
        try:
            _sent_ms = int(os.environ.get("ORPHEUS_SENTENCE_PAUSE_MS", "0"))
        except ValueError:
            _sent_ms = 0
        try:
            _comma_ms = int(os.environ.get("ORPHEUS_COMMA_PAUSE_MS", "0"))
        except ValueError:
            _comma_ms = 0

        voice = (msg.get("voice") or "").strip().lower() or STATE.default_voice
        await ws.send(json.dumps({"type": "start", "text": text}))

        target_bytes = self.chunk_bytes
        chunk_duration_s = target_bytes / float(SAMPLE_RATE * OUTPUT_BYTES_PER_SAMPLE)

        # ── Segmentation par phrase / virgule pour injecter du silence ──
        # On garde le texte intact si pauses=0 (ancien comportement).
        def _segment(t: str) -> list[tuple[str, int]]:
            if _sent_ms <= 0 and _comma_ms <= 0:
                return [(t, 0)]
            out: list[tuple[str, int]] = []
            buf: list[str] = []
            i = 0
            n = len(t)
            while i < n:
                ch = t[i]
                buf.append(ch)
                if ch in ".!?;":
                    seg = "".join(buf).strip()
                    if seg:
                        out.append((seg, _sent_ms))
                    buf = []
                elif ch == ",":
                    seg = "".join(buf).strip()
                    if seg:
                        out.append((seg, _comma_ms))
                    buf = []
                i += 1
            tail = "".join(buf).strip()
            if tail:
                out.append((tail, 0))
            return out or [(t, 0)]

        segments = _segment(text)

        loop = asyncio.get_event_loop()
        t0 = time.monotonic()
        first_chunk_ms = None
        total_bytes = 0
        chunks_sent = 0
        err_msg: "str | None" = None
        next_send_at = None  # rempli apres le 1er chunk

        for seg_idx, (seg_text, pause_ms) in enumerate(segments):
            if self._cancel.is_set():
                break

            queue: asyncio.Queue = asyncio.Queue(maxsize=64)
            SENTINEL = object()

            def _producer(_seg=seg_text) -> None:
                try:
                    for pcm_chunk in _stream_pcm(
                        text=_seg,
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

            fut = loop.run_in_executor(Session._executor, _producer)

            while True:
                item = await queue.get()
                if item is SENTINEL:
                    break
                if isinstance(item, tuple) and item[0] == "error":
                    err_msg = item[1]
                    break
                if self._cancel.is_set():
                    continue

                n = len(item)
                if n == 0:
                    continue
                if n % OUTPUT_BYTES_PER_SAMPLE != 0:
                    log.warning("[ws] chunk mal aligne (%d B), troncature", n)
                    item = item[: n - (n % OUTPUT_BYTES_PER_SAMPLE)]
                    n = len(item)

                now = time.monotonic()
                if next_send_at is not None:
                    wait = next_send_at - now
                    if wait > 0:
                        await asyncio.sleep(min(wait, chunk_duration_s))
                await ws.send(item)
                sent_at = time.monotonic()
                total_bytes += n
                chunks_sent += 1
                if first_chunk_ms is None:
                    first_chunk_ms = (sent_at - t0) * 1000.0
                    log.info(
                        "[ws] first_chunk_ms=%.0f size=%dB dur=%.1fms segs=%d",
                        first_chunk_ms, n, chunk_duration_s * 1000.0, len(segments),
                    )
                    next_send_at = sent_at + chunk_duration_s
                else:
                    next_send_at = max(sent_at, next_send_at) + chunk_duration_s

            await fut

            if err_msg:
                break

            # Silence inter-segment : on emet des chunks de zero PCM16 a la
            # cadence reelle, pour respecter la timeline cote client.
            if pause_ms > 0 and seg_idx < len(segments) - 1 and not self._cancel.is_set():
                silence_total = int(SAMPLE_RATE * pause_ms / 1000) * OUTPUT_BYTES_PER_SAMPLE
                # Aligne sur target_bytes
                full_chunks = silence_total // target_bytes
                for _ in range(max(1, full_chunks)):
                    if self._cancel.is_set():
                        break
                    now = time.monotonic()
                    if next_send_at is not None:
                        wait = next_send_at - now
                        if wait > 0:
                            await asyncio.sleep(min(wait, chunk_duration_s))
                    await ws.send(_SILENCE_PAD[:target_bytes])
                    sent_at = time.monotonic()
                    total_bytes += target_bytes
                    chunks_sent += 1
                    next_send_at = (next_send_at or sent_at) + chunk_duration_s

            if err_msg:
                break

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
    # Import différé : ce module est dans services/, le helper dans python/shared.
    try:
        from python.shared.graceful_shutdown import install_shutdown
    except ImportError:
        import sys, pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
        from python.shared.graceful_shutdown import install_shutdown
    token = install_shutdown(name="orpheus")
    async with websockets.serve(
        handler,
        bind_host,
        port,
        max_size=None,
        process_request=process_request,
    ) as server:
        try:
            await token.wait()
        finally:
            log.info("[orpheus] fermeture WS server (clients=%d)", len(CONNECTED_CLIENTS))
            for ws in list(CONNECTED_CLIENTS):
                try:
                    await ws.close()
                except Exception:
                    pass
            CONNECTED_CLIENTS.clear()


def _warmup() -> None:
    """Warmup LLM complet (multi-voix) pour amortir l'init CUDA et stabiliser
    le first_chunk de la 1re synthese reelle. Couvre toutes les voix declarees
    (pierre, amelie, marie...) car llama.cpp re-allouer le KV cache au 1er
    appel par voix peut couter ~300-400 ms supplementaires.
    Utilise le meme chunk_bytes que le runtime (lu via ORPHEUS_WS_CHUNK_BYTES)
    pour amortir aussi le bon chemin SNAC->WAV.
    Aucun audio n'est emis (chunks consommes et jetes), aucun token logge.
    """
    try:
        t_total = time.monotonic()
        cancel = threading.Event()
        # Meme chunk_bytes que le runtime (1920 en prod) pour ne pas laisser
        # un cold path SNAC->WAV non amorti.
        chunk_bytes = int(os.environ.get("ORPHEUS_WS_CHUNK_BYTES", "1920"))
        # Phrase courte mais > 1 token : force l'init reelle des kernels
        # CUDA (cuBLAS GEMM, flash-attn, KV cache prefill) sur un prompt
        # equivalent a une vraie requete utilisateur.
        warm_text = "Bonjour, ceci est un warmup interne."
        per_voice_ms = []
        for voice in STATE.voices:
            t_v = time.monotonic()
            n = 0
            for chunk in _stream_pcm(warm_text, voice, 1.0, chunk_bytes, cancel):
                n += len(chunk)
            per_voice_ms.append((voice, (time.monotonic() - t_v) * 1000.0, n))
        details = " | ".join(f"{v}={ms:.0f}ms/{nb}B" for v, ms, nb in per_voice_ms)
        log.info(
            "[warmup] complet en %.0f ms chunk=%dB (%s)",
            (time.monotonic() - t_total) * 1000.0, chunk_bytes, details,
        )
    except Exception as exc:
        log.warning("[warmup] echec (non fatal): %s", exc)


async def _broadcast_phase(new_phase: str) -> None:
    """Notifie tous les clients connectés d'une transition de phase readiness."""
    global READY_PHASE
    READY_PHASE = new_phase
    payload = json.dumps({
        "type": "ready",
        "phase": new_phase,
        "sample_rate": SAMPLE_RATE,
        "backend": "orpheus-gguf",
    })
    log.info("[phase] -> %s (clients=%d)", new_phase, len(CONNECTED_CLIENTS))
    dead = []
    for ws in list(CONNECTED_CLIENTS):
        try:
            await ws.send(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        CONNECTED_CLIENTS.discard(ws)


async def _bg_load(do_warmup: bool) -> None:
    """Charge les modèles + warmup en arrière-plan, sans bloquer le port WS."""
    loop = asyncio.get_running_loop()
    try:
        log.info("[bg_load] chargement GGUF + SNAC...")
        await loop.run_in_executor(None, load_models)
        await _broadcast_phase("ready_warmup")
        if do_warmup:
            log.info("[bg_load] warmup...")
            await loop.run_in_executor(None, _warmup)
        await _broadcast_phase("ready_online")
        log.info("[bg_load] Orpheus ONLINE")
    except Exception:
        log.exception("[bg_load] echec")


async def _async_main(host: str, port: int, chunk_bytes: int, do_warmup: bool) -> None:
    # Lance le serveur WS d'abord (port ouvert immédiatement, phase=ready_loading)
    # puis charge les modèles en arrière-plan.
    load_task = asyncio.create_task(_bg_load(do_warmup))
    try:
        await _serve(host, port, chunk_bytes)
    finally:
        load_task.cancel()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("ORPHEUS_WS_HOST", "0.0.0.0"))
    ap.add_argument("--port", type=int,
                    default=int(os.environ.get("ORPHEUS_WS_PORT", "8767")))
    ap.add_argument("--ws-chunk-bytes", type=int,
                    default=int(os.environ.get("ORPHEUS_WS_CHUNK_BYTES", "480")))
    ap.add_argument("--no-warmup", action="store_true")
    args = ap.parse_args()

    asyncio.run(_async_main(args.host, args.port, args.ws_chunk_bytes, not args.no_warmup))


if __name__ == "__main__":
    main()
