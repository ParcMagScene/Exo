"""Tests unitaires pour `shared.log_event` (FULL SAFE REFACTOR 2026-05-16)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "python"))

from shared.log_event import log_event  # noqa: E402


@pytest.fixture
def caplog_logger(caplog: pytest.LogCaptureFixture) -> logging.Logger:
    caplog.set_level(logging.DEBUG, logger="exo.test.log_event")
    return logging.getLogger("exo.test.log_event")


def test_format_de_base(caplog: pytest.LogCaptureFixture, caplog_logger: logging.Logger) -> None:
    log_event(caplog_logger, "vad", "frame_dropped", reason="overflow", n=3)
    records = [r for r in caplog.records if r.name == "exo.test.log_event"]
    assert len(records) == 1
    msg = records[0].getMessage()
    assert msg.startswith("[vad][frame_dropped] ")
    # Tri alphabetique des cles : n=3 reason=...
    assert "n=3" in msg
    assert "reason=" in msg


def test_sans_contexte(caplog: pytest.LogCaptureFixture, caplog_logger: logging.Logger) -> None:
    log_event(caplog_logger, "orch", "ready")
    records = [r for r in caplog.records if r.name == "exo.test.log_event"]
    assert records[-1].getMessage() == "[orch][ready]"


def test_niveau_invalide_defaut_info(
    caplog: pytest.LogCaptureFixture, caplog_logger: logging.Logger
) -> None:
    log_event(caplog_logger, "x", "y", level="N_IMPORTE_QUOI")
    rec = [r for r in caplog.records if r.name == "exo.test.log_event"][-1]
    assert rec.levelno == logging.INFO


def test_domaine_evenement_vides_remplaces(
    caplog: pytest.LogCaptureFixture, caplog_logger: logging.Logger
) -> None:
    log_event(caplog_logger, "", "", level="INFO")
    rec = [r for r in caplog.records if r.name == "exo.test.log_event"][-1]
    assert rec.getMessage() == "[unknown][event]"


def test_exo_context_attache_en_extra(
    caplog: pytest.LogCaptureFixture, caplog_logger: logging.Logger
) -> None:
    log_event(caplog_logger, "llm", "claude_call", model="opus", latency_ms=1234)
    rec = [r for r in caplog.records if r.name == "exo.test.log_event"][-1]
    ctx = getattr(rec, "exo_context", None)
    assert ctx == {"model": "opus", "latency_ms": 1234}


def test_niveau_warning_remonte(
    caplog: pytest.LogCaptureFixture, caplog_logger: logging.Logger
) -> None:
    log_event(caplog_logger, "stt", "slow_inference", level="WARNING", ms=987)
    rec = [r for r in caplog.records if r.name == "exo.test.log_event"][-1]
    assert rec.levelno == logging.WARNING


def test_valeur_avec_espace_serializee_avec_repr(
    caplog: pytest.LogCaptureFixture, caplog_logger: logging.Logger
) -> None:
    log_event(caplog_logger, "nlu", "intent", phrase="bonjour exo")
    rec = [r for r in caplog.records if r.name == "exo.test.log_event"][-1]
    # repr ajoute des quotes autour de la valeur contenant un espace
    assert "phrase='bonjour exo'" in rec.getMessage()
