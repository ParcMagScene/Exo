"""
EXO v8.2 — TTS Prédictif Streaming

Gestion prédictive du streaming TTS :
- Buffer circulaire de chunks audio pré-synthétisés
- Micro-buffer textuel pour accumulation phrase-par-phrase
- Seuil minimal configurable (200-300ms) avant lecture
- Métriques latence premier chunk, buffer underrun, etc.

Coordonne avec tts_server.py (port 8767) via WebSocket.
"""

from __future__ import annotations

import asyncio
import collections
import logging
import time
from typing import Any, Callable, Coroutine, Optional

log = logging.getLogger("pipeline.tts_predictive")

# ── Configuration ────────────────────────────────────────────
DEFAULT_MIN_BUFFER_MS = 250       # seuil minimum avant lecture
DEFAULT_CHUNK_SIZE = 2048         # taille chunk PCM16 (~43ms à 24kHz)
DEFAULT_BUFFER_CAPACITY = 200    # nombre max de chunks en buffer


class AudioChunk:
    """Chunk audio PCM16 avec métadonnées."""
    __slots__ = ("data", "timestamp", "seq")

    def __init__(self, data: bytes, timestamp: float, seq: int):
        self.data = data
        self.timestamp = timestamp
        self.seq = seq


class CircularAudioBuffer:
    """Buffer circulaire thread-safe pour chunks audio pré-synthétisés."""

    def __init__(self, capacity: int = DEFAULT_BUFFER_CAPACITY):
        self._buffer: collections.deque[AudioChunk] = collections.deque(maxlen=capacity)
        self._seq = 0
        self._total_pushed = 0
        self._total_popped = 0
        self._underruns = 0

    def push(self, data: bytes) -> AudioChunk:
        """Ajoute un chunk audio au buffer."""
        self._seq += 1
        chunk = AudioChunk(data=data, timestamp=time.perf_counter(), seq=self._seq)
        self._buffer.append(chunk)
        self._total_pushed += 1
        return chunk

    def pop(self) -> Optional[AudioChunk]:
        """Retire le plus ancien chunk du buffer."""
        if self._buffer:
            self._total_popped += 1
            return self._buffer.popleft()
        self._underruns += 1
        return None

    def peek(self) -> Optional[AudioChunk]:
        """Regarde le plus ancien chunk sans le retirer."""
        return self._buffer[0] if self._buffer else None

    @property
    def size(self) -> int:
        return len(self._buffer)

    @property
    def empty(self) -> bool:
        return len(self._buffer) == 0

    def clear(self) -> None:
        self._buffer.clear()

    def metrics(self) -> dict[str, Any]:
        return {
            "current_size": len(self._buffer),
            "capacity": self._buffer.maxlen,
            "total_pushed": self._total_pushed,
            "total_popped": self._total_popped,
            "underruns": self._underruns,
        }


class TextAccumulator:
    """Micro-buffer textuel : accumule les tokens LLM par phrase.

    Flush dès qu'une phrase complète est détectée (ponctuation terminale).
    """

    SENTENCE_ENDS = ('.', '!', '?', ':', ';')
    MIN_SENTENCE_LEN = 5  # minimum pour considérer comme phrase

    def __init__(self):
        self._buffer = ""
        self._flushed_count = 0

    def add(self, token: str) -> Optional[str]:
        """Ajoute un token. Retourne phrase complète si prête, sinon None."""
        self._buffer += token
        for ch in self.SENTENCE_ENDS:
            idx = self._buffer.rfind(ch)
            if idx >= 0:
                candidate = self._buffer[:idx + 1].strip()
                if len(candidate) >= self.MIN_SENTENCE_LEN:
                    self._buffer = self._buffer[idx + 1:]
                    self._flushed_count += 1
                    return candidate
        return None

    def flush(self) -> Optional[str]:
        """Force le flush du buffer restant."""
        remaining = self._buffer.strip()
        self._buffer = ""
        if remaining:
            self._flushed_count += 1
            return remaining
        return None

    @property
    def pending(self) -> str:
        return self._buffer

    @property
    def flushed_count(self) -> int:
        return self._flushed_count


