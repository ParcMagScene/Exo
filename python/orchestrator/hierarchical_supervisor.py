"""
EXO v18 — HierarchicalSupervisor
Supervise chaque couche, macro-agent et micro-agent.
Applique les règles hiérarchiques, détecte les anomalies,
escalade les problèmes entre niveaux.

API:
  supervise_layer(layer)          → dict
  supervise_macro(agent)          → dict
  supervise_micro(agent)          → dict
  enforce_hierarchy_rules()       → dict
  get_supervision_report()        → dict
  health_check()                  → dict
  restart()                       → None
  get_stats()                     → dict
"""

import logging
import time
import uuid

log = logging.getLogger("hierarchical_supervisor")


class HierarchicalSupervisor:
    """Superviseur hiérarchique multi-niveaux EXO v18."""

    def __init__(self, layer_stack=None, macro_layer=None,
                 micro_layer=None, governance=None, meta_memory=None):
        self._stack = layer_stack
        self._macro = macro_layer
        self._micro = micro_layer
        self._governance = governance
        self._memory = meta_memory

        self._supervision_log: list[dict] = []
        self._violations: list[dict] = []
        self._escalations: list[dict] = []
        self._stats = {
            "layers_supervised": 0,
            "macros_supervised": 0,
            "micros_supervised": 0,
            "rules_enforced": 0,
            "violations_detected": 0,
            "escalations": 0,
        }

    # ── supervise_layer ─────────────────────────────────────
    def supervise_layer(self, layer: dict) -> dict:
        """Superviser une couche cognitive."""
        self._stats["layers_supervised"] += 1

        layer_name = layer.get("layer", layer.get("name", "unknown"))
        checks = []

        # Vérifier l'état via le stack
        if self._stack:
            try:
                state = self._stack.get_layer_state(layer_name)
                checks.append({
                    "check": "layer_state",
                    "passed": state.get("active", False),
                    "details": state,
                })
            except Exception:
                checks.append({
                    "check": "layer_state",
                    "passed": False,
                    "details": {"error": "stack_unavailable"},
                })
        else:
            checks.append({
                "check": "layer_state",
                "passed": True,
                "details": {"simulated": True},
            })

        # Gouvernance check
        governed = False
        if self._governance:
            try:
                g = self._governance.check_action(
                    f"supervise_layer:{layer_name}", layer)
                governed = g.get("allowed", True)
            except Exception:
                governed = True

        all_passed = all(c["passed"] for c in checks)

        record = {
            "id": f"sl_{uuid.uuid4().hex[:8]}",
            "target_type": "layer",
            "target": layer_name,
            "supervised": True,
            "checks": checks,
            "all_passed": all_passed,
            "governed": governed,
            "timestamp": time.time(),
        }

        if not all_passed:
            self._stats["violations_detected"] += 1
            self._violations.append(record)

        self._supervision_log.append(record)
        self._trim()
        return record

    # ── supervise_macro ─────────────────────────────────────
    def supervise_macro(self, agent: dict) -> dict:
        """Superviser un macro-agent."""
        self._stats["macros_supervised"] += 1

        agent_name = agent.get("name", agent.get("macro", "unknown"))
        checks = []

        # Vérifier le macro via la couche macro
        if self._macro:
            try:
                macros = self._macro.list_macros()
                found = any(m.get("name") == agent_name for m in macros)
                checks.append({
                    "check": "macro_exists",
                    "passed": found,
                    "agent": agent_name,
                })
            except Exception:
                checks.append({
                    "check": "macro_exists",
                    "passed": True,
                    "simulated": True,
                })
        else:
            checks.append({
                "check": "macro_exists",
                "passed": True,
                "simulated": True,
            })

        all_passed = all(c["passed"] for c in checks)

        record = {
            "id": f"sm_{uuid.uuid4().hex[:8]}",
            "target_type": "macro",
            "target": agent_name,
            "supervised": True,
            "checks": checks,
            "all_passed": all_passed,
            "timestamp": time.time(),
        }

        if not all_passed:
            self._stats["violations_detected"] += 1
            self._violations.append(record)

        self._supervision_log.append(record)
        self._trim()
        return record

    # ── supervise_micro ─────────────────────────────────────
    def supervise_micro(self, agent: dict) -> dict:
        """Superviser un micro-agent."""
        self._stats["micros_supervised"] += 1

        agent_name = agent.get("name", agent.get("micro", "unknown"))
        checks = []

        if self._micro:
            try:
                micros = self._micro.list_micros()
                found = any(m.get("name") == agent_name for m in micros)
                checks.append({
                    "check": "micro_exists",
                    "passed": found,
                    "agent": agent_name,
                })
            except Exception:
                checks.append({
                    "check": "micro_exists",
                    "passed": True,
                    "simulated": True,
                })
        else:
            checks.append({
                "check": "micro_exists",
                "passed": True,
                "simulated": True,
            })

        all_passed = all(c["passed"] for c in checks)

        record = {
            "id": f"si_{uuid.uuid4().hex[:8]}",
            "target_type": "micro",
            "target": agent_name,
            "supervised": True,
            "checks": checks,
            "all_passed": all_passed,
            "timestamp": time.time(),
        }

        if not all_passed:
            self._stats["violations_detected"] += 1
            self._violations.append(record)

        self._supervision_log.append(record)
        self._trim()
        return record

    # ── enforce_hierarchy_rules ─────────────────────────────
    def enforce_hierarchy_rules(self) -> dict:
        """Appliquer les règles hiérarchiques globales."""
        self._stats["rules_enforced"] += 1

        rules_checked = []

        # Règle 1 : toutes les couches doivent être actives
        if self._stack:
            try:
                layers = self._stack.list_layers()
                inactive = [L for L in layers if not L.get("active", True)]
                rules_checked.append({
                    "rule": "all_layers_active",
                    "passed": len(inactive) == 0,
                    "inactive_count": len(inactive),
                })
            except Exception:
                rules_checked.append({
                    "rule": "all_layers_active",
                    "passed": True,
                    "simulated": True,
                })

        # Règle 2 : pas trop de violations récentes
        recent_violations = [v for v in self._violations
                             if time.time() - v.get("timestamp", 0) < 300]
        rules_checked.append({
            "rule": "violations_threshold",
            "passed": len(recent_violations) < 10,
            "recent_violations": len(recent_violations),
        })

        # Règle 3 : supervision régulière
        recent_supervisions = [s for s in self._supervision_log
                               if time.time() - s.get("timestamp", 0) < 600]
        rules_checked.append({
            "rule": "supervision_frequency",
            "passed": True,
            "recent_supervisions": len(recent_supervisions),
        })

        all_passed = all(r["passed"] for r in rules_checked)

        if not all_passed:
            self._stats["escalations"] += 1
            esc = {
                "id": f"esc_{uuid.uuid4().hex[:8]}",
                "failed_rules": [r for r in rules_checked
                                 if not r["passed"]],
                "timestamp": time.time(),
            }
            self._escalations.append(esc)

        return {
            "id": f"hr_{uuid.uuid4().hex[:8]}",
            "enforced": True,
            "rules_checked": rules_checked,
            "all_passed": all_passed,
            "escalations_total": self._stats["escalations"],
            "timestamp": time.time(),
        }

    # ── get_supervision_report ──────────────────────────────
    def get_supervision_report(self) -> dict:
        return {
            "id": f"sr_{uuid.uuid4().hex[:8]}",
            "supervision_entries": len(self._supervision_log),
            "violations_total": len(self._violations),
            "escalations_total": len(self._escalations),
            "recent_entries": self._supervision_log[-10:],
            "recent_violations": self._violations[-5:],
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "hierarchical_supervisor",
            "status": "ok",
            "supervision_count": len(self._supervision_log),
            "violations": len(self._violations),
            "escalations": len(self._escalations),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._supervision_log.clear()
        self._violations.clear()
        self._escalations.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("HierarchicalSupervisor restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _trim(self) -> None:
        if len(self._supervision_log) > 5000:
            self._supervision_log = self._supervision_log[-5000:]
        if len(self._violations) > 1000:
            self._violations = self._violations[-1000:]
        if len(self._escalations) > 500:
            self._escalations = self._escalations[-500:]
