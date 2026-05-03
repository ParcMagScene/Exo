"""
EXO v18 — MicroAgentLayer (couche micro-agents)
Exécute les tâches fines, spécialisées, atomiques à faible coût cognitif.

API:
  micro_execute(task)       → dict
  micro_report()            → dict
  micro_error()             → dict
  register_micro(name, fn)  → dict
  list_micros()             → list[dict]
  health_check()            → dict
  restart()                 → None
  get_stats()               → dict
"""

import logging
import time
import uuid
from typing import Any, Callable

log = logging.getLogger("micro_agent_layer")

DEFAULT_MICROS = [
    "scan_network", "ping_device", "check_light_state",
    "extract_entities", "verify_rule", "read_sensor",
    "toggle_device", "query_knowledge", "validate_output",
    "compute_metric",
]


class MicroAgentLayer:
    """Couche de micro-agents atomiques EXO v18."""

    def __init__(self, meta_memory=None, governance=None):
        self._memory = meta_memory
        self._governance = governance
        self._micros: dict[str, dict] = {}
        self._history: list[dict] = []
        self._errors: list[dict] = []
        self._stats = {
            "tasks_executed": 0,
            "tasks_succeeded": 0,
            "tasks_failed": 0,
            "reports_generated": 0,
            "errors_logged": 0,
        }

        # Enregistrer les micro-agents par défaut
        for name in DEFAULT_MICROS:
            self._micros[name] = {
                "name": name,
                "active": True,
                "executions": 0,
                "failures": 0,
                "avg_latency_ms": 0.0,
                "created_at": time.time(),
            }

    # ── micro_execute ───────────────────────────────────────
    def micro_execute(self, task: dict) -> dict:
        """Exécuter une micro-tâche atomique."""
        self._stats["tasks_executed"] += 1
        t0 = time.time()

        action = task.get("action", task.get("micro", "generic"))
        params = task.get("params", {})
        macro = task.get("macro", "")
        domain = task.get("domain", "general")
        text = task.get("text", "")

        # Trouver le micro-agent
        micro = self._micros.get(action)
        if not micro:
            # Auto-routing par domaine/texte
            action = self._route_task(domain, text, action)
            micro = self._micros.get(action, {
                "name": action, "active": True,
                "executions": 0, "failures": 0,
                "avg_latency_ms": 0.0,
            })

        if not micro.get("active", True):
            self._stats["tasks_failed"] += 1
            return {
                "id": f"mx_{uuid.uuid4().hex[:8]}",
                "executed": False,
                "reason": "micro_inactive",
                "micro": action,
                "timestamp": time.time(),
            }

        # Gouvernance
        if self._governance:
            try:
                g = self._governance.check_action(
                    f"micro_execute:{action}", task)
                if not g.get("allowed", True):
                    self._stats["tasks_failed"] += 1
                    return {
                        "id": f"mx_{uuid.uuid4().hex[:8]}",
                        "executed": False,
                        "reason": "governance_denied",
                        "micro": action,
                        "timestamp": time.time(),
                    }
            except Exception:
                pass

        # Simuler l'exécution atomique
        output = self._execute_atomic(action, params, text, domain)

        elapsed_ms = (time.time() - t0) * 1000
        micro["executions"] = micro.get("executions", 0) + 1
        # Running average
        prev = micro.get("avg_latency_ms", 0.0)
        n = micro["executions"]
        micro["avg_latency_ms"] = round(prev + (elapsed_ms - prev) / n, 3)

        self._stats["tasks_succeeded"] += 1

        result = {
            "id": f"mx_{uuid.uuid4().hex[:8]}",
            "executed": True,
            "micro": action,
            "macro": macro,
            "output": output,
            "latency_ms": round(elapsed_ms, 3),
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        log.info("Micro '%s' executed in %.1fms", action, elapsed_ms)
        return result

    # ── micro_report ────────────────────────────────────────
    def micro_report(self) -> dict:
        """Générer un rapport d'activité des micro-agents."""
        self._stats["reports_generated"] += 1

        agents = []
        for name, micro in self._micros.items():
            agents.append({
                "name": name,
                "active": micro["active"],
                "executions": micro.get("executions", 0),
                "failures": micro.get("failures", 0),
                "avg_latency_ms": micro.get("avg_latency_ms", 0.0),
            })

        return {
            "id": f"mr_{uuid.uuid4().hex[:8]}",
            "agents": agents,
            "total_agents": len(self._micros),
            "active_agents": sum(1 for m in self._micros.values()
                                 if m["active"]),
            "total_executions": self._stats["tasks_executed"],
            "total_failures": self._stats["tasks_failed"],
            "timestamp": time.time(),
        }

    # ── micro_error ─────────────────────────────────────────
    def micro_error(self) -> dict:
        """Retourner les erreurs récentes des micro-agents."""
        self._stats["errors_logged"] += 1
        return {
            "errors": self._errors[-50:],
            "total_errors": len(self._errors),
            "timestamp": time.time(),
        }

    # ── register_micro ──────────────────────────────────────
    def register_micro(self, name: str, config: dict | None = None) -> dict:
        cfg = config or {}
        self._micros[name] = {
            "name": name,
            "active": True,
            "executions": 0,
            "failures": 0,
            "avg_latency_ms": 0.0,
            "created_at": time.time(),
            **{k: v for k, v in cfg.items()
               if k not in ("name", "active", "executions", "failures")},
        }
        return {"registered": True, "name": name}

    # ── list_micros ─────────────────────────────────────────
    def list_micros(self) -> list[dict]:
        return list(self._micros.values())

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "micro_agent_layer",
            "status": "ok",
            "micros_count": len(self._micros),
            "active_micros": sum(1 for m in self._micros.values()
                                 if m["active"]),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._history.clear()
        self._errors.clear()
        for k in self._stats:
            self._stats[k] = 0
        for m in self._micros.values():
            m["executions"] = 0
            m["failures"] = 0
            m["avg_latency_ms"] = 0.0
        log.info("MicroAgentLayer restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _execute_atomic(self, action: str, params: dict,
                        text: str, domain: str) -> dict:
        """Exécuter une action atomique (simulation)."""
        return {
            "action": action,
            "status": "completed",
            "domain": domain,
            "result": f"micro_{action}_done",
        }

    def _route_task(self, domain: str, text: str,
                    fallback: str) -> str:
        """Router une tâche vers le micro-agent approprié."""
        text_lower = text.lower()
        mappings = {
            "scan_network": ["scan", "réseau", "network"],
            "ping_device": ["ping", "connecté"],
            "check_light_state": ["lumière", "lampe", "état"],
            "extract_entities": ["entité", "extraire", "nommée"],
            "verify_rule": ["règle", "vérifier", "valider"],
            "read_sensor": ["capteur", "sensor", "température"],
            "toggle_device": ["allumer", "éteindre", "toggle"],
            "query_knowledge": ["savoir", "connaissance", "query"],
            "validate_output": ["valider", "sortie", "output"],
            "compute_metric": ["métrique", "calcul", "mesure"],
        }
        for name, keywords in mappings.items():
            if any(kw in text_lower for kw in keywords):
                return name
        return fallback

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-5000:]
        if len(self._errors) > 1000:
            self._errors = self._errors[-1000:]
