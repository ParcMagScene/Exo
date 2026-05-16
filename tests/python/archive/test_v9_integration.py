"""
Tests unitaires — v9 BaseService & Integration

Valide l'intégration de tous les modules v9 :
 - BaseService (init, health_check, handle_ws_message, instrumentation)
 - init_v9() one-liner factory
"""

import asyncio
import json
import time

import pytest

import sys
from pathlib import Path

from shared.base_service import BaseService, init_v9
from shared.metrics_manager import MetricsManager
from shared.trace_manager import TraceManager
from shared.error_manager import ErrorManager
from shared.security_manager import SecurityManager
from shared.config_manager import ConfigManager
from shared.log_manager import LogManager


# ═══════════════════════════════════════════════════════
#  BaseService
# ═══════════════════════════════════════════════════════

class TestBaseService:
    def setup_method(self):
        MetricsManager.reset()
        TraceManager.reset()
        ErrorManager.reset()
        SecurityManager.reset()
        ConfigManager.reset()
        LogManager._instances.clear()

    def test_creation(self):
        svc = BaseService("test_svc", 9999, init_config=False)
        assert svc.name == "test_svc"
        assert svc.port == 9999
        assert svc.log is not None
        assert svc.metrics is not None
        assert svc.traces is not None
        assert svc.errors is not None
        assert svc.security is not None

    def test_health_check(self):
        svc = BaseService("test_svc", 9999, init_config=False)
        health = svc.health_check()
        assert health["type"] == "health"
        assert health["service"] == "test_svc"
        assert health["status"] == "ok"
        assert health["uptime_s"] >= 0

    def test_begin_end_request(self):
        svc = BaseService("test_svc", 9999, init_config=False)
        rid = svc.begin_request()
        assert len(rid) == 12
        assert svc.metrics.counter("requests_total").value == 1

        svc.end_request(rid)
        # No error
        assert svc.metrics.counter("errors_total").value == 0

    def test_end_request_with_error(self):
        svc = BaseService("test_svc", 9999, init_config=False)
        rid = svc.begin_request()
        svc.end_request(rid, error=True)
        assert svc.metrics.counter("errors_total").value == 1

    def test_on_shutdown(self):
        svc = BaseService("test_svc", 9999, init_config=False)
        # Should not raise
        svc.on_shutdown()


# ═══════════════════════════════════════════════════════
#  WebSocket Message Handler
# ═══════════════════════════════════════════════════════

class TestHandleWsMessage:
    def setup_method(self):
        MetricsManager.reset()
        TraceManager.reset()
        ErrorManager.reset()
        SecurityManager.reset()
        ConfigManager.reset()
        LogManager._instances.clear()

    def test_ping_pong(self):
        svc = BaseService("test_svc", 9999, init_config=False)
        result = asyncio.get_event_loop().run_until_complete(
            svc.handle_ws_message(None, '{"type": "ping"}')
        )
        data = json.loads(result)
        assert data["type"] == "pong"

    def test_health_message(self):
        svc = BaseService("test_svc", 9999, init_config=False)
        result = asyncio.get_event_loop().run_until_complete(
            svc.handle_ws_message(None, '{"type": "health"}')
        )
        data = json.loads(result)
        assert data["type"] == "health"
        assert data["service"] == "test_svc"

    def test_metrics_message(self):
        svc = BaseService("test_svc", 9999, init_config=False)
        svc.metrics.counter("requests_total").inc(5)
        result = asyncio.get_event_loop().run_until_complete(
            svc.handle_ws_message(None, '{"type": "metrics"}')
        )
        data = json.loads(result)
        assert data["type"] == "metrics"
        assert data["counters"]["requests_total"]["value"] == 5

    def test_traces_message(self):
        svc = BaseService("test_svc", 9999, init_config=False)
        result = asyncio.get_event_loop().run_until_complete(
            svc.handle_ws_message(None, '{"type": "traces"}')
        )
        data = json.loads(result)
        assert data["type"] == "traces"
        assert isinstance(data["traces"], list)

    def test_errors_message(self):
        svc = BaseService("test_svc", 9999, init_config=False)
        result = asyncio.get_event_loop().run_until_complete(
            svc.handle_ws_message(None, '{"type": "errors"}')
        )
        data = json.loads(result)
        assert data["type"] == "errors"

    def test_unknown_message_returns_none(self):
        svc = BaseService("test_svc", 9999, init_config=False)
        result = asyncio.get_event_loop().run_until_complete(
            svc.handle_ws_message(None, '{"type": "synthesize", "text": "hello"}')
        )
        assert result is None

    def test_invalid_json_returns_none(self):
        svc = BaseService("test_svc", 9999, init_config=False)
        result = asyncio.get_event_loop().run_until_complete(
            svc.handle_ws_message(None, 'not json')
        )
        assert result is None


# ═══════════════════════════════════════════════════════
#  init_v9 Factory
# ═══════════════════════════════════════════════════════

class TestInitV9:
    def setup_method(self):
        MetricsManager.reset()
        TraceManager.reset()
        ErrorManager.reset()
        SecurityManager.reset()
        ConfigManager.reset()
        LogManager._instances.clear()

    def test_init_v9_returns_base_service(self):
        svc = init_v9("test_service", 9999, init_config=False)
        assert isinstance(svc, BaseService)
        assert svc.name == "test_service"
        assert svc.port == 9999

    def test_init_v9_modules_wired(self):
        svc = init_v9("test_service", 9999, init_config=False)
        # All modules should be initialized
        assert svc.log is not None
        assert svc.metrics is not None
        assert svc.traces is not None
        assert svc.errors is not None
        assert svc.security is not None

    def test_init_v9_health_works(self):
        svc = init_v9("test_service", 9999, init_config=False)
        h = svc.health_check()
        assert h["status"] == "ok"

    def test_init_v9_multiple_services(self):
        svc1 = init_v9("svc_a", 8001, init_config=False)
        MetricsManager.reset()
        svc2 = init_v9("svc_b", 8002, init_config=False)
        assert svc1.name != svc2.name
        assert svc1.log.service_name == "svc_a"
        assert svc2.log.service_name == "svc_b"
