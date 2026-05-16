"""

# Patch global EXO : forcer le working directory à D:/EXO/ pour tous les services
import os
os.chdir("D:/EXO/")
exo_server.py — EXO backend server.

Runs:
1. Home Assistant bridge (WebSocket + REST)
2. GUI WebSocket server on ws://localhost:8765
3. BrainEngine function-calling router

This is the main entry point for the Python side of EXO.
"""

from __future__ import annotations

import asyncio
try:
    import ujson as json  # v6.0 perf : 3-5x plus rapide que stdlib (audit perf)
except ImportError:
    import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any

import websockets
import websockets.server

from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9
from shared.config_validator import validate_config_file

from integrations.home_bridge import HomeBridge
from integrations.ha_entities import EntityManager
from integrations.ha_devices import DeviceManager
from integrations.ha_areas import AreaManager
from integrations.ha_actions import ActionDispatcher, TOOL_DEFINITIONS
from integrations.ha_sync import SyncManager

# v8.2 — Ultra-Low Latency modules
from llm_warmup import LLMWarmup
from fused_pipeline import FusedPipeline, PipelineState
from tts_predictive import TTSPredictive
from context_cache import ContextCache, CacheDomain
from cpu_gpu_orchestrator import CPUGPUOrchestrator
from pipeline_profiler import PipelineProfiler
from pipeline_resilience import PipelineResilience
from pipeline_v9 import PipelineV9Integration

# v10 — Agent cognitif
from agent_manager import AgentManager

# v11-v25 — Lazy-loaded via _version_registry (138 modules deferred)
from _version_registry import create_all_versions

# Hardening 2026 — réutilisation des helpers partagés (sûr / opportuniste).
try:
    from shared.hardening import safe_json_loads as _safe_json_loads  # type: ignore
    from shared.hardening import safe_json_dumps as _safe_json_dumps  # type: ignore
except Exception:  # noqa: BLE001
    def _safe_json_loads(raw, default=None):  # type: ignore
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            return default
    def _safe_json_dumps(obj, default="{}"):  # type: ignore
        try:
            return json.dumps(obj)
        except Exception:  # noqa: BLE001
            return default

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("exo.server")

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------

def _load_env() -> None:
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


# ---------------------------------------------------------------------------
# GUI WebSocket server
# ---------------------------------------------------------------------------

