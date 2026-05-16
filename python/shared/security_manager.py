"""EXO v9 — Security manager: permissions, audit log."""

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

AUDIT_LOG_PATH = Path(
    os.environ.get("EXO_AUDIT_LOG")
    or (
        (os.environ.get("EXO_LOGS_DIR") or (os.environ.get("EXO_SSD_ROOT", r"D:\EXO") + r"\logs"))
        + r"\audit.jsonl"
    )
)

# ── Permission rules ─────────────────────────────────────────────

PERMISSION_DEFAULTS: dict[str, dict[str, str]] = {
    "domotique": {
        "ha_turn_on": "allow",
        "ha_turn_off": "allow",
        "ha_toggle": "allow",
        "ha_set_brightness": "allow",
        "ha_set_color": "allow",
        "ha_set_temperature": "restricted",
        "ha_get_state": "allow",
        "ha_list_entities": "allow",
        "camera_snapshot": "restricted",
        "camera_stream": "restricted",
    },
    "fichiers": {
        "read": "allow",
        "write": "restricted",
        "delete": "deny",
        "execute": "deny",
    },
    "reseau": {
        "scan": "restricted",
        "ping": "allow",
        "port_scan": "deny",
    },
    "outils": {
        "calendar_read": "allow",
        "calendar_write": "restricted",
        "system_info": "allow",
        "system_execute": "deny",
    },
}


class AuditLog:
    """Append-only audit log for sensitive actions."""

    def __init__(self, path: Optional[Path] = None):
        self._path = path or AUDIT_LOG_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._entries: list[dict[str, Any]] = []
        self._max_memory = 1000

    def record(self, action: str, module: str,
               params: Optional[dict] = None,
               result: str = "ok",
               details: Optional[str] = None) -> None:
        entry = {
            "ts": time.time(),
            "action": action,
            "module": module,
            "params": params or {},
            "result": result,
        }
        if details:
            entry["details"] = details

        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_memory:
                self._entries = self._entries[-self._max_memory:]

        try:
            line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"
            with self._lock:
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(line)
        except OSError:
            pass

    def recent(self, n: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._entries[-n:])

    def search(self, module: Optional[str] = None,
               action: Optional[str] = None,
               since: Optional[float] = None) -> list[dict[str, Any]]:
        with self._lock:
            entries = list(self._entries)
        results = []
        for e in entries:
            if module and e["module"] != module:
                continue
            if action and e["action"] != action:
                continue
            if since and e["ts"] < since:
                continue
            results.append(e)
        return results


class SecurityManager:
    """Permission enforcement + audit logging for EXO."""

    _instance: Optional["SecurityManager"] = None

    def __init__(self):
        self._permissions: dict[str, dict[str, str]] = dict(PERMISSION_DEFAULTS)
        self.audit = AuditLog()
        self._lock = threading.Lock()

    @classmethod
    def instance(cls) -> "SecurityManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def load_permissions(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            with self._lock:
                for mod, rules in data.items():
                    self._permissions.setdefault(mod, {}).update(rules)
        except (json.JSONDecodeError, OSError):
            pass

    def check_permission(self, module: str, action: str) -> str:
        """Returns 'allow', 'deny', or 'restricted'."""
        with self._lock:
            rules = self._permissions.get(module, {})
        return rules.get(action, "deny")

    def is_allowed(self, module: str, action: str) -> bool:
        perm = self.check_permission(module, action)
        return perm in ("allow", "restricted")

    def authorize(self, module: str, action: str,
                  params: Optional[dict] = None) -> bool:
        """Check + audit. Returns True if allowed."""
        perm = self.check_permission(module, action)
        allowed = perm in ("allow", "restricted")
        self.audit.record(
            action=action,
            module=module,
            params=params,
            result="allowed" if allowed else "denied",
        )
        return allowed

    def set_permission(self, module: str, action: str, rule: str) -> None:
        if rule not in ("allow", "deny", "restricted"):
            raise ValueError(f"Invalid rule: {rule}")
        with self._lock:
            self._permissions.setdefault(module, {})[action] = rule

    def get_permissions(self, module: Optional[str] = None) -> dict:
        with self._lock:
            if module:
                return dict(self._permissions.get(module, {}))
            return {m: dict(r) for m, r in self._permissions.items()}

    def export_permissions(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            data = {m: dict(r) for m, r in self._permissions.items()}
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8")
