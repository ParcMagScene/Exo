"""EXO 2026 — Hardening toolkit.

Pièces complémentaires à `resilience.py` / `error_manager.py` :

- ``install_global_excepthook()``  : capture des exceptions non rattrapées
  (thread + asyncio) pour empêcher tout crash silencieux.
- ``preflight_*()``                 : vérifications synchrones avant démarrage
  (fichiers, ports, modèles, GGUF, binaires, dépendances).
- ``safe_json_loads()``             : parsing JSON tolérant aux entrées
  invalides (retourne ``None`` au lieu de lever).
- ``with_timeout()``                : helper async-friendly pour wrapper
  une coroutine ou un appel sync avec un timeout strict + log.
- ``debounce_async()``              : decorator pour empêcher les ré-entrées
  rapides (utilisé pour les handlers WS).
- ``RateLimiter``                   : token-bucket simple pour limiter les
  reconnexions WebSocket trop rapides.

N'IMPORTE PAS de modules réseau lourds ; conçu pour être chargé tôt dans
``shared/__init__.py``.
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import socket
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Optional, Union

__all__ = [
    "install_global_excepthook",
    "preflight_file",
    "preflight_port_free",
    "preflight_port_listen",
    "preflight_model_gguf",
    "preflight_binary",
    "preflight_dependencies",
    "safe_json_loads",
    "safe_json_dumps",
    "with_timeout",
    "debounce_async",
    "RateLimiter",
    "PreflightReport",
]

_log = logging.getLogger("exo.hardening")
if not _log.handlers:
    _log.addHandler(logging.NullHandler())

# ---------------------------------------------------------------------------
# 1) Global exception hooks — anti-crash-silencieux
# ---------------------------------------------------------------------------

_excepthook_installed = False


def _sys_excepthook(exc_type, exc_value, exc_tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    _log.critical(
        "Exception non rattrapée (thread principal) : %s",
        "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
    )


def _thread_excepthook(args) -> None:  # type: ignore[no-untyped-def]
    if issubclass(args.exc_type, KeyboardInterrupt):
        return
    _log.critical(
        "Exception non rattrapée (thread %s) : %s",
        args.thread.name if args.thread else "?",
        "".join(
            traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
        ),
    )


def _asyncio_excepthook(loop, context) -> None:  # type: ignore[no-untyped-def]
    exc = context.get("exception")
    msg = context.get("message", "")
    if exc is not None:
        _log.error(
            "Exception asyncio non rattrapée : %s — %s",
            msg,
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        )
    else:
        _log.error("Erreur asyncio : %s", msg)


def install_global_excepthook() -> None:
    """Installe les hooks globaux (idempotent)."""
    global _excepthook_installed
    if _excepthook_installed:
        return
    try:
        sys.excepthook = _sys_excepthook
        threading.excepthook = _thread_excepthook  # type: ignore[attr-defined]
        try:
            loop = asyncio.get_event_loop()
            loop.set_exception_handler(_asyncio_excepthook)
        except RuntimeError:
            # Pas de loop en cours — sera réinstallé par BaseService.
            pass
        _excepthook_installed = True
        _log.debug("Hooks d'exceptions globaux installés.")
    except Exception:  # défense ultime : ne jamais casser l'init
        pass


# ---------------------------------------------------------------------------
# 2) Préflight — vérifications avant démarrage
# ---------------------------------------------------------------------------


class PreflightReport:
    """Accumule les résultats des contrôles préflight."""

    def __init__(self, service: str):
        self.service = service
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.ok: list[str] = []

    def add_ok(self, msg: str) -> None:
        self.ok.append(msg)

    def add_warn(self, msg: str) -> None:
        self.warnings.append(msg)
        _log.warning("[%s] %s", self.service, msg)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        _log.error("[%s] %s", self.service, msg)

    @property
    def is_ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return (
            f"Préflight {self.service} : "
            f"{len(self.ok)} OK, {len(self.warnings)} avertissement(s), "
            f"{len(self.errors)} erreur(s)"
        )


def preflight_file(
    path: Union[str, Path],
    *,
    min_size_bytes: int = 0,
    report: Optional[PreflightReport] = None,
) -> bool:
    """Vérifie l'existence et la taille minimale d'un fichier."""
    p = Path(path)
    if not p.exists():
        msg = f"Fichier introuvable : {p}"
        if report:
            report.add_error(msg)
        else:
            _log.error(msg)
        return False
    if not p.is_file():
        msg = f"Chemin non-fichier : {p}"
        if report:
            report.add_error(msg)
        return False
    if min_size_bytes > 0 and p.stat().st_size < min_size_bytes:
        msg = (
            f"Fichier trop petit : {p} ({p.stat().st_size} < {min_size_bytes} octets)"
        )
        if report:
            report.add_warn(msg)
        return False
    if report:
        report.add_ok(f"Fichier OK : {p.name}")
    return True


def preflight_port_free(port: int, *, host: str = "127.0.0.1",
                        report: Optional[PreflightReport] = None) -> bool:
    """Vérifie que le port est LIBRE (peut être lié)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.bind((host, port))
        s.close()
        if report:
            report.add_ok(f"Port {port} libre")
        return True
    except OSError:
        msg = f"Port {port} déjà occupé"
        if report:
            report.add_error(msg)
        return False


