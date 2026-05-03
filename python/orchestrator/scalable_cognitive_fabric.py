"""
EXO v20 — ScalableCognitiveFabric
Tissu cognitif extensible : routage intelligent, enregistrement de modules,
extension horizontale et verticale.

API:
  fabric_route(message: dict)   → dict
  fabric_register(module: dict) → dict
  fabric_scale(direction: dict) → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("scalable_cognitive_fabric")


class ScalableCognitiveFabric:
    """Tissu cognitif extensible EXO v20."""

    def __init__(self, governance=None, mcu=None):
        self._governance = governance
        self._mcu = mcu

        self._modules: dict[str, dict] = {}
        self._routes: list[dict] = []
        self._stats = {
            "routed": 0,
            "registered": 0,
            "scaled": 0,
        }

    # ── fabric_route ────────────────────────────────────────
    def fabric_route(self, message: dict) -> dict:
        """Router un message à travers le tissu cognitif."""
        self._stats["routed"] += 1

        source = message.get("source", "unknown")
        destination = message.get("destination", "")
        payload = message.get("payload", {})
        priority = message.get("priority", "normal")

        route_id = f"route_{uuid.uuid4().hex[:8]}"

        # Determine target module
        target = self._modules.get(destination)
        delivered = target is not None

        route = {
            "id": route_id,
            "source": source,
            "destination": destination,
            "delivered": delivered,
            "priority": priority,
            "timestamp": time.time(),
        }
        self._routes.append(route)
        self._trim()

        return {
            "id": route_id,
            "routed": True,
            "source": source,
            "destination": destination,
            "delivered": delivered,
            "priority": priority,
            "timestamp": time.time(),
        }

    # ── fabric_register ─────────────────────────────────────
    def fabric_register(self, module: dict) -> dict:
        """Enregistrer un module dans le tissu cognitif."""
        self._stats["registered"] += 1

        name = module.get("name", "unnamed")
        mod_type = module.get("type", "generic")
        capabilities = module.get("capabilities", [])
        uid = f"fab_{uuid.uuid4().hex[:8]}"

        entry = {
            "id": uid,
            "name": name,
            "type": mod_type,
            "capabilities": capabilities,
            "state": "active",
            "registered_at": time.time(),
        }
        self._modules[uid] = entry

        return {
            "id": uid,
            "registered": True,
            "name": name,
            "type": mod_type,
            "timestamp": time.time(),
        }

    # ── fabric_scale ────────────────────────────────────────
    def fabric_scale(self, direction: dict) -> dict:
        """Étendre le tissu cognitif horizontalement ou verticalement."""
        self._stats["scaled"] += 1

        scale_type = direction.get("type", "horizontal")
        factor = direction.get("factor", 1)
        target_module = direction.get("module", "")

        scale_id = f"scale_{uuid.uuid4().hex[:8]}"

        return {
            "id": scale_id,
            "scaled": True,
            "type": scale_type,
            "factor": factor,
            "target_module": target_module,
            "active_modules": len(self._modules),
            "timestamp": time.time(),
        }

    def list_modules(self) -> list[dict]:
        return [
            {"id": uid, "name": m["name"], "type": m["type"],
             "state": m["state"]}
            for uid, m in self._modules.items()
        ]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "scalable_cognitive_fabric",
            "status": "ok",
            "total_modules": len(self._modules),
            "total_routes": len(self._routes),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._modules.clear()
        self._routes.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("ScalableCognitiveFabric restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._routes) > 5000:
            self._routes = self._routes[-2500:]