class TTSPredictive:
    """Gestionnaire prédictif de TTS streaming.

    Coordonne l'accumulation de texte, la synthèse anticipée,
    et le buffer circulaire pour une lecture fluide.
    """

    def __init__(
        self,
        *,
        min_buffer_ms: float = DEFAULT_MIN_BUFFER_MS,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        buffer_capacity: int = DEFAULT_BUFFER_CAPACITY,
        synthesize_fn: Optional[Callable[..., Coroutine]] = None,
        play_fn: Optional[Callable[[bytes], Coroutine]] = None,
    ):
        self._min_buffer_ms = min_buffer_ms
        self._chunk_size = chunk_size
        self._synthesize_fn = synthesize_fn
        self._play_fn = play_fn

        self._audio_buffer = CircularAudioBuffer(buffer_capacity)
        self._text_accum = TextAccumulator()

        # Métriques
        self._total_sessions = 0
        self._first_chunk_latencies: list[float] = []
        self._active = False
        self._synth_task: Optional[asyncio.Task] = None
        self._play_task: Optional[asyncio.Task] = None
        self._synth_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        self._t_session_start: float = 0.0
        self._t_first_chunk: float = 0.0

    def begin_session(self) -> None:
        """Démarre une session TTS prédictive."""
        self._audio_buffer.clear()
        self._text_accum = TextAccumulator()
        self._synth_queue = asyncio.Queue()
        self._active = True
        self._total_sessions += 1
        self._t_session_start = time.perf_counter()
        self._t_first_chunk = 0.0
        log.debug(f"TTS session #{self._total_sessions} démarrée")

    async def feed_token(self, token: str) -> None:
        """Alimente un token LLM → accumule et synthétise par phrase."""
        sentence = self._text_accum.add(token)
        if sentence:
            await self._synth_queue.put(sentence)
            log.debug(f"Phrase prête: {sentence[:50]}...")

    async def flush(self) -> None:
        """Flush le texte restant pour synthèse."""
        remaining = self._text_accum.flush()
        if remaining:
            await self._synth_queue.put(remaining)
        await self._synth_queue.put(None)  # signal de fin

    async def run_synthesis_loop(self) -> None:
        """Boucle de synthèse : consomme les phrases et les synthétise."""
        if not self._synthesize_fn:
            log.warning("Pas de fonction de synthèse configurée")
            return
        try:
            while self._active:
                sentence = await self._synth_queue.get()
                if sentence is None:
                    break
                try:
                    t0 = time.perf_counter()
                    async for chunk_data in self._synthesize_fn(sentence):
                        chunk = self._audio_buffer.push(chunk_data)
                        if not self._t_first_chunk:
                            self._t_first_chunk = time.perf_counter()
                            latency = (self._t_first_chunk - self._t_session_start) * 1000
                            self._first_chunk_latencies.append(latency)
                            log.info(f"Premier chunk TTS en {latency:.0f}ms")
                    synth_time = (time.perf_counter() - t0) * 1000
                    log.debug(f"Phrase synthétisée en {synth_time:.0f}ms")
                except Exception as exc:
                    log.error(f"Synthèse erreur: {exc}")
        except asyncio.CancelledError:
            pass
        finally:
            self._active = False

    async def run_playback_loop(self) -> None:
        """Boucle de lecture : consomme le buffer audio et joue les chunks.

        Attend que le buffer ait accumulé min_buffer_ms avant de commencer.
        """
        if not self._play_fn:
            log.warning("Pas de fonction de lecture configurée")
            return

        # Attendre le seuil minimum de buffer
        sample_rate = 24000  # CosyVoice2 native rate
        bytes_per_sample = 2  # PCM16
        ms_per_chunk = (self._chunk_size / (sample_rate * bytes_per_sample)) * 1000

        min_chunks = max(1, int(self._min_buffer_ms / ms_per_chunk))
        log.debug(f"Attente de {min_chunks} chunks ({self._min_buffer_ms}ms) avant lecture")

        # Attendre assez de chunks
        while self._active and self._audio_buffer.size < min_chunks:
            await asyncio.sleep(0.01)

        try:
            while self._active or not self._audio_buffer.empty:
                chunk = self._audio_buffer.pop()
                if chunk:
                    await self._play_fn(chunk.data)
                else:
                    if not self._active:
                        break
                    await asyncio.sleep(0.005)  # attendre nouveau chunk
        except asyncio.CancelledError:
            pass

    async def run(self) -> None:
        """Lance synthèse + lecture en parallèle."""
        synth = asyncio.create_task(self.run_synthesis_loop())
        play = asyncio.create_task(self.run_playback_loop())
        await asyncio.gather(synth, play, return_exceptions=True)

    def end_session(self) -> None:
        """Termine la session TTS prédictive."""
        self._active = False
        log.debug(f"TTS session #{self._total_sessions} terminée")

    def cancel(self) -> None:
        """Annule la session en cours."""
        self._active = False
        self._audio_buffer.clear()

    def metrics(self) -> dict[str, Any]:
        """Métriques du TTS prédictif."""
        first_chunk_ms = self._first_chunk_latencies[-20:] if self._first_chunk_latencies else []

        def _avg(vals: list[float]) -> float:
            return round(sum(vals) / len(vals), 1) if vals else 0.0

        return {
            "total_sessions": self._total_sessions,
            "active": self._active,
            "avg_first_chunk_ms": _avg(first_chunk_ms),
            "text_accumulator_flushed": self._text_accum.flushed_count,
            "text_pending": len(self._text_accum.pending),
            "buffer": self._audio_buffer.metrics(),
        }