def preflight_port_listen(
    port: int,
    *,
    host: str = "127.0.0.1",
    timeout_s: float = 1.0,
    report: Optional[PreflightReport] = None,
) -> bool:
    """Vérifie qu'un service ÉCOUTE sur le port (dépendance amont)."""
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            if report:
                report.add_ok(f"Service détecté sur port {port}")
            return True
    except (OSError, socket.timeout):
        msg = f"Aucun service en écoute sur port {port}"
        if report:
            report.add_warn(msg)
        return False


def preflight_model_gguf(
    path: Union[str, Path],
    *,
    report: Optional[PreflightReport] = None,
) -> bool:
    """Vérification spécifique fichier GGUF (magic header + taille min)."""
    p = Path(path)
    if not preflight_file(p, min_size_bytes=1024 * 1024, report=report):
        return False
    try:
        with open(p, "rb") as f:
            magic = f.read(4)
        if magic != b"GGUF":
            msg = f"Magic GGUF invalide : {p} (lu {magic!r})"
            if report:
                report.add_error(msg)
            return False
        if report:
            report.add_ok(f"GGUF valide : {p.name}")
        return True
    except OSError as exc:
        msg = f"Lecture GGUF échouée : {p} ({exc})"
        if report:
            report.add_error(msg)
        return False


def preflight_binary(
    path: Union[str, Path],
    *,
    report: Optional[PreflightReport] = None,
) -> bool:
    """Vérifie qu'un binaire est exécutable."""
    p = Path(path)
    if not preflight_file(p, report=report):
        return False
    if os.name == "nt":
        # Windows : pas de bit exécutable, on contrôle l'extension.
        if p.suffix.lower() not in {".exe", ".bat", ".cmd", ".ps1"}:
            if report:
                report.add_warn(f"Binaire d'extension inhabituelle : {p.suffix}")
        return True
    if not os.access(p, os.X_OK):
        msg = f"Binaire non exécutable : {p}"
        if report:
            report.add_error(msg)
        return False
    return True


def preflight_dependencies(
    modules: Iterable[str],
    *,
    report: Optional[PreflightReport] = None,
) -> bool:
    """Vérifie que tous les modules Python listés sont importables."""
    import importlib

    all_ok = True
    for mod in modules:
        try:
            importlib.import_module(mod)
            if report:
                report.add_ok(f"Module Python : {mod}")
        except Exception as exc:  # noqa: BLE001
            all_ok = False
            msg = f"Module Python manquant : {mod} ({exc.__class__.__name__})"
            if report:
                report.add_error(msg)
            else:
                _log.error(msg)
    return all_ok


# ---------------------------------------------------------------------------
# 3) JSON safe wrappers
# ---------------------------------------------------------------------------


def safe_json_loads(raw: Union[str, bytes], *, default: Any = None) -> Any:
    """Parse JSON sans jamais lever (retourne ``default`` en cas d'échec)."""
    if raw is None or raw == b"" or raw == "":
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        _log.warning(
            "JSON invalide ignoré (%s) : %r…",
            exc.__class__.__name__,
            (raw[:120] if isinstance(raw, (str, bytes)) else raw),
        )
        return default


def safe_json_dumps(obj: Any, *, default: str = "{}") -> str:
    """Sérialise sans jamais lever."""
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError) as exc:
        _log.warning("Sérialisation JSON échouée (%s)", exc)
        return default


# ---------------------------------------------------------------------------
# 4) Timeouts et debounce
# ---------------------------------------------------------------------------


async def with_timeout(
    coro_or_callable: Union[Awaitable, Callable[..., Any]],
    timeout_s: float,
    *args,
    fallback: Any = None,
    label: str = "<anonyme>",
    **kwargs,
) -> Any:
    """Exécute une coroutine ou un callable avec un timeout strict.

    Retourne ``fallback`` si le délai est dépassé.
    """
    try:
        if asyncio.iscoroutine(coro_or_callable):
            return await asyncio.wait_for(coro_or_callable, timeout=timeout_s)
        if asyncio.iscoroutinefunction(coro_or_callable):
            return await asyncio.wait_for(
                coro_or_callable(*args, **kwargs), timeout=timeout_s
            )
        # Sync : exécution en thread pour pouvoir timeout proprement.
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, lambda: coro_or_callable(*args, **kwargs))
        return await asyncio.wait_for(fut, timeout=timeout_s)
    except asyncio.TimeoutError:
        _log.warning("Délai dépassé pour %s (>%.1fs) — repli", label, timeout_s)
        return fallback
    except Exception as exc:  # noqa: BLE001
        _log.error("Erreur dans with_timeout(%s) : %s", label, exc)
        return fallback


def debounce_async(min_interval_s: float = 0.25) -> Callable:
    """Decorator empêchant les ré-entrées rapides d'une coroutine."""

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        last = {"t": 0.0}
        lock = asyncio.Lock()

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            async with lock:
                now = time.monotonic()
                if now - last["t"] < min_interval_s:
                    _log.debug("Debounce : appel ignoré pour %s", fn.__name__)
                    return None
                last["t"] = now
            return await fn(*args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# 5) Rate-limiter — anti-reconnexion intempestive
# ---------------------------------------------------------------------------


class RateLimiter:
    """Token-bucket très léger (thread-safe via lock asyncio)."""

    def __init__(self, max_events: int, period_s: float):
        self.max_events = max(1, max_events)
        self.period_s = max(0.01, period_s)
        self._events: list[float] = []
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        now = time.monotonic()
        with self._lock:
            self._events = [t for t in self._events if now - t < self.period_s]
            if len(self._events) >= self.max_events:
                return False
            self._events.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
