"""
Tests unitaires — System Service (EXO v8)
System info queries.
"""

import sys
from pathlib import Path

import pytest


class TestSystemService:
    """Tests du SystemService."""

    def _make_service(self):
        from system_service import SystemService
        return SystemService()

    def test_create_service(self):
        svc = self._make_service()
        assert svc is not None

    def test_system_info(self):
        svc = self._make_service()
        info = svc.system_info()
        assert "platform" in info
        assert "cpu" in info or "error" not in info
        # At minimum should have platform info
        assert isinstance(info["platform"], str)

    def test_system_info_has_memory(self):
        svc = self._make_service()
        info = svc.system_info()
        # If psutil is available, we should have memory info
        if "ram" in info:
            ram = info["ram"]
            assert "total_gb" in ram
            assert ram["total_gb"] > 0

    def test_system_processes(self):
        svc = self._make_service()
        procs = svc.processes(top_n=5)
        if "error" not in procs:
            assert "processes" in procs
            assert len(procs["processes"]) <= 5

    def test_system_network(self):
        svc = self._make_service()
        net = svc.network()
        # Should return something, even if psutil not available
        assert isinstance(net, dict)

    def test_system_info_no_crash(self):
        """Ensure system_info never raises, even without psutil."""
        svc = self._make_service()
        try:
            info = svc.system_info()
            assert isinstance(info, dict)
        except Exception as e:
            pytest.fail(f"system_info() raised {e}")
