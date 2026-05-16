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

# ---------------------------------------------------------------------------
# Hardening 2026 — réutilisation de shared.with_timeout si disponible.
# Fallback transparent si le service est exécuté hors PYTHONPATH=python/.
# ---------------------------------------------------------------------------
try:  # pragma: no cover - import opportuniste
    from shared.hardening import with_timeout as _shared_with_timeout  # type: ignore
except Exception:  # noqa: BLE001
    _shared_with_timeout = None


async def _run_with_timeout(coro, timeout_s: float, label: str, fallback=None):
    """Exécute *coro* avec timeout, en log structuré et fallback contrôlé.

    Utilise shared.with_timeout si dispo (logs centralisés), sinon fallback
    sur asyncio.wait_for.
    """
    if _shared_with_timeout is not None:
        return await _shared_with_timeout(coro, timeout_s, label=label, fallback=fallback)
    try:
        return await asyncio.wait_for(coro, timeout=timeout_s)
    except asyncio.TimeoutError:
        log.warning("[fsm][timeout] %s >%.1fs — fallback appliqué", label, timeout_s)
        return fallback


class PipelineState(Enum):
    IDLE = auto()
    LISTENING = auto()
    TRANSCRIBING = auto()
    ANTICIPATING = auto()   # pré-analyse LLM sur partial
    THINKING = auto()       # réponse LLM finale
    SPEAKING = auto()
    ERROR = auto()


# Table de transitions tolérées (validation soft : on n'interdit jamais,
# on journalise simplement les transitions inattendues pour audit).
# Tous les états peuvent retomber en IDLE ou ERROR (récupération/sécurité).
_VALID_TRANSITIONS: dict["PipelineState", set["PipelineState"]] = {
    # rempli après la définition complète de l'Enum, juste en dessous.
}


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