class GUIServer:
    """WebSocket server that the React GUI connects to (ws://localhost:8765)."""

    # Ensemble des états reconnus du côté GUI (validation soft : on logge
    # une transition inattendue mais on ne bloque jamais le broadcast pour
    # ne pas casser le pipeline existant).
    _KNOWN_STATES = {
        "IDLE", "LISTENING", "TRANSCRIBING", "ANTICIPATING",
        "THINKING", "SPEAKING", "ERROR",
        "idle", "listening", "transcribing", "anticipating",
        "thinking", "speaking", "error", "interrupting",
        "detecting_speech", "waking", "processing",
    }
    def __init__(self, sync: SyncManager, pipeline_mgr: "PipelineManager",
                 agent_mgr: AgentManager | None = None,
                 v11: dict | None = None,
                 v12: dict | None = None,
                 v13: dict | None = None,
                 v14: dict | None = None,
                 v15: dict | None = None,
                 v16: dict | None = None,
                 v17: dict | None = None,
                 v18: dict | None = None,
                 v19: dict | None = None,
                 v20: dict | None = None,
                 v21: dict | None = None,
                 v22: dict | None = None,
                 v23: dict | None = None,
                 v24: dict | None = None,
                 v25: dict | None = None) -> None:
        self._sync = sync
        self._pipeline = pipeline_mgr
        self._agent = agent_mgr
        self._v11 = v11 or {}
        self._v12 = v12 or {}
        self._v13 = v13 or {}
        self._v14 = v14 or {}
        self._v15 = v15 or {}
        self._v16 = v16 or {}
        self._v17 = v17 or {}
        self._v18 = v18 or {}
        self._v19 = v19 or {}
        self._v20 = v20 or {}
        self._v21 = v21 or {}
        self._v22 = v22 or {}
        self._v23 = v23 or {}
        self._v24 = v24 or {}
        self._v25 = v25 or {}
        self._clients: set[websockets.server.WebSocketServerProtocol] = set()
        self._state = "IDLE"
        self._volume = 0.0
        self._text = ""

    async def handler(self, ws: websockets.server.WebSocketServerProtocol) -> None:
        self._clients.add(ws)
        logger.info("GUI client connected (%d total)", len(self._clients))
        try:
            # ReadinessProtocol v5 — envoyer ready avant le snapshot
            await ws.send(_safe_json_dumps({"type": "ready", "service": "orchestrator"}))

            # Send initial snapshot
            snapshot = self._sync.build_full_snapshot()
            snapshot["state"] = self._state
            snapshot["volume"] = self._volume
            snapshot["text"] = self._text
            await ws.send(_safe_json_dumps(snapshot))

            async for raw in ws:
                try:
                    await self._handle_client_message(ws, raw)
                except Exception as exc:  # noqa: BLE001
                    # Une erreur dans le dispatch d'un message ne doit jamais
                    # tuer la connexion GUI : on logge et on continue.
                    logger.error("GUI message dispatch error: %s", exc, exc_info=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("GUI handler stopped: %s", exc)
        finally:
            self._clients.discard(ws)
            logger.info("GUI client disconnected (%d remaining)", len(self._clients))

    async def _handle_client_message(self, ws: Any, raw: str) -> None:
        msg = _safe_json_loads(raw, default=None)
        if not isinstance(msg, dict):
            return

        msg_type = msg.get("type")

        if msg_type == "ping":
            await ws.send(json.dumps({"type": "pong"}))

        elif msg_type == "plan_move":
            await self._sync.on_plan_move(
                device_id=msg.get("device_id", ""),
                x=msg.get("x", 0),
                y=msg.get("y", 0),
                room=msg.get("room", ""),
            )

        elif msg_type == "settings_update":
            logger.info("Settings update: %s = %s", msg.get("key"), msg.get("value"))

        elif msg_type == "network_scan":
            hosts = msg.get("hosts", [])
            await self._sync.sync_network_devices(hosts)

        elif msg_type == "transcript":
            text = msg.get("text", "")
            timestamp = msg.get("timestamp", 0)
            req_id = msg.get("req_id", "")
            logger.info("[req_id=%s] Voice transcript: %s (ts=%s)", req_id, text, timestamp)
            await self.broadcast({"type": "transcript", "text": text, "req_id": req_id})

        elif msg_type == "partial_transcript":
            text = msg.get("text", "")
            await self.broadcast({"type": "partial_transcript", "text": text})

        elif msg_type == "pipeline_state":
            state = msg.get("state", "idle")
            logger.info("Pipeline state: %s", state)
            await self.push_state(state)

        elif msg_type == "audio_level":
            rms = msg.get("rms", 0.0)
            vad = msg.get("vad_score", 0.0)
            is_speech = msg.get("is_speech", False)
            await self.broadcast({
                "type": "audio_level",
                "rms": rms,
                "vad_score": vad,
                "is_speech": is_speech,
            })

        elif msg_type == "pipeline_metrics":
            metrics = self._pipeline.metrics()
            await ws.send(json.dumps({"type": "pipeline_metrics", **metrics}))

        # v10 — Agent actions
        elif msg_type == "agent_process":
            if self._agent:
                text = msg.get("text", "")
                result = await self._agent.process_intent(text)
                await ws.send(json.dumps({"type": "agent_result", **result}))

        elif msg_type == "agent_health":
            if self._agent:
                health = await self._agent.health_check()
                await ws.send(json.dumps({"type": "agent_health", **health}))

        elif msg_type == "agent_state":
            if self._agent:
                state = self._agent.get_state()
                await ws.send(json.dumps({"type": "agent_state", **state}))

        elif msg_type == "agent_metrics":
            if self._agent:
                metrics = self._agent.get_metrics()
                await ws.send(json.dumps({"type": "agent_metrics", **metrics}))

        # ── v11 — Auto-apprentissage & auto-optimisation ─────
        elif msg_type == "v11_learn":
            eng = self._v11.get("learning")
            if eng:
                entry_id = eng.learn(msg.get("event", {}))
                await ws.send(json.dumps({"type": "v11_learn_result",
                                          "entry_id": entry_id}))

        elif msg_type == "v11_feedback":
            eng = self._v11.get("feedback")
            if eng:
                fb_type = msg.get("feedback_type", "positive")
                event = msg.get("event", {})
                method = getattr(eng, f"feedback_{fb_type}", None)
                if method:
                    method(event)
                await ws.send(json.dumps({"type": "v11_feedback_ack",
                                          "feedback_type": fb_type}))

        elif msg_type == "v11_optimize":
            eng = self._v11.get("optimization")
            if eng:
                result = eng.optimize_all()
                await ws.send(json.dumps({"type": "v11_optimize_result",
                                          **result}))

        elif msg_type == "v11_diagnose":
            eng = self._v11.get("diagnosis")
            if eng:
                report = eng.diagnose()
                await ws.send(json.dumps({"type": "v11_diagnose_result",
                                          **report}))

        elif msg_type == "v11_tune":
            eng = self._v11.get("tuning")
            if eng:
                param = msg.get("parameter", "")
                value = msg.get("value", 0)
                ok = eng.tune(param, float(value))
                await ws.send(json.dumps({"type": "v11_tune_result",
                                          "parameter": param, "applied": ok}))

        elif msg_type == "v11_auto_tune":
            eng = self._v11.get("tuning")
            if eng:
                result = eng.auto_tune_all()
                await ws.send(json.dumps({"type": "v11_auto_tune_result",
                                          **result}))

        elif msg_type == "v11_explain":
            eng = self._v11.get("explanation")
            if eng:
                kind = msg.get("kind", "decision")
                if kind == "decision":
                    text = eng.explain_decision(msg.get("action", ""),
                                                msg.get("context"))
                elif kind == "learning":
                    text = eng.explain_learning(msg.get("entry_id", ""))
                elif kind == "tuning":
                    text = eng.explain_tuning(msg.get("parameter", ""))
                elif kind == "diagnosis":
                    text = eng.explain_diagnosis(msg.get("report", {}))
                elif kind == "optimization":
                    text = eng.explain_optimization(msg.get("record", {}))
                else:
                    text = ""
                await ws.send(json.dumps({"type": "v11_explain_result",
                                          "explanation": text}))

        elif msg_type == "v11_stats":
            stats = {}
            for name, mod in self._v11.items():
                if hasattr(mod, "get_stats"):
                    stats[name] = mod.get_stats()
            await ws.send(json.dumps({"type": "v11_stats", **stats}))

        elif msg_type == "v11_governance":
            eng = self._v11.get("governance")
            if eng:
                sub = msg.get("sub", "rules")
                if sub == "rules":
                    await ws.send(json.dumps({"type": "v11_governance_result",
                                              "rules": eng.get_rules()}))
                elif sub == "set_rules":
                    eng.set_rules(msg.get("rules", {}))
                    await ws.send(json.dumps({"type": "v11_governance_ack"}))
                elif sub == "set_limits":
                    eng.set_limits(msg.get("limits", {}))
                    await ws.send(json.dumps({"type": "v11_governance_ack"}))
                elif sub == "set_permissions":
                    eng.set_permissions(msg.get("permissions", {}))
                    await ws.send(json.dumps({"type": "v11_governance_ack"}))
                elif sub == "audit":
                    log = eng.get_audit_log(msg.get("limit", 50))
                    await ws.send(json.dumps({"type": "v11_governance_audit",
                                              "audit": log}))

        elif msg_type == "v11_supervisor":
            eng = self._v11.get("supervisor")
            if eng:
                sub = msg.get("sub", "drift")
                if sub == "drift":
                    report = eng.get_drift_report()
                    await ws.send(json.dumps({"type": "v11_supervisor_drift",
                                              **report}))
                elif sub == "enforce":
                    result = eng.enforce_rules()
                    await ws.send(json.dumps({"type": "v11_supervisor_enforce",
                                              **result}))
                elif sub == "rollback":
                    entry_id = msg.get("entry_id", "")
                    ok = eng.rollback_learning(entry_id)
                    await ws.send(json.dumps({"type": "v11_supervisor_rollback",
                                              "entry_id": entry_id,
                                              "success": ok}))

        elif msg_type == "v11_memory":
            mem = self._v11.get("meta_memory")
            if mem:
                sub = msg.get("sub", "stats")
                if sub == "stats":
                    await ws.send(json.dumps({"type": "v11_memory_stats",
                                              **mem.get_stats()}))
                elif sub == "search":
                    results = mem.meta_get(msg.get("query", ""))
                    await ws.send(json.dumps({"type": "v11_memory_results",
                                              "results": results}))
                elif sub == "list":
                    entries = mem.list_entries(
                        msg.get("category"), msg.get("limit", 50))
                    await ws.send(json.dumps({"type": "v11_memory_list",
                                              "entries": entries}))

        # ── v12 — Auto-réflexion, méta-raisonnement, auto-cohérence ──
        elif msg_type == "v12_reflect":
            eng = self._v12.get("reflection")
            if eng:
                sub = msg.get("sub", "reasoning")
                if sub == "reasoning":
                    result = eng.reflect_on_reasoning(msg.get("trace", {}))
                elif sub == "plan":
                    result = eng.reflect_on_plan(msg.get("plan", {}))
                elif sub == "decision":
                    result = eng.reflect_on_decision(msg.get("decision", {}))
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v12_reflect_result",
                                          **result}))

        elif msg_type == "v12_meta_reason":
            eng = self._v12.get("reasoning")
            if eng:
                sub = msg.get("sub", "full")
                trace = msg.get("trace", {})
                if sub == "full":
                    result = eng.meta_reason(trace)
                elif sub == "quality":
                    result = eng.evaluate_reasoning_quality(trace)
                elif sub == "improve":
                    result = eng.propose_reasoning_improvements(trace)
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v12_meta_reason_result",
                                          **result}))

        elif msg_type == "v12_evaluate_plan":
            eng = self._v12.get("planner_v2")
            if eng:
                sub = msg.get("sub", "evaluate")
                if sub == "evaluate":
                    result = eng.evaluate_plan(msg.get("plan", {}))
                elif sub == "compare":
                    result = eng.compare_plans(msg.get("plans", []))
                elif sub == "improve":
                    result = eng.improve_plan(msg.get("plan", {}))
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v12_evaluate_plan_result",
                                          **result}))

        elif msg_type == "v12_verify":
            eng = self._v12.get("verifier")
            if eng:
                sub = msg.get("sub", "plan")
                if sub == "plan":
                    result = eng.meta_verify(msg.get("plan", {}))
                elif sub == "reasoning":
                    result = eng.meta_verify_reasoning(msg.get("trace", {}))
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v12_verify_result",
                                          **result}))

        elif msg_type == "v12_consistency":
            eng = self._v12.get("consistency")
            if eng:
                sub = msg.get("sub", "plan")
                if sub == "plan":
                    result = eng.check_consistency(msg.get("plan", {}))
                elif sub == "reasoning":
                    result = eng.check_consistency_reasoning(msg.get("trace", {}))
                elif sub == "enforce":
                    result = eng.enforce_consistency()
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v12_consistency_result",
                                          **result}))

        elif msg_type == "v12_supervise":
            eng = self._v12.get("supervisor_v2")
            if eng:
                sub = msg.get("sub", "reasoning")
                if sub == "reasoning":
                    result = eng.supervise_reasoning(msg.get("trace", {}))
                elif sub == "planning":
                    result = eng.supervise_planning(msg.get("plan", {}))
                elif sub == "enforce":
                    result = eng.enforce_meta_rules()
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v12_supervise_result",
                                          **result}))

        elif msg_type == "v12_explain":
            eng = self._v16.get("explainability")
            if eng:
                kind = msg.get("kind", "plan")
                if kind == "plan":
                    text = eng.explain_plan(msg.get("plan", {}))
                elif kind == "reasoning":
                    text = eng.explain_reasoning(msg.get("trace", {}))
                elif kind == "meta_decision":
                    text = eng.explain_meta_decision(msg.get("decision", {}))
                else:
                    text = ""
                await ws.send(json.dumps({"type": "v12_explain_result",
                                          "explanation": text}))

        elif msg_type == "v12_stats":
            stats = {}
            for name, mod in self._v12.items():
                if hasattr(mod, "get_stats"):
                    stats[name] = mod.get_stats()
            await ws.send(json.dumps({"type": "v12_stats", **stats}))

        # ── v13 — Auto-simulation, prévision, planification prospective ──
        elif msg_type == "v13_simulate":
            eng = self._v13.get("simulation")
            if eng:
                sub = msg.get("sub", "plan")
                if sub == "plan":
                    result = eng.simulate_plan(msg.get("plan", {}))
                elif sub == "step":
                    result = eng.simulate_step(msg.get("step", {}))
                elif sub == "scenario":
                    result = eng.simulate_scenario(msg.get("scenario", {}))
                elif sub == "outcome":
                    result = eng.simulate_outcome(msg.get("plan", {}))
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v13_simulate_result",
                                          **result}))

        elif msg_type == "v13_predict":
            eng = self._v13.get("prediction")
            if eng:
                sub = msg.get("sub", "user_need")
                if sub == "user_need":
                    result = eng.predict_user_need()
                elif sub == "domotic":
                    result = eng.predict_domotic_state()
                elif sub == "network":
                    result = eng.predict_network_state()
                elif sub == "routine":
                    result = eng.predict_routine()
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v13_predict_result",
                                          **result}))

        elif msg_type == "v13_future_plan":
            eng = self._v13.get("future_planner")
            if eng:
                sub = msg.get("sub", "future")
                if sub == "future":
                    result = eng.plan_future_action(
                        msg.get("action", {}), msg.get("time_target", 0))
                elif sub == "conditional":
                    result = eng.plan_conditional_action(
                        msg.get("action", {}), msg.get("condition", {}))
                elif sub == "recurrent":
                    result = eng.plan_recurrent_action(
                        msg.get("action", {}), msg.get("schedule", {}))
                elif sub == "pending":
                    result = {"plans": eng.get_pending_plans()}
                elif sub == "cancel":
                    ok = eng.cancel_plan(msg.get("plan_id", ""))
                    result = {"cancelled": ok}
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v13_future_plan_result",
                                          **result}))

        elif msg_type == "v13_scenarios":
            eng = self._v13.get("multi_scenario")
            if eng:
                sub = msg.get("sub", "generate")
                if sub == "generate":
                    result = eng.generate_future_variants(msg.get("plan", {}))
                elif sub == "compare":
                    result = eng.compare_futures(msg.get("futures", []))
                elif sub == "select":
                    result = eng.select_best_future(msg.get("futures", []))
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v13_scenarios_result",
                                          **result}))

        elif msg_type == "v13_temporal":
            eng = self._v13.get("temporal")
            if eng:
                sub = msg.get("sub", "check")
                if sub == "check":
                    result = eng.check_temporal_conflicts(msg.get("plans", []))
                elif sub == "enforce":
                    result = eng.enforce_temporal_coherence()
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v13_temporal_result",
                                          **result}))

        elif msg_type == "v13_anticipate":
            eng = self._v13.get("anticipation")
            if eng:
                sub = msg.get("sub", "need")
                if sub == "need":
                    result = eng.anticipate_need()
                elif sub == "propose":
                    result = eng.propose_anticipation()
                elif sub == "context":
                    result = eng.prepare_future_context()
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v13_anticipate_result",
                                          **result}))

        elif msg_type == "v13_explain":
            eng = self._v16.get("explainability")
            if eng:
                kind = msg.get("kind", "simulation")
                if kind == "simulation":
                    text = eng.explain_simulation(msg.get("simulation", {}))
                elif kind == "prediction":
                    text = eng.explain_prediction(msg.get("prediction", {}))
                elif kind == "future":
                    # Signature str héritée v3 (v5 forme dict exposée via v15_explain)
                    text = eng.explain_future_str(msg.get("future", {}))
                else:
                    text = ""
                await ws.send(json.dumps({"type": "v13_explain_result",
                                          "explanation": text}))

        elif msg_type == "v13_supervise":
            eng = self._v13.get("supervisor_v3")
            if eng:
                sub = msg.get("sub", "simulation")
                if sub == "simulation":
                    result = eng.supervise_simulation(msg.get("simulation", {}))
                elif sub == "prediction":
                    result = eng.supervise_prediction(msg.get("prediction", {}))
                elif sub == "enforce":
                    result = eng.enforce_future_rules()
                elif sub == "alerts":
                    result = {"alerts": eng.get_alerts(msg.get("limit", 20))}
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v13_supervise_result",
                                          **result}))

        elif msg_type == "v13_stats":
            stats = {}
            for name, mod in self._v13.items():
                if hasattr(mod, "get_stats"):
                    stats[name] = mod.get_stats()
            await ws.send(json.dumps({"type": "v13_stats", **stats}))

        # ── v14 — Cognition distribuée, agents spécialisés ───────
        elif msg_type == "v14_orchestrate":
            eng = self._v14.get("orchestrator")
            if eng:
                result = eng.orchestrate(msg.get("intent", {}))
                await ws.send(json.dumps({"type": "v14_orchestrate_result",
                                          **result}))

        elif msg_type == "v14_agents":
            eng = self._v14.get("registry")
            if eng:
                sub = msg.get("sub", "list")
                if sub == "list":
                    result = {"agents": eng.list_agents()}
                elif sub == "info":
                    result = eng.get_agent_info(msg.get("name", ""))
                elif sub == "dispatch":
                    orch = self._v14.get("orchestrator")
                    if orch:
                        result = orch.dispatch(
                            msg.get("task", {}), msg.get("agent", ""))
                    else:
                        result = {}
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v14_agents_result",
                                          **result}))

        elif msg_type == "v14_messaging":
            eng = self._v14.get("messaging_bus")
            if eng:
                sub = msg.get("sub", "log")
                if sub == "send":
                    result = eng.send(
                        msg.get("sender", ""), msg.get("recipient", ""),
                        msg.get("message", {}))
                elif sub == "broadcast":
                    results = eng.broadcast(
                        msg.get("sender", ""), msg.get("message", {}))
                    result = {"delivered": results}
                elif sub == "log":
                    result = {"log": eng.get_message_log(
                        msg.get("limit", 50))}
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v14_messaging_result",
                                          **result}))

        elif msg_type == "v14_conflicts":
            eng = self._v14.get("conflict_resolver")
            if eng:
                sub = msg.get("sub", "detect")
                if sub == "detect":
                    result = eng.detect_conflicts(
                        msg.get("agent_outputs", []))
                elif sub == "resolve":
                    result = eng.resolve(msg.get("agent_outputs", []))
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v14_conflicts_result",
                                          **result}))

        elif msg_type == "v14_consistency":
            eng = self._v14.get("consistency")
            if eng:
                sub = msg.get("sub", "check")
                if sub == "check":
                    result = eng.check_global_consistency()
                elif sub == "enforce":
                    result = eng.enforce_global_consistency()
                elif sub == "agent":
                    result = eng.check_agent_consistency(
                        msg.get("name", ""))
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v14_consistency_result",
                                          **result}))

        elif msg_type == "v14_supervise":
            eng = self._v14.get("supervisor_v4")
            if eng:
                sub = msg.get("sub", "agent")
                if sub == "agent":
                    result = eng.supervise_agent(msg.get("name", ""))
                elif sub == "interaction":
                    result = eng.supervise_interaction(
                        msg.get("message", {}))
                elif sub == "decision":
                    result = eng.supervise_decision(
                        msg.get("decision", {}))
                elif sub == "enforce":
                    result = eng.enforce_meta_rules()
                elif sub == "alerts":
                    result = {"alerts": eng.get_alerts(
                        msg.get("limit", 20))}
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v14_supervise_result",
                                          **result}))

        elif msg_type == "v14_explain":
            eng = self._v16.get("explainability")
            if eng:
                kind = msg.get("kind", "agent")
                if kind == "agent":
                    result = eng.explain_agent_decision(
                        msg.get("name", ""))
                elif kind == "global":
                    result = eng.explain_global_decision(
                        msg.get("decision", {}))
                elif kind == "conflict":
                    result = eng.explain_conflict_resolution(
                        msg.get("resolution", {}))
                elif kind == "orchestration":
                    result = eng.explain_orchestration(
                        msg.get("orch_result", {}))
                else:
                    result = {}
                await ws.send(json.dumps({"type": "v14_explain_result",
                                          **result}))

        elif msg_type == "v14_stats":
            stats = {}
            for name, mod in self._v14.items():
                if hasattr(mod, "get_stats"):
                    stats[name] = mod.get_stats()
            await ws.send(json.dumps({"type": "v14_stats", **stats}))

        # ── v15 — Architecture cognitive complète ─────────────
        elif msg_type == "v15_expert_infer":
            eng = self._v15.get("expert_system")
            if eng:
                result = eng.infer(msg.get("query", {}))
                await ws.send(json.dumps({"type": "v15_expert_result", **result}))

        elif msg_type == "v15_expert_add_rule":
            eng = self._v15.get("expert_system")
            if eng:
                rule_id = eng.add_rule(msg.get("rule", {}))
                await ws.send(json.dumps({"type": "v15_rule_added", "rule_id": rule_id}))

        elif msg_type == "v15_kg_add":
            kg = self._v15.get("knowledge_graph")
            if kg:
                eid = kg.kg_add(msg.get("node", ""), msg.get("relation", ""),
                                msg.get("target", ""))
                await ws.send(json.dumps({"type": "v15_kg_added", "edge_id": eid}))

        elif msg_type == "v15_kg_query":
            kg = self._v15.get("knowledge_graph")
            if kg:
                results = kg.kg_query(msg.get("pattern", {}))
                await ws.send(json.dumps({"type": "v15_kg_results",
                                          "results": results}))

        elif msg_type == "v15_infer":
            eng = self._v15.get("inference")
            if eng:
                mode = msg.get("mode", "logical")
                if mode == "causal":
                    r = eng.infer_causal(msg.get("chain", []))
                elif mode == "temporal":
                    r = eng.infer_temporal(msg.get("sequence", []))
                elif mode == "contextual":
                    r = eng.infer_contextual(msg.get("context", {}))
                else:
                    r = eng.infer_logical(msg.get("query", {}))
                await ws.send(json.dumps({"type": "v15_inference_result", **r}))

        elif msg_type == "v15_plan":
            cog = self._v15.get("cognitive_agent")
            if cog:
                plan = cog.plan(msg.get("intent", {}))
                await ws.send(json.dumps({"type": "v15_plan_result", **plan}))

        elif msg_type == "v15_execute":
            cog = self._v15.get("cognitive_agent")
            if cog:
                result = cog.execute(msg.get("plan", {}))
                await ws.send(json.dumps({"type": "v15_exec_result", **result}))

        elif msg_type == "v15_reflect":
            mc = self._v15.get("meta_cognition")
            if mc:
                result = mc.reflect(msg.get("trace", {}))
                await ws.send(json.dumps({"type": "v15_reflect_result", **result}))

        elif msg_type == "v15_simulate":
            pe = self._v15.get("prospective")
            if pe:
                result = pe.simulate(msg.get("plan", {}))
                await ws.send(json.dumps({"type": "v15_simulate_result", **result}))

        elif msg_type == "v15_futures":
            pe = self._v15.get("prospective")
            if pe:
                result = pe.generate_futures(msg.get("plan", {}),
                                             msg.get("n", 3))
                await ws.send(json.dumps({"type": "v15_futures_result", **result}))

        elif msg_type == "v15_supervise":
            sup = self._v15.get("supervisor_v5")
            if sup:
                result = sup.supervise_all()
                await ws.send(json.dumps({"type": "v15_supervise_result", **result}))

        elif msg_type == "v15_validate":
            sup = self._v15.get("supervisor_v5")
            if sup:
                result = sup.validate_decision(msg.get("decision", {}))
                await ws.send(json.dumps({"type": "v15_validate_result", **result}))

        elif msg_type == "v15_explain":
            exp = self._v16.get("explainability")
            if exp:
                mode = msg.get("mode", "decision")
                if mode == "inference":
                    r = exp.explain_inference(msg.get("inference", {}))
                elif mode == "future":
                    r = exp.explain_future(msg.get("future", {}))
                elif mode == "conflict":
                    r = exp.explain_conflict(msg.get("conflict", {}))
                elif mode == "full":
                    r = exp.explain_full(msg.get("session", {}))
                else:
                    r = exp.explain_decision(msg.get("decision", {}))
                await ws.send(json.dumps({"type": "v15_explain_result", **r}))

        elif msg_type == "v15_dispatch":
            dc = self._v15.get("distributed")
            if dc:
                result = dc.dispatch(msg.get("task", {}))
                await ws.send(json.dumps({"type": "v15_dispatch_result", **result}))

        elif msg_type == "v15_stats":
            stats = {}
            for name, mod in self._v15.items():
                if hasattr(mod, "get_stats"):
                    stats[name] = mod.get_stats()
            await ws.send(json.dumps({"type": "v15_stats", **stats}))

        # ── v16 — Agents autonomes supervisés, émergence ──────
        elif msg_type == "v16_propose_initiative":
            layer = self._v16.get("autonomous_layer")
            if layer:
                result = layer.propose_initiative(
                    msg.get("agent", ""), msg.get("action", ""),
                    msg.get("context", {}))
                await ws.send(json.dumps({"type": "v16_initiative_proposed",
                                          **result}))

        elif msg_type == "v16_validate_initiative":
            layer = self._v16.get("autonomous_layer")
            if layer:
                result = layer.validate_initiative(msg.get("initiative_id", ""))
                await ws.send(json.dumps({"type": "v16_initiative_validated",
                                          **result}))

        elif msg_type == "v16_execute_initiative":
            layer = self._v16.get("autonomous_layer")
            if layer:
                result = layer.execute_initiative(msg.get("initiative_id", ""))
                await ws.send(json.dumps({"type": "v16_initiative_executed",
                                          **result}))

        elif msg_type == "v16_rollback_initiative":
            layer = self._v16.get("autonomous_layer")
            if layer:
                result = layer.rollback_initiative(msg.get("initiative_id", ""))
                await ws.send(json.dumps({"type": "v16_initiative_rollback",
                                          **result}))

        elif msg_type == "v16_collaborate":
            bus = self._v16.get("collaboration_bus")
            if bus:
                result = bus.collaborate(
                    msg.get("initiator", ""), msg.get("participants", []),
                    msg.get("goal", ""))
                await ws.send(json.dumps({"type": "v16_collab_started",
                                          **result}))

        elif msg_type == "v16_share_observation":
            bus = self._v16.get("collaboration_bus")
            if bus:
                result = bus.share_observation(
                    msg.get("agent", ""), msg.get("observation", {}))
                await ws.send(json.dumps({"type": "v16_observation_shared",
                                          **result}))

        elif msg_type == "v16_emergent_solve":
            eng = self._v16.get("emergent_reasoning")
            if eng:
                result = eng.generate_emergent_solution(msg.get("context", {}))
                await ws.send(json.dumps({"type": "v16_emergent_solution",
                                          **result}))

        elif msg_type == "v16_detect_emergence":
            eng = self._v16.get("emergent_reasoning")
            if eng:
                result = eng.detect_emergence(msg.get("observations", []))
                await ws.send(json.dumps({"type": "v16_emergence_detected",
                                          **result}))

        elif msg_type == "v16_regulate":
            reg = self._v16.get("self_regulation")
            if reg:
                result = reg.regulate_all(msg.get("system_state", {}))
                await ws.send(json.dumps({"type": "v16_regulation_result",
                                          **result}))

        elif msg_type == "v16_supervise":
            gov = self._v16.get("governor")
            if gov:
                result = gov.supervise_initiative(msg.get("initiative", {}))
                await ws.send(json.dumps({"type": "v16_supervise_result",
                                          **result}))

        elif msg_type == "v16_explain":
            exp = self._v16.get("explainability")
            if exp:
                mode = msg.get("mode", "initiative")
                if mode == "emergence":
                    r = exp.explain_emergence(msg.get("emergence", {}))
                elif mode == "governor":
                    r = exp.explain_governor_decision(msg.get("decision", {}))
                elif mode == "regulation":
                    r = exp.explain_regulation(msg.get("regulation", {}))
                elif mode == "collaboration":
                    r = exp.explain_collaboration(msg.get("collab", {}))
                elif mode == "full":
                    r = exp.explain_full_v16(msg.get("session", {}))
                else:
                    r = exp.explain_initiative(msg.get("initiative", {}))
                await ws.send(json.dumps({"type": "v16_explain_result", **r}))

        elif msg_type == "v16_audit_trail":
            audit = self._v16.get("audit_log")
            if audit:
                result = audit.get_audit_trail(
                    msg.get("limit", 50), msg.get("filters", {}))
                await ws.send(json.dumps({"type": "v16_audit_trail",
                                          "entries": result}))

        elif msg_type == "v16_stats":
            stats = {}
            for name, mod in self._v16.items():
                if hasattr(mod, "get_stats"):
                    stats[name] = mod.get_stats()
            await ws.send(json.dumps({"type": "v16_stats", **stats}))

        # ── v17 — Architecture neuro-symbolique ──────────────
        elif msg_type == "v17_hybrid_infer":
            eng = self._v17.get("hybrid_inference")
            if eng:
                result = eng.infer_hybrid(msg.get("query", ""))
                await ws.send(json.dumps({"type": "v17_hybrid_result",
                                          **result}))

        elif msg_type == "v17_ground_prompt":
            grounded = self._v17.get("knowledge_grounded_llm")
            if grounded:
                result = grounded.ground_prompt(
                    msg.get("prompt", ""), msg.get("knowledge", {}))
                await ws.send(json.dumps({"type": "v17_ground_result",
                                          **result}))

        elif msg_type == "v17_ground_output":
            grounded = self._v17.get("knowledge_grounded_llm")
            if grounded:
                result = grounded.ground_llm_output(msg.get("output", ""))
                await ws.send(json.dumps({"type": "v17_ground_output_result",
                                          **result}))

        elif msg_type == "v17_validate_output":
            val = self._v17.get("symbolic_validator")
            if val:
                result = val.validate_llm_output(msg.get("output", ""))
                await ws.send(json.dumps({"type": "v17_validate_result",
                                          **result}))

        elif msg_type == "v17_correct_output":
            val = self._v17.get("symbolic_validator")
            if val:
                result = val.correct_llm_output(msg.get("output", ""))
                await ws.send(json.dumps({"type": "v17_correct_result",
                                          **result}))

        elif msg_type == "v17_extract_entities":
            ext = self._v17.get("semantic_extractor")
            if ext:
                result = ext.extract_entities(msg.get("text", ""))
                await ws.send(json.dumps({"type": "v17_entities_result",
                                          **result}))

        elif msg_type == "v17_extract_relations":
            ext = self._v17.get("semantic_extractor")
            if ext:
                result = ext.extract_relations(msg.get("text", ""))
                await ws.send(json.dumps({"type": "v17_relations_result",
                                          **result}))

        elif msg_type == "v17_augment_kg":
            aug = self._v17.get("knowledge_augmentor")
            if aug:
                result = aug.augment_kg(msg.get("facts", []))
                await ws.send(json.dumps({"type": "v17_augment_result",
                                          **result}))

        elif msg_type == "v17_coherence_check":
            coh = self._v17.get("coherence_engine")
            if coh:
                result = coh.check_neuro_symbolic_consistency()
                await ws.send(json.dumps({"type": "v17_coherence_result",
                                          **result}))

        elif msg_type == "v17_explain":
            exp = self._v17.get("neurosymbolic_explainability")
            if exp:
                mode = msg.get("mode", "hybrid")
                if mode == "symbolic":
                    r = exp.explain_symbolic_part(msg.get("decision", {}))
                elif mode == "neural":
                    r = exp.explain_neural_part(msg.get("decision", {}))
                elif mode == "full":
                    r = exp.explain_full_v17(msg.get("session", {}))
                else:
                    r = exp.explain_hybrid_decision(msg.get("decision", {}))
                await ws.send(json.dumps({"type": "v17_explain_result", **r}))

        elif msg_type == "v17_stats":
            stats = {}
            for name, mod in self._v17.items():
                if hasattr(mod, "get_stats"):
                    stats[name] = mod.get_stats()
            await ws.send(json.dumps({"type": "v17_stats", **stats}))

        # ── v18 — Cognition hiérarchique multi-niveaux ───────
        elif msg_type == "v18_macro_handle":
            eng = self._v18.get("macro_layer")
            if eng:
                result = eng.macro_handle(msg.get("intent", {}))
                await ws.send(json.dumps({"type": "v18_macro_result", **result}))

        elif msg_type == "v18_macro_delegate":
            eng = self._v18.get("macro_layer")
            if eng:
                result = eng.macro_delegate(msg.get("task", {}))
                await ws.send(json.dumps({"type": "v18_delegate_result", **result}))

        elif msg_type == "v18_micro_execute":
            eng = self._v18.get("micro_layer")
            if eng:
                result = eng.micro_execute(msg.get("task", {}))
                await ws.send(json.dumps({"type": "v18_micro_result", **result}))

        elif msg_type == "v18_micro_report":
            eng = self._v18.get("micro_layer")
            if eng:
                result = eng.micro_report()
                await ws.send(json.dumps({"type": "v18_micro_report_result", **result}))

        elif msg_type == "v18_push_layer":
            eng = self._v18.get("layer_stack")
            if eng:
                result = eng.push_to_layer(msg.get("layer", ""), msg.get("data", {}))
                await ws.send(json.dumps({"type": "v18_push_result", **result}))

        elif msg_type == "v18_pull_layer":
            eng = self._v18.get("layer_stack")
            if eng:
                result = eng.pull_from_layer(msg.get("layer", ""))
                await ws.send(json.dumps({"type": "v18_pull_result", **result}))

        elif msg_type == "v18_propagate_up":
            eng = self._v18.get("vertical_flow")
            if eng:
                result = eng.reason_bottom_up(msg.get("data", {}))
                await ws.send(json.dumps({"type": "v18_propagate_up_result", **result}))

        elif msg_type == "v18_propagate_down":
            eng = self._v18.get("vertical_flow")
            if eng:
                result = eng.reason_top_down(msg.get("goal", {}))
                await ws.send(json.dumps({"type": "v18_propagate_down_result", **result}))

        elif msg_type == "v18_merge_flows":
            eng = self._v18.get("vertical_flow")
            if eng:
                result = eng.merge_vertical_flows()
                await ws.send(json.dumps({"type": "v18_merge_result", **result}))

        elif msg_type == "v18_supervise_layer":
            eng = self._v18.get("hierarchical_supervisor")
            if eng:
                result = eng.supervise_layer(msg.get("layer", {}))
                await ws.send(json.dumps({"type": "v18_supervise_layer_result", **result}))

        elif msg_type == "v18_supervise_macro":
            eng = self._v18.get("hierarchical_supervisor")
            if eng:
                result = eng.supervise_macro(msg.get("agent", {}))
                await ws.send(json.dumps({"type": "v18_supervise_macro_result", **result}))

        elif msg_type == "v18_supervise_micro":
            eng = self._v18.get("hierarchical_supervisor")
            if eng:
                result = eng.supervise_micro(msg.get("agent", {}))
                await ws.send(json.dumps({"type": "v18_supervise_micro_result", **result}))

        elif msg_type == "v18_enforce_rules":
            eng = self._v18.get("hierarchical_supervisor")
            if eng:
                result = eng.enforce_hierarchy_rules()
                await ws.send(json.dumps({"type": "v18_enforce_result", **result}))

        elif msg_type == "v18_set_priority":
            eng = self._v18.get("priority_engine")
            if eng:
                result = eng.set_priority(msg.get("entity", {}), msg.get("level", "normal"))
                await ws.send(json.dumps({"type": "v18_priority_result", **result}))

        elif msg_type == "v18_adjust_priority":
            eng = self._v18.get("priority_engine")
            if eng:
                result = eng.adjust_priority(msg.get("entity", {}))
                await ws.send(json.dumps({"type": "v18_adjust_result", **result}))

        elif msg_type == "v18_priority_map":
            eng = self._v18.get("priority_engine")
            if eng:
                result = eng.compute_priority_map()
                await ws.send(json.dumps({"type": "v18_priority_map_result", **result}))

        elif msg_type == "v18_check_consistency":
            eng = self._v18.get("layered_consistency")
            if eng:
                result = eng.check_layer_consistency()
                await ws.send(json.dumps({"type": "v18_consistency_result", **result}))

        elif msg_type == "v18_enforce_consistency":
            eng = self._v18.get("layered_consistency")
            if eng:
                result = eng.enforce_layer_consistency()
                await ws.send(json.dumps({"type": "v18_enforce_consistency_result", **result}))

        elif msg_type == "v18_cross_level":
            eng = self._v18.get("layered_consistency")
            if eng:
                result = eng.check_cross_level()
                await ws.send(json.dumps({"type": "v18_cross_level_result", **result}))

        elif msg_type == "v18_explain_layer":
            eng = self._v18.get("layered_explainability")
            if eng:
                result = eng.explain_layer(msg.get("layer", {}))
                await ws.send(json.dumps({"type": "v18_explain_layer_result", **result}))

        elif msg_type == "v18_explain_macro":
            eng = self._v18.get("layered_explainability")
            if eng:
                result = eng.explain_macro(msg.get("agent", {}))
                await ws.send(json.dumps({"type": "v18_explain_macro_result", **result}))

        elif msg_type == "v18_explain_micro":
            eng = self._v18.get("layered_explainability")
            if eng:
                result = eng.explain_micro(msg.get("agent", {}))
                await ws.send(json.dumps({"type": "v18_explain_micro_result", **result}))

        elif msg_type == "v18_explain_flow":
            eng = self._v18.get("layered_explainability")
            if eng:
                result = eng.explain_vertical_flow()
                await ws.send(json.dumps({"type": "v18_explain_flow_result", **result}))

        elif msg_type == "v18_explain_decision":
            eng = self._v18.get("layered_explainability")
            if eng:
                result = eng.explain_decision(msg.get("decision", {}))
                await ws.send(json.dumps({"type": "v18_explain_decision_result", **result}))

        elif msg_type == "v18_stats":
            stats = {}
            for name, mod in self._v18.items():
                if hasattr(mod, "get_stats"):
                    stats[name] = mod.get_stats()
            await ws.send(json.dumps({"type": "v18_stats", **stats}))

        # ── v19 — Optimisation cognitive ─────────────────────
        elif msg_type == "v19_analyze_system":
            eng = self._v19.get("meta_optimizer")
            if eng:
                result = eng.analyze_system()
                await ws.send(json.dumps({"type": "v19_analyze_system_result", **result}))

        elif msg_type == "v19_detect_inefficiencies":
            eng = self._v19.get("meta_optimizer")
            if eng:
                result = eng.detect_inefficiencies()
                await ws.send(json.dumps({"type": "v19_detect_inefficiencies_result", **result}))

        elif msg_type == "v19_propose_optimizations":
            eng = self._v19.get("meta_optimizer")
            if eng:
                result = eng.propose_optimizations()
                await ws.send(json.dumps({"type": "v19_propose_optimizations_result", **result}))

        elif msg_type == "v19_update_heuristics":
            eng = self._v19.get("adaptive_heuristics")
            if eng:
                result = eng.update_heuristics()
                await ws.send(json.dumps({"type": "v19_update_heuristics_result", **result}))

        elif msg_type == "v19_select_strategy":
            eng = self._v19.get("adaptive_heuristics")
            if eng:
                result = eng.select_best_strategy(msg.get("task", {}))
                await ws.send(json.dumps({"type": "v19_select_strategy_result", **result}))

        elif msg_type == "v19_adapt_context":
            eng = self._v19.get("adaptive_heuristics")
            if eng:
                result = eng.adapt_to_context(msg.get("context", {}))
                await ws.send(json.dumps({"type": "v19_adapt_context_result", **result}))

        elif msg_type == "v19_optimize_pipeline":
            eng = self._v19.get("pipeline_optimizer")
            if eng:
                result = eng.optimize_pipeline(msg.get("pipeline", {}))
                await ws.send(json.dumps({"type": "v19_optimize_pipeline_result", **result}))

        elif msg_type == "v19_reorder_steps":
            eng = self._v19.get("pipeline_optimizer")
            if eng:
                result = eng.reorder_steps(msg.get("steps", {}))
                await ws.send(json.dumps({"type": "v19_reorder_steps_result", **result}))

        elif msg_type == "v19_optimize_flow":
            eng = self._v19.get("pipeline_optimizer")
            if eng:
                result = eng.optimize_flow(msg.get("flow", {}))
                await ws.send(json.dumps({"type": "v19_optimize_flow_result", **result}))

        elif msg_type == "v19_remove_redundancies":
            eng = self._v19.get("load_reducer")
            if eng:
                result = eng.remove_redundancies()
                await ws.send(json.dumps({"type": "v19_remove_redundancies_result", **result}))

        elif msg_type == "v19_reduce_llm_calls":
            eng = self._v19.get("load_reducer")
            if eng:
                result = eng.reduce_llm_calls()
                await ws.send(json.dumps({"type": "v19_reduce_llm_calls_result", **result}))

        elif msg_type == "v19_simplify_pipeline":
            eng = self._v19.get("load_reducer")
            if eng:
                result = eng.simplify_pipeline()
                await ws.send(json.dumps({"type": "v19_simplify_pipeline_result", **result}))

        elif msg_type == "v19_optimize_for":
            eng = self._v19.get("multi_objective")
            if eng:
                result = eng.optimize_for(msg.get("criteria", {}))
                await ws.send(json.dumps({"type": "v19_optimize_for_result", **result}))

        elif msg_type == "v19_compute_tradeoffs":
            eng = self._v19.get("multi_objective")
            if eng:
                result = eng.compute_tradeoffs(msg.get("criteria", {}))
                await ws.send(json.dumps({"type": "v19_compute_tradeoffs_result", **result}))

        elif msg_type == "v19_select_optimal":
            eng = self._v19.get("multi_objective")
            if eng:
                result = eng.select_optimal_solution()
                await ws.send(json.dumps({"type": "v19_select_optimal_result", **result}))

        elif msg_type == "v19_profile_system":
            eng = self._v19.get("profiling")
            if eng:
                result = eng.profile_system()
                await ws.send(json.dumps({"type": "v19_profile_system_result", **result}))

        elif msg_type == "v19_profile_agent":
            eng = self._v19.get("profiling")
            if eng:
                result = eng.profile_agent(msg.get("agent", {}))
                await ws.send(json.dumps({"type": "v19_profile_agent_result", **result}))

        elif msg_type == "v19_profile_layer":
            eng = self._v19.get("profiling")
            if eng:
                result = eng.profile_layer(msg.get("layer", {}))
                await ws.send(json.dumps({"type": "v19_profile_layer_result", **result}))

        elif msg_type == "v19_optimize_plan":
            eng = self._v19.get("plan_optimizer")
            if eng:
                result = eng.optimize_plan(msg.get("plan", {}))
                await ws.send(json.dumps({"type": "v19_optimize_plan_result", **result}))

        elif msg_type == "v19_simplify_plan":
            eng = self._v19.get("plan_optimizer")
            if eng:
                result = eng.simplify_plan(msg.get("plan", {}))
                await ws.send(json.dumps({"type": "v19_simplify_plan_result", **result}))

        elif msg_type == "v19_alternative_plans":
            eng = self._v19.get("plan_optimizer")
            if eng:
                result = eng.generate_alternative_plans(msg.get("plan", {}))
                await ws.send(json.dumps({"type": "v19_alternative_plans_result", **result}))

        elif msg_type == "v19_optimize_simulation":
            eng = self._v19.get("simulation_optimizer")
            if eng:
                result = eng.optimize_simulation(msg.get("sim", {}))
                await ws.send(json.dumps({"type": "v19_optimize_simulation_result", **result}))

        elif msg_type == "v19_prune_tree":
            eng = self._v19.get("simulation_optimizer")
            if eng:
                result = eng.prune_simulation_tree(msg.get("tree", {}))
                await ws.send(json.dumps({"type": "v19_prune_tree_result", **result}))

        elif msg_type == "v19_select_scenarios":
            eng = self._v19.get("simulation_optimizer")
            if eng:
                result = eng.select_relevant_scenarios()
                await ws.send(json.dumps({"type": "v19_select_scenarios_result", **result}))

        elif msg_type == "v19_optimize_inference":
            eng = self._v19.get("inference_optimizer")
            if eng:
                result = eng.optimize_inference(msg.get("query", {}))
                await ws.send(json.dumps({"type": "v19_optimize_inference_result", **result}))

        elif msg_type == "v19_simplify_rules":
            eng = self._v19.get("inference_optimizer")
            if eng:
                result = eng.simplify_rules()
                await ws.send(json.dumps({"type": "v19_simplify_rules_result", **result}))

        elif msg_type == "v19_compress_graph":
            eng = self._v19.get("inference_optimizer")
            if eng:
                result = eng.compress_knowledge_graph()
                await ws.send(json.dumps({"type": "v19_compress_graph_result", **result}))

        elif msg_type == "v19_explain_optimization":
            eng = self._v19.get("optimization_explainability")
            if eng:
                result = eng.explain_optimization()
                await ws.send(json.dumps({"type": "v19_explain_optimization_result", **result}))

        elif msg_type == "v19_explain_tradeoffs":
            eng = self._v19.get("optimization_explainability")
            if eng:
                result = eng.explain_tradeoffs()
                await ws.send(json.dumps({"type": "v19_explain_tradeoffs_result", **result}))

        elif msg_type == "v19_explain_gain":
            eng = self._v19.get("optimization_explainability")
            if eng:
                result = eng.explain_performance_gain()
                await ws.send(json.dumps({"type": "v19_explain_gain_result", **result}))

        elif msg_type == "v19_stats":
            stats = {}
            for name, mod in self._v19.items():
                if hasattr(mod, "get_stats"):
                    stats[name] = mod.get_stats()
            await ws.send(json.dumps({"type": "v19_stats", **stats}))

        # ── v20 — Architecture modulaire ultra-scalable ──────
        elif msg_type == "v20_mcu_init":
            mcu = self._v20.get("mcu")
            if mcu:
                result = mcu.mcu_init(name=data.get("name", "default"),
                                      version=data.get("version", "1.0.0"),
                                      capabilities=data.get("capabilities"),
                                      config=data.get("config"))
                await ws.send(json.dumps({"type": "v20_mcu_init_result", **result}))

        elif msg_type == "v20_mcu_execute":
            mcu = self._v20.get("mcu")
            if mcu:
                result = mcu.mcu_execute(data)
                await ws.send(json.dumps({"type": "v20_mcu_execute_result", **result}))

        elif msg_type == "v20_mcu_report":
            mcu = self._v20.get("mcu")
            if mcu:
                result = mcu.mcu_report()
                await ws.send(json.dumps({"type": "v20_mcu_report_result", **result}))

        elif msg_type == "v20_mcu_shutdown":
            mcu = self._v20.get("mcu")
            if mcu:
                result = mcu.mcu_shutdown(data.get("unit_id", ""))
                await ws.send(json.dumps({"type": "v20_mcu_shutdown_result", **result}))

        elif msg_type == "v20_register_agent":
            pnp = self._v20.get("plug_and_play")
            if pnp:
                result = pnp.register_agent(data)
                await ws.send(json.dumps({"type": "v20_register_agent_result", **result}))

        elif msg_type == "v20_unregister_agent":
            pnp = self._v20.get("plug_and_play")
            if pnp:
                result = pnp.unregister_agent(data)
                await ws.send(json.dumps({"type": "v20_unregister_agent_result", **result}))

        elif msg_type == "v20_replace_agent":
            pnp = self._v20.get("plug_and_play")
            if pnp:
                result = pnp.replace_agent(data.get("old", {}), data.get("new", {}))
                await ws.send(json.dumps({"type": "v20_replace_agent_result", **result}))

        elif msg_type == "v20_orchestrate":
            orch = self._v20.get("distributed_orchestrator")
            if orch:
                result = orch.orchestrate(data)
                await ws.send(json.dumps({"type": "v20_orchestrate_result", **result}))

        elif msg_type == "v20_distribute":
            orch = self._v20.get("distributed_orchestrator")
            if orch:
                result = orch.distribute(data)
                await ws.send(json.dumps({"type": "v20_distribute_result", **result}))

        elif msg_type == "v20_collect":
            orch = self._v20.get("distributed_orchestrator")
            if orch:
                result = orch.collect(data)
                await ws.send(json.dumps({"type": "v20_collect_result", **result}))

        elif msg_type == "v20_fabric_route":
            fab = self._v20.get("scalable_fabric")
            if fab:
                result = fab.fabric_route(data)
                await ws.send(json.dumps({"type": "v20_fabric_route_result", **result}))

        elif msg_type == "v20_fabric_register":
            fab = self._v20.get("scalable_fabric")
            if fab:
                result = fab.fabric_register(data)
                await ws.send(json.dumps({"type": "v20_fabric_register_result", **result}))

        elif msg_type == "v20_fabric_scale":
            fab = self._v20.get("scalable_fabric")
            if fab:
                result = fab.fabric_scale(data)
                await ws.send(json.dumps({"type": "v20_fabric_scale_result", **result}))

        elif msg_type == "v20_partition_cognition":
            pe = self._v20.get("partitioning")
            if pe:
                result = pe.partition_cognition(data)
                await ws.send(json.dumps({"type": "v20_partition_cognition_result", **result}))

        elif msg_type == "v20_reassign_partition":
            pe = self._v20.get("partitioning")
            if pe:
                result = pe.reassign_partition(data)
                await ws.send(json.dumps({"type": "v20_reassign_partition_result", **result}))

        elif msg_type == "v20_merge_partitions":
            pe = self._v20.get("partitioning")
            if pe:
                result = pe.merge_partitions(data.get("partition_ids"))
                await ws.send(json.dumps({"type": "v20_merge_partitions_result", **result}))

        elif msg_type == "v20_install_module":
            lm = self._v20.get("lifecycle")
            if lm:
                result = lm.install_module(data)
                await ws.send(json.dumps({"type": "v20_install_module_result", **result}))

        elif msg_type == "v20_update_module":
            lm = self._v20.get("lifecycle")
            if lm:
                result = lm.update_module(data)
                await ws.send(json.dumps({"type": "v20_update_module_result", **result}))

        elif msg_type == "v20_remove_module":
            lm = self._v20.get("lifecycle")
            if lm:
                result = lm.remove_module(data)
                await ws.send(json.dumps({"type": "v20_remove_module_result", **result}))

        elif msg_type == "v20_hotswap":
            hs = self._v20.get("hot_swap")
            if hs:
                result = hs.hotswap(data.get("old", {}), data.get("new", {}))
                await ws.send(json.dumps({"type": "v20_hotswap_result", **result}))

        elif msg_type == "v20_rollback":
            hs = self._v20.get("hot_swap")
            if hs:
                result = hs.rollback(data)
                await ws.send(json.dumps({"type": "v20_rollback_result", **result}))

        elif msg_type == "v20_validate_swap":
            hs = self._v20.get("hot_swap")
            if hs:
                result = hs.validate_swap(data.get("old", {}), data.get("new", {}))
                await ws.send(json.dumps({"type": "v20_validate_swap_result", **result}))

        elif msg_type == "v20_check_api":
            cc = self._v20.get("compatibility")
            if cc:
                result = cc.check_api(data)
                await ws.send(json.dumps({"type": "v20_check_api_result", **result}))

        elif msg_type == "v20_check_version":
            cc = self._v20.get("compatibility")
            if cc:
                result = cc.check_version(data)
                await ws.send(json.dumps({"type": "v20_check_version_result", **result}))

        elif msg_type == "v20_check_dependencies":
            cc = self._v20.get("compatibility")
            if cc:
                result = cc.check_dependencies(data)
                await ws.send(json.dumps({"type": "v20_check_dependencies_result", **result}))

        elif msg_type == "v20_explain_module":
            me = self._v20.get("modular_explainability")
            if me:
                result = me.explain_module(data)
                await ws.send(json.dumps({"type": "v20_explain_module_result", **result}))

        elif msg_type == "v20_explain_swap":
            me = self._v20.get("modular_explainability")
            if me:
                result = me.explain_swap(data.get("old", {}), data.get("new", {}))
                await ws.send(json.dumps({"type": "v20_explain_swap_result", **result}))

        elif msg_type == "v20_explain_partitioning":
            me = self._v20.get("modular_explainability")
            if me:
                result = me.explain_partitioning()
                await ws.send(json.dumps({"type": "v20_explain_partitioning_result", **result}))

        elif msg_type == "v20_stats":
            stats = {}
            for name, mod in self._v20.items():
                if hasattr(mod, "get_stats"):
                    stats[name] = mod.get_stats()
            await ws.send(json.dumps({"type": "v20_stats", **stats}))

        # ── v21 handlers ─────────────────────────────────
        elif msg_type == "v21_evaluate_rules":
            eng = self._v21.get("rule_engine")
            if eng:
                ctx = data.get("context", {})
                result = eng.evaluate_rules(ctx)
                await ws.send(json.dumps({"type": "v21_evaluate_rules_result", **result}))

        elif msg_type == "v21_causal_chain":
            eng = self._v21.get("causal_engine")
            if eng:
                query = data.get("query", {})
                result = eng.infer_causal_chain(query)
                await ws.send(json.dumps({"type": "v21_causal_chain_result", **result}))

        elif msg_type == "v21_deduce":
            eng = self._v21.get("deductive")
            if eng:
                query = data.get("query", {})
                result = eng.deduce(query)
                await ws.send(json.dumps({"type": "v21_deduce_result", **result}))

        elif msg_type == "v21_induce":
            eng = self._v21.get("inductive")
            if eng:
                patterns = data.get("patterns", {})
                result = eng.induce(patterns)
                await ws.send(json.dumps({"type": "v21_induce_result", **result}))

        elif msg_type == "v21_abduct":
            eng = self._v21.get("abductive")
            if eng:
                query = data.get("query", {})
                result = eng.abduct(query)
                await ws.send(json.dumps({"type": "v21_abduct_result", **result}))

        elif msg_type == "v21_solve_constraints":
            eng = self._v21.get("constraint_solver")
            if eng:
                cs = data.get("constraint_set", {})
                result = eng.solve_constraints(cs)
                await ws.send(json.dumps({"type": "v21_solve_constraints_result", **result}))

        elif msg_type == "v21_check_coherence":
            eng = self._v21.get("coherence")
            if eng:
                result = eng.check_logical_consistency()
                await ws.send(json.dumps({"type": "v21_check_coherence_result", **result}))

        elif msg_type == "v21_kg_add":
            eng = self._v21.get("kg_v2")
            if eng:
                node = data.get("node", {})
                result = eng.kg_add(node)
                await ws.send(json.dumps({"type": "v21_kg_add_result", **result}))

        elif msg_type == "v21_kg_query":
            eng = self._v21.get("kg_v2")
            if eng:
                pattern = data.get("pattern", {})
                result = eng.kg_query(pattern)
                await ws.send(json.dumps({"type": "v21_kg_query_result", **result}))

        elif msg_type == "v21_explain_symbolic":
            eng = self._v21.get("symbolic_explain")
            if eng:
                what = data.get("what", "deduction")
                if what == "deduction":
                    result = eng.explain_deduction()
                elif what == "induction":
                    result = eng.explain_induction()
                elif what == "abduction":
                    result = eng.explain_abduction()
                elif what == "causal":
                    result = eng.explain_causal_chain()
                else:
                    result = eng.explain_deduction()
                await ws.send(json.dumps({"type": "v21_explain_symbolic_result", **result}))

        elif msg_type == "v21_stats":
            stats = {}
            for name, mod in self._v21.items():
                if hasattr(mod, "get_stats"):
                    stats[name] = mod.get_stats()
            await ws.send(json.dumps({"type": "v21_stats", **stats}))

        # ── v22 — Planification stratégique ─────────────────
        elif msg_type == "v22_plan":
            planner = self._v22.get("strategic_planner")
            if planner:
                intent = msg.get("intent", {})
                result = planner.plan(intent)
                await ws.send(json.dumps({"type": "v22_plan_result", **result}))

        elif msg_type == "v22_htn_expand":
            eng = self._v22.get("htn_plus")
            if eng:
                task = msg.get("task", {})
                result = eng.htn_expand(task)
                await ws.send(json.dumps({"type": "v22_htn_expand_result", **result}))

        elif msg_type == "v22_multi_objective":
            eng = self._v22.get("multi_objective")
            if eng:
                intent = msg.get("intent", {})
                objectives = msg.get("objectives", [])
                result = eng.plan_multi_objectives(intent, objectives)
                await ws.send(json.dumps({"type": "v22_multi_objective_result", **result}))

        elif msg_type == "v22_apply_constraints":
            eng = self._v22.get("constraint_aware")
            if eng:
                plan = msg.get("plan", {})
                result = eng.apply_constraints(plan)
                await ws.send(json.dumps({"type": "v22_constraints_result", **result}))

        elif msg_type == "v22_scenarios":
            eng = self._v22.get("scenario_planner")
            if eng:
                intent = msg.get("intent", {})
                result = eng.generate_scenarios(intent)
                await ws.send(json.dumps({"type": "v22_scenarios_result", **result}))

        elif msg_type == "v22_arbitrate":
            eng = self._v22.get("arbitration")
            if eng:
                plans = msg.get("plans", [])
                result = eng.arbitrate(plans)
                await ws.send(json.dumps({"type": "v22_arbitrate_result", **result}))

        elif msg_type == "v22_temporal":
            eng = self._v22.get("temporal")
            if eng:
                plan = msg.get("plan", {})
                result = eng.analyze_temporal_constraints(plan)
                await ws.send(json.dumps({"type": "v22_temporal_result", **result}))

        elif msg_type == "v22_coherence":
            eng = self._v22.get("coherence")
            if eng:
                plan = msg.get("plan", {})
                result = eng.check_plan_coherence(plan)
                await ws.send(json.dumps({"type": "v22_coherence_result", **result}))

        elif msg_type == "v22_explain":
            eng = self._v22.get("explainability")
            if eng:
                what = msg.get("what", "plan")
                if what == "scenario":
                    scenario = msg.get("scenario", {})
                    result = eng.explain_scenario(scenario)
                elif what == "decision":
                    result = eng.explain_decision()
                else:
                    plan = msg.get("plan", {})
                    result = eng.explain_plan(plan)
                await ws.send(json.dumps({"type": "v22_explain_result", **result}))

        elif msg_type == "v22_stats":
            stats = {}
            for name, mod in self._v22.items():
                if hasattr(mod, "get_stats"):
                    stats[name] = mod.get_stats()
            await ws.send(json.dumps({"type": "v22_stats", **stats}))

        # ── v23 contextual simulation ──────────────────────
        elif msg_type == "v23_sandbox_init":
            eng = self._v23.get("sandbox")
            if eng:
                ctx = msg.get("context", {})
                result = eng.sandbox_init(ctx)
                await ws.send(json.dumps({"type": "v23_sandbox_init_result", **result}))

        elif msg_type == "v23_sandbox_run":
            eng = self._v23.get("sandbox")
            if eng:
                plan = msg.get("plan", {})
                result = eng.sandbox_run(plan)
                await ws.send(json.dumps({"type": "v23_sandbox_run_result", **result}))

        elif msg_type == "v23_generate_scenarios":
            eng = self._v23.get("multi_scenario")
            if eng:
                plan = msg.get("plan", {})
                result = eng.generate_scenarios(plan)
                await ws.send(json.dumps({"type": "v23_generate_scenarios_result", **result}))

        elif msg_type == "v23_simulate_scenarios":
            eng = self._v23.get("multi_scenario")
            if eng:
                scenarios = msg.get("scenarios", [])
                result = eng.simulate_scenarios(scenarios)
                await ws.send(json.dumps({"type": "v23_simulate_scenarios_result", **result}))

        elif msg_type == "v23_compare_scenarios":
            eng = self._v23.get("multi_scenario")
            if eng:
                scenarios = msg.get("scenarios", [])
                result = eng.compare_scenarios(scenarios)
                await ws.send(json.dumps({"type": "v23_compare_scenarios_result", **result}))

        elif msg_type == "v23_predict_outcomes":
            eng = self._v23.get("predictive")
            if eng:
                plan = msg.get("plan", {})
                result = eng.predict_outcomes(plan)
                await ws.send(json.dumps({"type": "v23_predict_outcomes_result", **result}))

        elif msg_type == "v23_predict_event":
            eng = self._v23.get("predictive")
            if eng:
                event = msg.get("event", {})
                result = eng.predict_event(event)
                await ws.send(json.dumps({"type": "v23_predict_event_result", **result}))

        elif msg_type == "v23_analyze_outcomes":
            eng = self._v23.get("outcome_analysis")
            if eng:
                results_data = msg.get("results", {})
                result = eng.analyze_outcomes(results_data)
                await ws.send(json.dumps({"type": "v23_analyze_outcomes_result", **result}))

        elif msg_type == "v23_classify_risks":
            eng = self._v23.get("outcome_analysis")
            if eng:
                results_data = msg.get("results", {})
                result = eng.classify_risks(results_data)
                await ws.send(json.dumps({"type": "v23_classify_risks_result", **result}))

        elif msg_type == "v23_temporal_flow":
            eng = self._v23.get("temporal_sim")
            if eng:
                plan = msg.get("plan", {})
                result = eng.simulate_temporal_flow(plan)
                await ws.send(json.dumps({"type": "v23_temporal_flow_result", **result}))

        elif msg_type == "v23_check_coherence":
            eng = self._v23.get("coherence")
            if eng:
                sim = msg.get("simulation", {})
                result = eng.check_simulation_coherence(sim)
                await ws.send(json.dumps({"type": "v23_check_coherence_result", **result}))

        elif msg_type == "v23_validate_simulation":
            eng = self._v23.get("governance")
            if eng:
                sim = msg.get("simulation", {})
                result = eng.validate_simulation(sim)
                await ws.send(json.dumps({"type": "v23_validate_simulation_result", **result}))

        elif msg_type == "v23_explain_simulation":
            eng = self._v23.get("explainability")
            if eng:
                sim = msg.get("simulation", {})
                result = eng.explain_simulation(sim)
                await ws.send(json.dumps({"type": "v23_explain_simulation_result", **result}))

        elif msg_type == "v23_explain_outcome":
            eng = self._v23.get("explainability")
            if eng:
                outcome = msg.get("outcome", {})
                result = eng.explain_outcome(outcome)
                await ws.send(json.dumps({"type": "v23_explain_outcome_result", **result}))

        elif msg_type == "v23_stats":
            stats = {}
            for name, mod in self._v23.items():
                if hasattr(mod, "get_stats"):
                    stats[name] = mod.get_stats()
            await ws.send(json.dumps({"type": "v23_stats", **stats}))

        # ── v24 cognitive observability ─────────────────────────
        elif msg_type == "v24_telemetry_collect":
            mod = self._v24.get("telemetry")
            if mod:
                result = mod.telemetry_collect(data.get("event", {}))
                await ws.send(json.dumps({"type": "v24_telemetry_collect_result", **result}))
        elif msg_type == "v24_telemetry_snapshot":
            mod = self._v24.get("telemetry")
            if mod:
                result = mod.telemetry_snapshot()
                await ws.send(json.dumps({"type": "v24_telemetry_snapshot_result", **result}))
        elif msg_type == "v24_trace_start":
            mod = self._v24.get("tracing")
            if mod:
                result = mod.trace_start(data.get("operation", {}))
                await ws.send(json.dumps({"type": "v24_trace_start_result", **result}))
        elif msg_type == "v24_trace_end":
            mod = self._v24.get("tracing")
            if mod:
                result = mod.trace_end(data.get("operation", {}))
                await ws.send(json.dumps({"type": "v24_trace_end_result", **result}))
        elif msg_type == "v24_metrics_update":
            mod = self._v24.get("metrics")
            if mod:
                result = mod.metrics_update(data.get("metric", {}))
                await ws.send(json.dumps({"type": "v24_metrics_update_result", **result}))
        elif msg_type == "v24_metrics_compute":
            mod = self._v24.get("metrics")
            if mod:
                result = mod.metrics_compute()
                await ws.send(json.dumps({"type": "v24_metrics_compute_result", **result}))
        elif msg_type == "v24_analyze_performance":
            mod = self._v24.get("performance")
            if mod:
                result = mod.analyze_performance()
                await ws.send(json.dumps({"type": "v24_analyze_performance_result", **result}))
        elif msg_type == "v24_detect_bottlenecks":
            mod = self._v24.get("performance")
            if mod:
                result = mod.detect_bottlenecks()
                await ws.send(json.dumps({"type": "v24_detect_bottlenecks_result", **result}))
        elif msg_type == "v24_detect_anomaly":
            mod = self._v24.get("anomaly")
            if mod:
                result = mod.detect_anomaly(data.get("event", {}))
                await ws.send(json.dumps({"type": "v24_detect_anomaly_result", **result}))
        elif msg_type == "v24_aggregate_all":
            mod = self._v24.get("aggregator")
            if mod:
                result = mod.aggregate_all()
                await ws.send(json.dumps({"type": "v24_aggregate_all_result", **result}))
        elif msg_type == "v24_dashboard_generate":
            mod = self._v24.get("dashboard")
            if mod:
                result = mod.dashboard_generate()
                await ws.send(json.dumps({"type": "v24_dashboard_generate_result", **result}))
        elif msg_type == "v24_dashboard_summary":
            mod = self._v24.get("dashboard")
            if mod:
                result = mod.dashboard_summary()
                await ws.send(json.dumps({"type": "v24_dashboard_summary_result", **result}))
        elif msg_type == "v24_explain_metric":
            mod = self._v24.get("explainability")
            if mod:
                result = mod.explain_metric(data.get("metric", ""))
                await ws.send(json.dumps({"type": "v24_explain_metric_result", **result}))
        elif msg_type == "v24_explain_anomaly":
            mod = self._v24.get("explainability")
            if mod:
                result = mod.explain_anomaly(data.get("anomaly", ""))
                await ws.send(json.dumps({"type": "v24_explain_anomaly_result", **result}))
        elif msg_type == "v24_explain_performance":
            mod = self._v24.get("explainability")
            if mod:
                result = mod.explain_performance()
                await ws.send(json.dumps({"type": "v24_explain_performance_result", **result}))
        elif msg_type == "v24_stats":
            stats = {}
            for name, mod in self._v24.items():
                if hasattr(mod, "get_stats"):
                    stats[name] = mod.get_stats()
            await ws.send(json.dumps({"type": "v24_stats", **stats}))

        # ── v25 cognitive governance ──────────────────────────
        elif msg_type == "v25_grant_permission":
            mod = self._v25.get("permissions")
            if mod:
                result = mod.grant_permission(data.get("entity", ""), data.get("action", ""))
                await ws.send(json.dumps({"type": "v25_grant_permission_result", **result}))
        elif msg_type == "v25_revoke_permission":
            mod = self._v25.get("permissions")
            if mod:
                result = mod.revoke_permission(data.get("entity", ""), data.get("action", ""))
                await ws.send(json.dumps({"type": "v25_revoke_permission_result", **result}))
        elif msg_type == "v25_check_permission":
            mod = self._v25.get("permissions")
            if mod:
                result = mod.check_permission(data.get("entity", ""), data.get("action", ""))
                await ws.send(json.dumps({"type": "v25_check_permission_result", **result}))
        elif msg_type == "v25_validate_action":
            mod = self._v25.get("validation")
            if mod:
                result = mod.validate_action(data.get("action", {}))
                await ws.send(json.dumps({"type": "v25_validate_action_result", **result}))
        elif msg_type == "v25_validate_decision":
            mod = self._v25.get("validation")
            if mod:
                result = mod.validate_decision(data.get("decision", {}))
                await ws.send(json.dumps({"type": "v25_validate_decision_result", **result}))
        elif msg_type == "v25_audit_log":
            mod = self._v25.get("audit")
            if mod:
                result = mod.audit_log(data.get("event", {}))
                await ws.send(json.dumps({"type": "v25_audit_log_result", **result}))
        elif msg_type == "v25_audit_export":
            mod = self._v25.get("audit")
            if mod:
                result = mod.audit_export()
                await ws.send(json.dumps({"type": "v25_audit_export_result", **result}))
        elif msg_type == "v25_audit_query":
            mod = self._v25.get("audit")
            if mod:
                result = mod.audit_query(data.get("criteria", {}))
                await ws.send(json.dumps({"type": "v25_audit_query_result", **result}))
        elif msg_type == "v25_check_compliance":
            mod = self._v25.get("compliance")
            if mod:
                result = mod.check_compliance(data.get("action", {}))
                await ws.send(json.dumps({"type": "v25_check_compliance_result", **result}))
        elif msg_type == "v25_enforce_compliance":
            mod = self._v25.get("compliance")
            if mod:
                result = mod.enforce_compliance(data.get("action", {}))
                await ws.send(json.dumps({"type": "v25_enforce_compliance_result", **result}))
        elif msg_type == "v25_load_policies":
            mod = self._v25.get("policies")
            if mod:
                result = mod.load_policies(data.get("policies", []))
                await ws.send(json.dumps({"type": "v25_load_policies_result", **result}))
        elif msg_type == "v25_apply_policy":
            mod = self._v25.get("policies")
            if mod:
                result = mod.apply_policy(data.get("policy", ""))
                await ws.send(json.dumps({"type": "v25_apply_policy_result", **result}))
        elif msg_type == "v25_control_action":
            mod = self._v25.get("action_control")
            if mod:
                result = mod.control_action(data.get("action", {}))
                await ws.send(json.dumps({"type": "v25_control_action_result", **result}))
        elif msg_type == "v25_block_action":
            mod = self._v25.get("action_control")
            if mod:
                result = mod.block_action(data.get("action", {}))
                await ws.send(json.dumps({"type": "v25_block_action_result", **result}))
        elif msg_type == "v25_validate_final_decision":
            mod = self._v25.get("decision_validation")
            if mod:
                result = mod.validate_decision(data.get("decision", {}))
                await ws.send(json.dumps({"type": "v25_validate_final_decision_result", **result}))
        elif msg_type == "v25_reject_decision":
            mod = self._v25.get("decision_validation")
            if mod:
                result = mod.reject_decision(data.get("decision", {}))
                await ws.send(json.dumps({"type": "v25_reject_decision_result", **result}))
        elif msg_type == "v25_supervise_governance":
            mod = self._v25.get("supervisor")
            if mod:
                result = mod.supervise_governance()
                await ws.send(json.dumps({"type": "v25_supervise_governance_result", **result}))
        elif msg_type == "v25_enforce_governance_rules":
            mod = self._v25.get("supervisor")
            if mod:
                result = mod.enforce_governance_rules()
                await ws.send(json.dumps({"type": "v25_enforce_governance_rules_result", **result}))
        elif msg_type == "v25_governance_health":
            mod = self._v25.get("supervisor")
            if mod:
                result = mod.governance_health_check()
                await ws.send(json.dumps({"type": "v25_governance_health_result", **result}))
        elif msg_type == "v25_explain_permission":
            mod = self._v25.get("explainability")
            if mod:
                result = mod.explain_permission(data.get("entity", ""), data.get("action", ""))
                await ws.send(json.dumps({"type": "v25_explain_permission_result", **result}))
        elif msg_type == "v25_explain_governance_decision":
            mod = self._v25.get("explainability")
            if mod:
                result = mod.explain_governance_decision()
                await ws.send(json.dumps({"type": "v25_explain_governance_decision_result", **result}))
        elif msg_type == "v25_explain_block_reason":
            mod = self._v25.get("explainability")
            if mod:
                result = mod.explain_block_reason()
                await ws.send(json.dumps({"type": "v25_explain_block_reason_result", **result}))
        elif msg_type == "v25_stats":
            stats = {}
            for name, mod in self._v25.items():
                if hasattr(mod, "get_stats"):
                    stats[name] = mod.get_stats()
            await ws.send(json.dumps({"type": "v25_stats", **stats}))

    async def broadcast(self, data: dict) -> None:
        if not self._clients:
            return
        payload = _safe_json_dumps(data)
        if not payload:
            logger.warning("broadcast: payload non-serialisable, abandon")
            return
        results = await asyncio.gather(
            *(c.send(payload) for c in self._clients),
            return_exceptions=True,
        )
        # Audit des envois en échec sans casser la boucle.
        for client, res in zip(list(self._clients), results):
            if isinstance(res, Exception):
                logger.debug("broadcast: client perdu (%s) — retiré", type(res).__name__)
                self._clients.discard(client)

    async def push_state(self, state: str, volume: float = 0.0, text: str = "") -> None:
        # Validation soft : on accepte toutes les valeurs mais on logge celles
        # qui ne font pas partie de l'ensemble connu (utile pour repérer un
        # service amont qui enverrait un état fantaisiste).
        if state not in self._KNOWN_STATES:
            logger.warning("[gui][state] valeur inconnue: %r", state)
        old = self._state
        self._state = state
        if volume:
            self._volume = volume
        if text:
            self._text = text
        if old != state:
            logger.info("[gui][state] %s -> %s", old, state)
        await self.broadcast({"state": state, "volume": self._volume, "text": text})


