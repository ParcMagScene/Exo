"""
EXO v8.2 — Fused Pipeline STT → LLM → TTS

Pipeline fusionné ultra-low latency :
- Réception des résultats partiels STT → pré-analyse LLM anticipative
- Résultat final STT → réponse LLM complète → streaming TTS immédiat
- Coordination des 3 étages avec timestamps, métriques, traces

Le pipeline coordonne les microservices Python (STT port 8766, TTS port 8767)
et la GUI (port 8765). Le LLM réel tourne en C++ (ClaudeAPI).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Coroutine, Optional

log = logging.getLogger("pipeline.fused")


class PipelineState(Enum):
    IDLE = auto()
    LISTENING = auto()
    TRANSCRIBING = auto()
    ANTICIPATING = auto()   # pré-analyse LLM sur partial
    THINKING = auto()       # réponse LLM finale
    SPEAKING = auto()
    ERROR = auto()


@dataclass
class InteractionContext:
    """Contexte d'une interaction vocale complète."""
    interaction_id: str = ""
    t_start: float = 0.0
    t_stt_start: float = 0.0
    t_stt_end: float = 0.0
    t_llm_start: float = 0.0
    t_llm_first_token: float = 0.0
    t_llm_end: float = 0.0
    t_tts_start: float = 0.0
    t_tts_first_chunk: float = 0.0
    t_tts_end: float = 0.0
    partial_texts: list[str] = field(default_factory=list)
    final_text: str = ""
    response_text: str = ""
    anticipation_result: str = ""
    state: PipelineState = PipelineState.IDLE

    @property
    def stt_latency_ms(self) -> float:
        if self.t_stt_start and self.t_stt_end:
            return (self.t_stt_end - self.t_stt_start) * 1000
        return 0.0

    @property
    def llm_first_token_ms(self) -> float:
        if self.t_llm_start and self.t_llm_first_token:
            return (self.t_llm_first_token - self.t_llm_start) * 1000
        return 0.0

    @property
    def llm_latency_ms(self) -> float:
        if self.t_llm_start and self.t_llm_end:
            return (self.t_llm_end - self.t_llm_start) * 1000
        return 0.0

    @property
    def tts_first_chunk_ms(self) -> float:
        if self.t_tts_start and self.t_tts_first_chunk:
            return (self.t_tts_first_chunk - self.t_tts_start) * 1000
        return 0.0

    @property
    def total_latency_ms(self) -> float:
        if self.t_start and self.t_tts_first_chunk:
            return (self.t_tts_first_chunk - self.t_start) * 1000
        return 0.0

    def snapshot(self) -> dict[str, Any]:
        return {
            "interaction_id": self.interaction_id,
            "state": self.state.name,
            "stt_latency_ms": round(self.stt_latency_ms, 1),
            "llm_first_token_ms": round(self.llm_first_token_ms, 1),
            "llm_latency_ms": round(self.llm_latency_ms, 1),
            "tts_first_chunk_ms": round(self.tts_first_chunk_ms, 1),
            "total_latency_ms": round(self.total_latency_ms, 1),
            "final_text": self.final_text,
            "anticipation_used": bool(self.anticipation_result),
        }


# Type aliases pour les callbacks
SendFn = Callable[..., Coroutine[Any, Any, str]]
StreamFn = Callable[..., Coroutine[Any, Any, None]]