# Renseigne la table de transitions après la définition de l'Enum.
_VALID_TRANSITIONS.update({
    PipelineState.IDLE:         {PipelineState.LISTENING, PipelineState.THINKING, PipelineState.ERROR},
    PipelineState.LISTENING:    {PipelineState.TRANSCRIBING, PipelineState.IDLE, PipelineState.ERROR},
    PipelineState.TRANSCRIBING: {PipelineState.ANTICIPATING, PipelineState.THINKING, PipelineState.LISTENING, PipelineState.IDLE, PipelineState.ERROR},
    PipelineState.ANTICIPATING: {PipelineState.TRANSCRIBING, PipelineState.THINKING, PipelineState.IDLE, PipelineState.ERROR},
    PipelineState.THINKING:     {PipelineState.SPEAKING, PipelineState.IDLE, PipelineState.ERROR},
    PipelineState.SPEAKING:     {PipelineState.IDLE, PipelineState.LISTENING, PipelineState.ERROR},
    PipelineState.ERROR:        {PipelineState.IDLE, PipelineState.LISTENING},
})


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

    # Timeouts explicites — protègent le pipeline contre des appels bloquants.
    # Valeurs prudentes : LLM peut être lent, TTS streaming peut couvrir une réponse longue.
    LLM_TIMEOUT_S: float = 30.0
    TTS_TIMEOUT_S: float = 60.0
    ANTICIPATION_TIMEOUT_S: float = 5.0
    ERROR_RECOVERY_DELAY_S: float = 0.5

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

        # Métriques FSM (compteurs cumulés)
        self._metrics: dict[str, int] = {
            "transitions": 0,
            "transitions_unexpected": 0,
            "interruptions": 0,
            "timeouts_llm": 0,
            "timeouts_tts": 0,
            "errors_llm": 0,
            "errors_tts": 0,
        }

        # Dédup anticipation : on ne relance pas sur un préfixe déjà analysé.
        self._last_anticipation_text: str = ""

        # Drapeau d'interruption en cours (priorité 1)
        self._interrupt_requested: bool = False

    @property
    def state(self) -> PipelineState:
        return self._state

    @property
    def current_context(self) -> Optional[InteractionContext]:
        return self._ctx

    def _set_state(self, new_state: PipelineState) -> None:
        if self._state != new_state:
            old = self._state
            # Validation soft : log si transition non listée mais on n'interdit jamais.
            allowed = _VALID_TRANSITIONS.get(old, set())
            if new_state not in allowed:
                self._metrics["transitions_unexpected"] += 1
                log.warning(
                    "[fsm][transition-inattendue] %s -> %s (int=%s)",
                    old.name, new_state.name,
                    self._ctx.interaction_id if self._ctx else "-",
                )
            self._state = new_state
            self._metrics["transitions"] += 1
            if self._ctx:
                self._ctx.state = new_state
            log.info(
                "[fsm][state] %s -> %s (int=%s)",
                old.name, new_state.name,
                self._ctx.interaction_id if self._ctx else "-",
            )
            if self._on_state_change:
                try:
                    self._on_state_change(new_state)
                except Exception as exc:  # noqa: BLE001
                    log.error("[fsm][callback] on_state_change a levé : %s", exc)

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
        self._interrupt_requested = False
        self._last_anticipation_text = ""
        self._set_state(PipelineState.LISTENING)
        log.info("[fsm][begin][int=%s]", ctx.interaction_id)
        return ctx

    async def on_partial(self, text: str) -> None:
        """Réception d'un résultat partiel STT → anticipation LLM si pertinent.

        Priorité 1 : si on parle déjà (SPEAKING), un nouveau partiel utilisateur
        déclenche une interruption immédiate (barge-in) avant de reprendre le
        cycle d'écoute. Cela évite que l'assistant continue à parler par-dessus.
        """
        # Barge-in : l'utilisateur reprend la parole pendant TTS/THINKING.
        if self._state in (PipelineState.SPEAKING, PipelineState.THINKING):
            log.info("[fsm][barge-in] partial STT pendant %s — interruption", self._state.name)
            self.interrupt()
            # On rebascule en LISTENING pour démarrer un nouveau cycle propre.
            if not self._ctx:
                self.begin_interaction()

        if not self._ctx:
            return
        self._ctx.partial_texts.append(text)
        self._ctx.t_stt_start = self._ctx.t_stt_start or time.perf_counter()
        self._set_state(PipelineState.TRANSCRIBING)

        # Lancer anticipation si le texte est assez long, cooldown respecté,
        # et ce préfixe diffère réellement du précédent (dédup).
        now = time.monotonic()
        if (
            len(text) >= self.ANTICIPATION_MIN_CHARS
            and (now - self._last_anticipation) >= self.ANTICIPATION_COOLDOWN
            and self._llm_send
            and text != self._last_anticipation_text
        ):
            self._last_anticipation = now
            self._last_anticipation_text = text
            self._cancel_anticipation()
            self._anticipation_task = asyncio.ensure_future(
                self._run_anticipation(text)
            )

    async def _run_anticipation(self, partial_text: str) -> None:
        """Pré-analyse LLM sur un résultat partiel — bornée par timeout court."""
        if not self._llm_send:
            return
        self._set_state(PipelineState.ANTICIPATING)
        try:
            prompt = (
                f"L'utilisateur est en train de dire: \"{partial_text}\"\n"
                "Prépare une pré-analyse courte (1-2 phrases) de ce que "
                "l'utilisateur pourrait demander. Sois concis."
            )
            result = await _run_with_timeout(
                self._llm_send(prompt, 50, ""),
                self.ANTICIPATION_TIMEOUT_S,
                label="anticipation_llm",
                fallback="",
            )
            if self._ctx and result:
                self._ctx.anticipation_result = result
                log.debug("[fsm][anticipation] %s...", str(result)[:80])
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.debug("[fsm][anticipation] ignorée : %s", exc)

    async def on_final(self, text: str) -> None:
        """Résultat final STT → pipeline complet LLM → TTS, avec timeouts stricts."""
        if not self._ctx:
            self.begin_interaction()
        ctx = self._ctx
        assert ctx is not None

        ctx.final_text = text
        ctx.t_stt_end = time.perf_counter()
        self._cancel_anticipation()
        self._interrupt_requested = False
        self._set_state(PipelineState.THINKING)

        log.info("[fsm][final-stt][int=%s] %s", ctx.interaction_id, text)
        log.info("[fsm][stt-lat][int=%s] %.0fms", ctx.interaction_id, ctx.stt_latency_ms)

        # LLM (borné)
        if self._llm_send:
            ctx.t_llm_start = time.perf_counter()
            try:
                response = await _run_with_timeout(
                    self._llm_send(text, 1024, ""),
                    self.LLM_TIMEOUT_S,
                    label="llm_send",
                    fallback=None,
                )
                if response is None:
                    self._metrics["timeouts_llm"] += 1
                    log.error("[fsm][llm-timeout][int=%s] %.1fs", ctx.interaction_id, self.LLM_TIMEOUT_S)
                    self._set_state(PipelineState.ERROR)
                    await self._recover_from_error()
                    self._finish_interaction()
                    return
                ctx.t_llm_first_token = ctx.t_llm_first_token or time.perf_counter()
                ctx.t_llm_end = time.perf_counter()
                ctx.response_text = response
                log.info("[fsm][llm-lat][int=%s] %.0fms", ctx.interaction_id, ctx.llm_latency_ms)
            except Exception as exc:  # noqa: BLE001
                self._metrics["errors_llm"] += 1
                log.error("[fsm][llm-error][int=%s] %s", ctx.interaction_id, exc)
                self._set_state(PipelineState.ERROR)
                await self._recover_from_error()
                self._finish_interaction()
                return

        # Interruption demandée pendant l'attente LLM ?
        if self._interrupt_requested:
            log.info("[fsm][interrupt][int=%s] avant TTS — abandon", ctx.interaction_id)
            self._finish_interaction()
            return

        # TTS streaming (borné)
        if self._tts_stream and ctx.response_text:
            self._set_state(PipelineState.SPEAKING)
            ctx.t_tts_start = time.perf_counter()
            try:
                await _run_with_timeout(
                    self._tts_stream(ctx.response_text),
                    self.TTS_TIMEOUT_S,
                    label="tts_stream",
                    fallback=None,
                )
                if not ctx.t_tts_first_chunk:
                    ctx.t_tts_first_chunk = time.perf_counter()
                ctx.t_tts_end = time.perf_counter()
            except asyncio.CancelledError:
                log.info("[fsm][tts-cancelled][int=%s]", ctx.interaction_id)
            except Exception as exc:  # noqa: BLE001
                self._metrics["errors_tts"] += 1
                log.error("[fsm][tts-error][int=%s] %s", ctx.interaction_id, exc)

        log.info("[fsm][total][int=%s] %.0fms", ctx.interaction_id, ctx.total_latency_ms)
        self._finish_interaction()

    async def _recover_from_error(self) -> None:
        """Pause brève après ERROR avant de revenir à IDLE (évite boucle)."""
        try:
            await asyncio.sleep(self.ERROR_RECOVERY_DELAY_S)
        except asyncio.CancelledError:
            raise

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
            log.info("[fsm][cancel][int=%s]", self._ctx.interaction_id)
        self._set_state(PipelineState.IDLE)

    def interrupt(self) -> None:
        """Interruption prioritaire (barge-in, stop utilisateur).

        Marque le drapeau, annule anticipations et tâches en cours, force le retour
        en IDLE pour permettre un nouveau cycle d'écoute propre. La sortie TTS
        réelle est arrêtée par le côté qui orchestre le streaming (callback).
        """
        self._metrics["interruptions"] += 1
        self._interrupt_requested = True
        self._cancel_pending()
        if self._ctx:
            log.info("[fsm][interrupt][int=%s] état=%s", self._ctx.interaction_id, self._state.name)
        self._set_state(PipelineState.IDLE)

    def metrics(self) -> dict[str, Any]:
        """Snapshot des métriques FSM (compteurs cumulés)."""
        return {
            "state": self._state.name,
            "history_size": len(self._history),
            **self._metrics,
        }
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
