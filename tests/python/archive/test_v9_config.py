"""
Tests unitaires — v9 ConfigManager

Valide la configuration centralisée :
 - Defaults, dot-notation get/set
 - Reload, save, deep merge
 - Hot-reload watcher
"""

import json
import time

import pytest

import sys
from pathlib import Path

from shared.config_manager import ConfigManager, _deep_merge


# ═══════════════════════════════════════════════════════
#  Deep Merge
# ═══════════════════════════════════════════════════════

class TestDeepMerge:
    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3}

    def test_nested_merge(self):
        base = {"llm": {"model": "claude", "timeout": 10}}
        override = {"llm": {"timeout": 5}}
        result = _deep_merge(base, override)
        assert result["llm"]["model"] == "claude"
        assert result["llm"]["timeout"] == 5

    def test_new_keys(self):
        base = {"a": 1}
        override = {"b": 2}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_empty_override(self):
        base = {"a": 1}
        result = _deep_merge(base, {})
        assert result == {"a": 1}


# ═══════════════════════════════════════════════════════
#  ConfigManager
# ═══════════════════════════════════════════════════════

class TestConfigManager:
    def setup_method(self):
        ConfigManager.reset()

    def test_defaults_loaded(self, tmp_path):
        cfg = ConfigManager(tmp_path / "config.json")
        assert cfg.get("llm.model") == "claude-sonnet-4-20250514"
        assert cfg.get("stt.backend") == "whispercpp"
        assert cfg.get("tts.voice") == ""

    def test_dot_notation_get(self, tmp_path):
        cfg = ConfigManager(tmp_path / "config.json")
        assert cfg.get("llm.timeout_s") == 10
        assert cfg.get("stt.beam_size") == 1

    def test_dot_notation_get_default(self, tmp_path):
        cfg = ConfigManager(tmp_path / "config.json")
        assert cfg.get("nonexistent.key", "default") == "default"

    def test_dot_notation_set(self, tmp_path):
        cfg = ConfigManager(tmp_path / "config.json")
        cfg.set("llm.temperature", 0.5)
        assert cfg.get("llm.temperature") == 0.5

    def test_section(self, tmp_path):
        cfg = ConfigManager(tmp_path / "config.json")
        llm = cfg.section("llm")
        assert "model" in llm
        assert "timeout_s" in llm

    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "config.json"
        cfg = ConfigManager(path)
        cfg.set("llm.temperature", 0.3)
        cfg.save()
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["llm"]["temperature"] == 0.3

        # Reload
        cfg.reload()
        assert cfg.get("llm.temperature") == 0.3

    def test_file_override(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"llm": {"temperature": 0.1}}))
        cfg = ConfigManager(path)
        assert cfg.get("llm.temperature") == 0.1
        # Other defaults still present
        assert cfg.get("llm.model") == "claude-sonnet-4-20250514"

    def test_on_reload_callback(self, tmp_path):
        path = tmp_path / "config.json"
        cfg = ConfigManager(path)
        called = []
        cfg.on_reload(lambda data: called.append(True))
        cfg.reload()
        assert len(called) == 1

    def test_data_property(self, tmp_path):
        cfg = ConfigManager(tmp_path / "config.json")
        data = cfg.data
        assert isinstance(data, dict)
        assert "llm" in data

    def test_all_default_sections(self, tmp_path):
        cfg = ConfigManager(tmp_path / "config.json")
        for section in ("audio", "llm", "stt", "tts", "tools", "domotique",
                        "network", "cache", "security", "logs", "metrics", "supervisor"):
            assert cfg.section(section), f"Missing section: {section}"

    def test_hot_reload_watcher(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"llm": {"temperature": 0.7}}))
        cfg = ConfigManager(path)
        assert cfg.get("llm.temperature") == 0.7

        # Start watcher
        cfg.start_watching(interval_s=0.1)
        try:
            # Modify config file
            time.sleep(0.05)
            path.write_text(json.dumps({"llm": {"temperature": 0.2}}))
            time.sleep(0.3)  # Wait for watcher to detect
            assert cfg.get("llm.temperature") == 0.2
        finally:
            cfg.stop_watching()
