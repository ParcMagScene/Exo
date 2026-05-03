"""
EXO v20 — ModuleCompatibilityChecker
Assure la compatibilité entre modules : API, version, dépendances, cohérence.

API:
  check_api(module: dict)            → dict
  check_version(module: dict)        → dict
  check_dependencies(module: dict)   → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("module_compatibility_checker")


class ModuleCompatibilityChecker:
    """Vérificateur de compatibilité des modules EXO v20."""

    def __init__(self, governance=None, mcu=None):
        self._governance = governance
        self._mcu = mcu

        self._checks: list[dict] = []
        self._stats = {
            "api_checks": 0,
            "version_checks": 0,
            "dependency_checks": 0,
        }

    # ── check_api ───────────────────────────────────────────
    def check_api(self, module: dict) -> dict:
        """Vérifier la compatibilité API d'un module."""
        self._stats["api_checks"] += 1

        name = module.get("name", "unknown")
        required_apis = module.get("required_apis", [])
        provided_apis = module.get("provided_apis", [])

        missing = [api for api in required_apis if api not in provided_apis]
        compatible = len(missing) == 0

        check = {
            "id": f"api_{uuid.uuid4().hex[:8]}",
            "check_type": "api",
            "module": name,
            "compatible": compatible,
            "required": required_apis,
            "provided": provided_apis,
            "missing": missing,
            "timestamp": time.time(),
        }
        self._checks.append(check)
        self._trim()

        return check

    # ── check_version ───────────────────────────────────────
    def check_version(self, module: dict) -> dict:
        """Vérifier la compatibilité de version d'un module."""
        self._stats["version_checks"] += 1

        name = module.get("name", "unknown")
        current = module.get("current_version", "1.0.0")
        required = module.get("required_version", "1.0.0")

        # Simple semver comparison
        cur_parts = [int(x) for x in current.split(".")[:3]]
        req_parts = [int(x) for x in required.split(".")[:3]]

        # Pad to length 3
        while len(cur_parts) < 3:
            cur_parts.append(0)
        while len(req_parts) < 3:
            req_parts.append(0)

        compatible = cur_parts >= req_parts

        check = {
            "id": f"ver_{uuid.uuid4().hex[:8]}",
            "check_type": "version",
            "module": name,
            "compatible": compatible,
            "current_version": current,
            "required_version": required,
            "timestamp": time.time(),
        }
        self._checks.append(check)

        return check

    # ── check_dependencies ──────────────────────────────────
    def check_dependencies(self, module: dict) -> dict:
        """Vérifier les dépendances d'un module."""
        self._stats["dependency_checks"] += 1

        name = module.get("name", "unknown")
        dependencies = module.get("dependencies", [])
        available = module.get("available_modules", [])

        missing = [dep for dep in dependencies if dep not in available]
        satisfied = len(missing) == 0

        check = {
            "id": f"dep_{uuid.uuid4().hex[:8]}",
            "check_type": "dependencies",
            "module": name,
            "satisfied": satisfied,
            "dependencies": dependencies,
            "missing": missing,
            "timestamp": time.time(),
        }
        self._checks.append(check)

        return check

    def list_checks(self, limit: int = 50) -> list[dict]:
        return self._checks[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "module_compatibility_checker",
            "status": "ok",
            "total_checks": len(self._checks),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._checks.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ModuleCompatibilityChecker restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._checks) > 5000:
            self._checks = self._checks[-2500:]