class FusedPipeline:
    """Pipeline fusionné STT → LLM → TTS avec anticipation.

    Coordonne les étages :
    - on_partial(text)  : résultat partiel STT → lance pré-analyse LLM si assez long
    - on_final(text)    : résultat final STT → LLM complet → TTS streaming
    - on_llm_token(tok) : token LLM reçu → accumule et flush vers TTS
    """

    # Seuils
    ANTICIPATION_MIN_CHARS = 15   # minimum pour lancer anticipation
    ANTICIPATION_COOLDOWN = 1.5   # secondes entre deux anticipations
    SENTENCE_FLUSH_CHARS = ('.', '!', '?', ':', ';')

    def __init__(
        self,
        *,
        llm_send: Optional[SendFn] = None,
        tts_stream: Optional[StreamFn] = None,
        on_state_change: Optional[Callable[[PipelineState], Any]] = None,
    ):
        self._llm_send = llm_send
        self._tts_stream = tts_stream
        self._on_state_change = on_state_change

        self._ctx: Optional[InteractionContext] = None
        self._state = PipelineState.IDLE
        self._interaction_counter = 0
        self._last_anticipation: float = 0.0
        self._anticipation_task: Optional[asyncio.Task] = None
        self._current_task: Optional[asyncio.Task] = None

        # Tampon de tokens pour TTS flush par phrase
        self._token_buffer: list[str] = []
        self._sentence_buffer = ""

        # Historique des dernières interactions
        self._history: list[dict[str, Any]] = []
        self._max_history = 50

    @property
    def state(self) -> PipelineState:
        return self._state

    @property
    def current_context(self) -> Optional[InteractionContext]:
        return self._ctx

    def _set_state(self, new_state: PipelineState) -> None:
        if self._state != new_state:
            old = self._state
            self._state = new_state
            if self._ctx:
                self._ctx.state = new_state
            log.debug(f"Pipeline: {old.name} → {new_state.name}")
            if self._on_state_change:
                try:
                    self._on_state_change(new_state)
                except Exception:
                    pass

    def begin_interaction(self) -> InteractionContext:
        """Démarre une nouvelle interaction vocale."""
        self._cancel_pending()
        self._interaction_counter += 1
        ctx = InteractionContext(
            interaction_id=f"int-{self._interaction_counter:06d}",
            t_start=time.perf_counter(),
        )
        self._ctx = ctx
        self._token_buffer.clear()
        self._sentence_buffer = ""
        self._set_state(PipelineState.LISTENING)
        log.info(f"Interaction {ctx.interaction_id} démarrée")
        return ctx

    async def on_partial(self, text: str) -> None:
        """Réception d'un résultat partiel STT → anticipation LLM si pertinent."""
        if not self._ctx:
            return
        self._ctx.partial_texts.append(text)
        self._ctx.t_stt_start = self._ctx.t_stt_start or time.perf_counter()
        self._set_state(PipelineState.TRANSCRIBING)

        # Lancer anticipation si le texte est assez long et cooldown respecté
        now = time.monotonic()
        if (
            len(text) >= self.ANTICIPATION_MIN_CHARS
            and (now - self._last_anticipation) >= self.ANTICIPATION_COOLDOWN
            and self._llm_send
        ):
            self._last_anticipation = now
            self._cancel_anticipation()
            self._anticipation_task = asyncio.ensure_future(
                self._run_anticipation(text)
            )

    async def _run_anticipation(self, partial_text: str) -> None:
        """Pré-analyse LLM sur un résultat partiel."""
        if not self._llm_send:
            return
        self._set_state(PipelineState.ANTICIPATING)
        try:
            prompt = (
                f"L'utilisateur est en train de dire: \"{partial_text}\"\n"
                "Prépare une pré-analyse courte (1-2 phrases) de ce que "
                "l'utilisateur pourrait demander. Sois concis."
            )
            result = await self._llm_send(prompt, 50, "")
            if self._ctx:
                self._ctx.anticipation_result = result
                log.debug(f"Anticipation: {result[:80]}...")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.debug(f"Anticipation ignorée: {exc}")

    async def on_final(self, text: str) -> None:
        """Résultat final STT → pipeline complet LLM → TTS."""
        if not self._ctx:
            self.begin_interaction()
        ctx = self._ctx
        assert ctx is not None

        ctx.final_text = text
        ctx.t_stt_end = time.perf_counter()
        self._cancel_anticipation()
        self._set_state(PipelineState.THINKING)

        log.info(f"[{ctx.interaction_id}] Final STT: {text}")
        log.info(f"[{ctx.interaction_id}] STT latency: {ctx.stt_latency_ms:.0f}ms")

        # LLM
        if self._llm_send:
            ctx.t_llm_start = time.perf_counter()
            try:
                response = await self._llm_send(text, 1024, "")
                ctx.t_llm_first_token = ctx.t_llm_first_token or time.perf_counter()
                ctx.t_llm_end = time.perf_counter()
                ctx.response_text = response
                log.info(
                    f"[{ctx.interaction_id}] LLM latency: {ctx.llm_latency_ms:.0f}ms"
                )
            except Exception as exc:
                log.error(f"[{ctx.interaction_id}] LLM erreur: {exc}")
                self._set_state(PipelineState.ERROR)
                self._finish_interaction()
                return

        # TTS streaming
        if self._tts_stream and ctx.response_text:
            self._set_state(PipelineState.SPEAKING)
            ctx.t_tts_start = time.perf_counter()
            try:
                await self._tts_stream(ctx.response_text)
                if not ctx.t_tts_first_chunk:
                    ctx.t_tts_first_chunk = time.perf_counter()
                ctx.t_tts_end = time.perf_counter()
            except Exception as exc:
                log.error(f"[{ctx.interaction_id}] TTS erreur: {exc}")

        log.info(
            f"[{ctx.interaction_id}] Total pipeline: {ctx.total_latency_ms:.0f}ms"
        )
        self._finish_interaction()

    def on_llm_token(self, token: str) -> Optional[str]:
        """Reçoit un token LLM en streaming. Retourne une phrase complète quand prête.

        Accumule les tokens et flush par phrase pour le TTS.
        """
        if self._ctx and not self._ctx.t_llm_first_token:
            self._ctx.t_llm_first_token = time.perf_counter()

        self._sentence_buffer += token
        # Vérifier si on a une phrase complète
        for ch in self.SENTENCE_FLUSH_CHARS:
            idx = self._sentence_buffer.rfind(ch)
            if idx >= 0 and len(self._sentence_buffer[:idx + 1].strip()) >= 5:
                sentence = self._sentence_buffer[:idx + 1].strip()
                self._sentence_buffer = self._sentence_buffer[idx + 1:]
                return sentence
        return None

    def flush_sentence_buffer(self) -> Optional[str]:
        """Flush le buffer de phrases restant (fin de réponse LLM)."""
        remaining = self._sentence_buffer.strip()
        self._sentence_buffer = ""
        return remaining if remaining else None

    def _finish_interaction(self) -> None:
        """Termine l'interaction et archiver."""
        if self._ctx:
            snapshot = self._ctx.snapshot()
            self._history.append(snapshot)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            log.info(f"[{self._ctx.interaction_id}] Interaction terminée")
        self._set_state(PipelineState.IDLE)
        self._ctx = None

    def _cancel_anticipation(self) -> None:
        if self._anticipation_task and not self._anticipation_task.done():
            self._anticipation_task.cancel()
            self._anticipation_task = None

    def _cancel_pending(self) -> None:
        self._cancel_anticipation()
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            self._current_task = None

    def cancel(self) -> None:
        """Annule l'interaction en cours."""
        self._cancel_pending()
        if self._ctx:
            log.info(f"[{self._ctx.interaction_id}] Interaction annulée")
        self._set_state(PipelineState.IDLE)
        self._ctx = None

    def metrics(self) -> dict[str, Any]:
        """Métriques du pipeline fusionné."""
        recent = self._history[-20:] if self._history else []
        latencies = [h["total_latency_ms"] for h in recent if h["total_latency_ms"] > 0]
        stt_lats = [h["stt_latency_ms"] for h in recent if h["stt_latency_ms"] > 0]
        llm_lats = [h["llm_latency_ms"] for h in recent if h["llm_latency_ms"] > 0]
        tts_lats = [h["tts_first_chunk_ms"] for h in recent if h["tts_first_chunk_ms"] > 0]
        anticipation_used = sum(1 for h in recent if h.get("anticipation_used"))

        def _avg(vals: list[float]) -> float:
            return round(sum(vals) / len(vals), 1) if vals else 0.0

        def _p95(vals: list[float]) -> float:
            if not vals:
                return 0.0
            s = sorted(vals)
            idx = int(len(s) * 0.95)
            return round(s[min(idx, len(s) - 1)], 1)

        return {
            "state": self._state.name,
            "total_interactions": self._interaction_counter,
            "avg_total_ms": _avg(latencies),
            "p95_total_ms": _p95(latencies),
            "avg_stt_ms": _avg(stt_lats),
            "avg_llm_ms": _avg(llm_lats),
            "avg_tts_first_chunk_ms": _avg(tts_lats),
            "anticipation_used": anticipation_used,
            "recent_count": len(recent),
        }

    def history(self, n: int = 10) -> list[dict[str, Any]]:
        """Retourne les n dernières interactions."""
        return list(self._history[-n:])