# ---------------------------------------------------------------------------
# Pipeline Manager v8.2
# ---------------------------------------------------------------------------

class PipelineManager:
    """Coordonne tous les modules ultra-low latency v8.2.

    Regroupe : warmup, fused pipeline, TTS prédictif, cache,
    CPU/GPU orchestrator, profiler, résilience, intégration v9.
    """

    def __init__(self) -> None:
        self.warmup = LLMWarmup()
        self.pipeline = FusedPipeline()
        self.tts_pred = TTSPredictive()
        self.cache = ContextCache()
        self.cpu_gpu = CPUGPUOrchestrator()
        self.profiler = PipelineProfiler()
        self.resilience = PipelineResilience()
        self.v9 = PipelineV9Integration("pipeline")

    async def startup(self) -> None:
        """Initialisation au démarrage du serveur."""
        # Priorité process
        self.cpu_gpu.init_process(high_priority=True)
        self.cpu_gpu.probe_gpu()

        # Warmup LLM (si send_fn configuré)
        result = await self.warmup.warmup()
        logger.info("Pipeline warmup: %s", result.get("status", "skip"))

        # KeepAlive en arrière-plan
        self.warmup.start_keepalive()
        logger.info("Pipeline v8.2 initialisé")

    def shutdown(self) -> None:
        """Arrêt propre."""
        self.warmup.stop_keepalive()
        logger.info("Pipeline v8.2 arrêté")

    def metrics(self) -> dict[str, Any]:
        """Métriques agrégées de tous les modules v8.2."""
        return {
            "warmup": self.warmup.metrics(),
            "pipeline": self.pipeline.metrics(),
            "tts_predictive": self.tts_pred.metrics(),
            "cache": self.cache.metrics(),
            "cpu_gpu": self.cpu_gpu.metrics(),
            "profiler": self.profiler.metrics(),
            "resilience": self.resilience.metrics(),
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    _load_env()

    # Hardening 2026-05-16 — validation non bloquante de la config principale.
    # On logue errors/warnings sans interrompre le boot (toute valeur manquante
    # est récupérée par config_manager._DEFAULT_CONFIG en aval).
    _cfg_report = validate_config_file(
        Path(__file__).resolve().parent.parent.parent / "config" / "exo_v9.json",
        required_keys={"audio": dict, "vad": dict, "stt": dict, "tts": dict, "llm": dict},
    )
    logger.info(_cfg_report.summary())
    for _err in _cfg_report.errors:
        logger.error("config exo_v9.json — %s", _err)
    for _warn in _cfg_report.warnings:
        logger.warning("config exo_v9.json — %s", _warn)

    # Prevent duplicate instances
    ensure_single_instance(8765, "exo_server")
    _v9 = init_v9("exo_server", 8765)

    # Initialize HA bridge + managers
    bridge = HomeBridge()
    entities = EntityManager(bridge)
    devices = DeviceManager(bridge)
    areas = AreaManager(bridge)
    actions = ActionDispatcher(bridge, entities, devices, areas)
    sync = SyncManager(bridge, entities, devices, areas)

    # Pipeline Manager v8.2
    pipeline_mgr = PipelineManager()

    # Agent Manager v10
    agent_mgr = AgentManager()
    logger.info("AgentManager v10 initialized")

    # ── v11-v25 — Lazy-loaded cognitive modules ──────────────
    _versions = create_all_versions(agent_mgr)
    logger.info("Cognitive modules v11-v25 registered (lazy-load)")

    # GUI server
    gui = GUIServer(sync, pipeline_mgr, agent_mgr,
                    _versions["v11"], _versions["v12"], _versions["v13"],
                    _versions["v14"], _versions["v15"], _versions["v16"],
                    _versions["v17"], _versions["v18"], _versions["v19"],
                    _versions["v20"], _versions["v21"], _versions["v22"],
                    _versions["v23"], _versions["v24"], _versions["v25"])
    sync.set_gui_broadcast(gui.broadcast)

    # Start GUI WS server
    gui_server = await websockets.serve(
        gui.handler, "localhost", 8765,
        ping_interval=None, ping_timeout=None,
    )
    logger.info("EXO GUI WebSocket server running on ws://localhost:8765")

    # Start Pipeline v8.2
    await pipeline_mgr.startup()

    # Start HA bridge in background
    ha_token = os.environ.get("HA_TOKEN", "")
    if ha_token:
        ha_task = asyncio.create_task(bridge.start())
        logger.info("Home Assistant bridge starting...")
    else:
        ha_task = None
        logger.warning("HA_TOKEN not set — Home Assistant integration disabled")

    # Idle loop
    stop = asyncio.Event()

    def _signal_handler() -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass  # Windows

    logger.info("EXO server ready. Press Ctrl+C to stop.")

    try:
        await stop.wait()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Shutting down...")
        pipeline_mgr.shutdown()
        gui_server.close()
        await gui_server.wait_closed()
        await bridge.stop()
        if ha_task:
            ha_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
