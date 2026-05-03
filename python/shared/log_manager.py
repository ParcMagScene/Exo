"""EXO v9 — Structured JSON logging with correlation IDs."""

import json
import logging
import os
import sys
import threading
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_session_id: ContextVar[Optional[str]] = ContextVar("session_id", default=None)

LOG_DIR = Path(os.environ.get("EXO_LOG_DIR", os.environ.get("EXO_SSD_ROOT", r"D:\EXO") + r"\project\logs"))


class JSONFormatter(logging.Formatter):
    """Emit each record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "module": getattr(record, "exo_module", record.module),
            "func": record.funcName,
            "thread": threading.current_thread().name,
            "msg": record.getMessage(),
        }
        req = _request_id.get()
        ses = _session_id.get()
        if req:
            entry["request_id"] = req
        if ses:
            entry["session_id"] = ses
        ctx = getattr(record, "exo_context", None)
        if ctx:
            entry["ctx"] = ctx
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "msg": str(record.exc_info[1]),
            }
        return json.dumps(entry, ensure_ascii=False, default=str)


class LogManager:
    """Centralized structured logger for an EXO microservice."""

    _instances: dict[str, "LogManager"] = {}

    def __init__(self, service_name: str, *, level: str = "DEBUG",
                 log_to_file: bool = True, log_to_console: bool = True,
                 max_bytes: int = 10 * 1024 * 1024, backup_count: int = 3):
        self.service_name = service_name
        self._logger = logging.getLogger(f"exo.{service_name}")
        self._logger.setLevel(getattr(logging, level.upper(), logging.DEBUG))
        self._logger.handlers.clear()
        self._logger.propagate = False

        fmt = JSONFormatter()

        if log_to_console:
            sh = logging.StreamHandler(sys.stderr)
            sh.setFormatter(fmt)
            self._logger.addHandler(sh)

        if log_to_file:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(
                LOG_DIR / f"{service_name}.jsonl",
                maxBytes=max_bytes, backupCount=backup_count,
                encoding="utf-8",
            )
            fh.setFormatter(fmt)
            self._logger.addHandler(fh)

        LogManager._instances[service_name] = self

    @classmethod
    def get(cls, service_name: str) -> "LogManager":
        inst = cls._instances.get(service_name)
        if inst is None:
            inst = cls(service_name)
        return inst

    # ── correlation ──────────────────────────────────────────────
    @staticmethod
    def new_request_id() -> str:
        rid = uuid.uuid4().hex[:12]
        _request_id.set(rid)
        return rid

    @staticmethod
    def set_request_id(rid: str) -> None:
        _request_id.set(rid)

    @staticmethod
    def get_request_id() -> Optional[str]:
        return _request_id.get()

    @staticmethod
    def set_session_id(sid: str) -> None:
        _session_id.set(sid)

    # ── public API ───────────────────────────────────────────────
    def debug(self, msg: str, context: Optional[dict] = None) -> None:
        self._log(logging.DEBUG, msg, context)

    def info(self, msg: str, context: Optional[dict] = None) -> None:
        self._log(logging.INFO, msg, context)

    def warn(self, msg: str, context: Optional[dict] = None) -> None:
        self._log(logging.WARNING, msg, context)

    def error(self, msg: str, context: Optional[dict] = None,
              exc: Optional[BaseException] = None) -> None:
        self._log(logging.ERROR, msg, context, exc_info=exc)

    def critical(self, msg: str, context: Optional[dict] = None,
                 exc: Optional[BaseException] = None) -> None:
        self._log(logging.CRITICAL, msg, context, exc_info=exc)

    # ── internal ─────────────────────────────────────────────────
    def _log(self, level: int, msg: str,
             context: Optional[dict] = None,
             exc_info: Optional[BaseException] = None) -> None:
        extra = {"exo_module": self.service_name, "exo_context": context}
        self._logger.log(level, msg, extra=extra,
                         exc_info=(type(exc_info), exc_info, exc_info.__traceback__)
                         if exc_info else None)
