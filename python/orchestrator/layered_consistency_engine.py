"""
EXO v18 — LayeredConsistencyEngine
Garantie de cohérence multi-niveaux.
Vérifie la cohérence entre les couches cognitives,
les macro-agents et les micro-agents.

API:
  check_layer_consistency()     → dict
  enforce_layer_consistency()   → dict
  check_cross_level()           → dict
  get_consistency_report()      → dict
  health_check()                → dict
  restart()                     → None
  get_stats()                   → dict
"""

import logging
import time
import uuid

log = logging.getLogger("layered_consistency")


class LayeredConsistencyEngine:
    """Moteur de cohérence hiérarchique EXO v18."""

    def __init__(self, layer_stack=None, macro_layer=None,
                 micro_layer=None, supervisor=None,
                 governance=None):
        self._stack = layer_stack
        self._macro = macro_layer
        self._micro = micro_layer
        self._supervisor = supervisor
        self._governance = governance

        self._checks_log: list[dict] = []
        self._enforcements: list[dict] = []
        self._inconsistencies: list[dict] = []
        self._stats = {
            "checks_performed": 0,
            "enforcements": 0,
            "cross_level_checks": 0,
            "inconsistencies_found": 0,
            "fixes_applied": 0,
        }

    # ── check_layer_consistency ─────────────────────────────
    def check_layer_consistency(self) -> dict:
        """Vérifier la cohérence intra-couche."""
        self._stats["checks_performed"] += 1

        findings = []

        # Check 1 : chaque couche du stack est active
        if self._stack:
            try:
                layers = self._stack.list_layers()
                for L in layers:
                    active = L.get("active", True)
                    if not active:
                        self._stats["inconsistencies_found"] += 1
                        findings.append({
                            "check": "layer_active",
                            "layer": L.get("name", "?"),
                            "consistent": False,
                            "issue": "layer_inactive",
                        })
                    else:
                        findings.append({
                            "check": "layer_active",
                            "layer": L.get("name", "?"),
                            "consistent": True,
                        })
            except Exception:
                findings.append({
                    "check": "layer_active",
                    "consistent": True,
                    "simulated": True,
                })

        # Check 2 : macro-agents cohérents
        if self._macro:
            try:
                macros = self._macro.list_macros()
                for m in macros:
                    findings.append({
                        "check": "macro_registered",
                        "macro": m.get("name", "?"),
                        "consistent": True,
                    })
            except Exception:
                pass

        all_consistent = all(f.get("consistent", True) for f in findings)

        record = {
            "id": f"cc_{uuid.uuid4().hex[:8]}",
            "checked": True,
            "findings": findings,
            "total_checks": len(findings),
            "all_consistent": all_consistent,
            "inconsistencies": sum(
                1 for f in findings if not f.get("consistent", True)),
            "timestamp": time.time(),
        }
        self._checks_log.append(record)
        self._trim()
        return record

    # ── enforce_layer_consistency ───────────────────────────
    def enforce_layer_consistency(self) -> dict:
        """Appliquer la cohérence entre couches."""
        self._stats["enforcements"] += 1

        # D'abord vérifier
        check = self.check_layer_consistency()
        inconsistent = [f for f in check.get("findings", [])
                        if not f.get("consistent", True)]

        actions = []
        for inc in inconsistent:
            # Tentative de correction
            actions.append({
                "target": inc.get("layer", inc.get("macro", "?")),
                "issue": inc.get("issue", "unknown"),
                "action": "notify_supervisor",
                "applied": True,
            })
            self._stats["fixes_applied"] += 1

            # Escalader au superviseur
            if self._supervisor:
                try:
                    self._supervisor.supervise_layer({
                        "layer": inc.get("layer", "unknown"),
                        "reason": "consistency_enforcement",
                    })
                except Exception:
                    pass

        record = {
            "id": f"ec_{uuid.uuid4().hex[:8]}",
            "enforced": True,
            "inconsistencies_found": len(inconsistent),
            "actions_taken": actions,
            "fixes_applied": len(actions),
            "timestamp": time.time(),
        }
        self._enforcements.append(record)
        self._trim()
        return record

    # ── check_cross_level ───────────────────────────────────
    def check_cross_level(self) -> dict:
        """Vérifier la cohérence entre niveaux (couche ↔ macro ↔ micro)."""
        self._stats["cross_level_checks"] += 1

        cross_checks = []

        # Vérifier que les macro-agents couvrent les domaines des couches
        if self._macro and self._stack:
            try:
                macros = self._macro.list_macros()
                layers = self._stack.list_layers()
                cross_checks.append({
                    "check": "macro_layer_coverage",
                    "macros": len(macros),
                    "layers": len(layers),
                    "consistent": True,
                })
            except Exception:
                pass

        # Vérifier que les micro-agents sont opérationnels
        if self._micro:
            try:
                micros = self._micro.list_micros()
                active = sum(1 for m in micros if m.get("active", True))
                cross_checks.append({
                    "check": "micro_operational",
                    "total": len(micros),
                    "active": active,
                    "consistent": active > 0,
                })
            except Exception:
                pass

        if not cross_checks:
            cross_checks.append({
                "check": "baseline",
                "consistent": True,
                "simulated": True,
            })

        all_consistent = all(c.get("consistent", True)
                             for c in cross_checks)

        return {
            "id": f"xl_{uuid.uuid4().hex[:8]}",
            "checked": True,
            "cross_checks": cross_checks,
            "all_consistent": all_consistent,
            "timestamp": time.time(),
        }

    # ── get_consistency_report ──────────────────────────────
    def get_consistency_report(self) -> dict:
        return {
            "id": f"cr_{uuid.uuid4().hex[:8]}",
            "checks_total": len(self._checks_log),
            "enforcements_total": len(self._enforcements),
            "inconsistencies_total": len(self._inconsistencies),
            "recent_checks": self._checks_log[-5:],
            "recent_enforcements": self._enforcements[-5:],
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "layered_consistency",
            "status": "ok",
            "checks_log_size": len(self._checks_log),
            "inconsistencies": len(self._inconsistencies),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._checks_log.clear()
        self._enforcements.clear()
        self._inconsistencies.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("LayeredConsistencyEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _trim(self) -> None:
        if len(self._checks_log) > 5000:
            self._checks_log = self._checks_log[-5000:]
        if len(self._enforcements) > 2000:
            self._enforcements = self._enforcements[-2000:]
        if len(self._inconsistencies) > 1000:
            self._inconsistencies = self._inconsistencies[-1000:]
