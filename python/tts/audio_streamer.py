"""
audio_streamer.py — utilitaires de streaming audio pour le TTS EXO.

Rôle:
  - Convertir un tensor / numpy float32 en PCM16 little-endian.
  - Re-segmenter des blocs PCM en chunks WebSocket de taille bornée.
  - Estimer durée audio depuis nb d'octets PCM16 mono.

Pas d'état global, pas de cache. Chaque appel est indépendant.
"""

from __future__ import annotations

from typing import Iterable, Iterator

import numpy as np


# Format de sortie attendu par le client EXO (TTSManager C++).
OUTPUT_SAMPLE_RATE = 24000   # Hz
OUTPUT_CHANNELS = 1
OUTPUT_BYTES_PER_SAMPLE = 2  # PCM16

# Bornes de chunk WebSocket. Plus petit = first_chunk plus court mais overhead
# par message plus élevé. ~10 ms @ 24 kHz mono16 = 480 octets.
DEFAULT_WS_CHUNK_BYTES = 480
MIN_WS_CHUNK_BYTES = 240        # ~5 ms
MAX_WS_CHUNK_BYTES = 4096       # ~85 ms


def float_wave_to_pcm16(wave: np.ndarray) -> bytes:
    """Convertit un signal float (-1..1) en bytes PCM16 LE.

    Normalise uniquement si le pic dépasse 1.0 pour éviter le clip.
    """
    if wave.size == 0:
        return b""
    if wave.dtype != np.float32 and wave.dtype != np.float64:
        wave = wave.astype(np.float32)
    peak = float(np.max(np.abs(wave)))
    if peak > 1.0:
        wave = wave / peak
    pcm = np.clip(wave * 32767.0, -32768.0, 32767.0).astype(np.int16)
    return pcm.tobytes()


def chunk_pcm(pcm: bytes, chunk_size: int = DEFAULT_WS_CHUNK_BYTES) -> Iterator[bytes]:
    """Découpe un buffer PCM16 en chunks de taille `chunk_size` octets.

    Garantit que chaque chunk a une taille paire (alignée échantillon).
    """
    if chunk_size < MIN_WS_CHUNK_BYTES:
        chunk_size = MIN_WS_CHUNK_BYTES
    if chunk_size > MAX_WS_CHUNK_BYTES:
        chunk_size = MAX_WS_CHUNK_BYTES
    if chunk_size % 2 == 1:
        chunk_size -= 1

    n = len(pcm)
    if n == 0:
        return
    for off in range(0, n, chunk_size):
        yield pcm[off:off + chunk_size]


def merge_and_chunk(blocks: Iterable[bytes],
                    chunk_size: int = DEFAULT_WS_CHUNK_BYTES) -> Iterator[bytes]:
    """Re-fragmente un flux de blocs PCM en chunks de taille bornée.

    Utile quand le modèle yield des blocs de taille variable (souvent gros).
    Émet immédiatement chaque chunk dès qu'il est plein → minimise la latence
    perçue côté lecture audio.
    """
    buf = bytearray()
    target = chunk_size if chunk_size % 2 == 0 else chunk_size - 1
    for blk in blocks:
        if not blk:
            continue
        buf.extend(blk)
        while len(buf) >= target:
            out = bytes(buf[:target])
            del buf[:target]
            yield out
    if buf:
        yield bytes(buf)


def pcm_duration_seconds(pcm_bytes: int) -> float:
    """Durée audio (s) pour `pcm_bytes` octets de PCM16 mono à OUTPUT_SAMPLE_RATE."""
    samples = pcm_bytes // OUTPUT_BYTES_PER_SAMPLE
    return samples / float(OUTPUT_SAMPLE_RATE * OUTPUT_CHANNELS)
