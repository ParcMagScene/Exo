"""Tests unitaires pour `shared.config_validator` (FULL SAFE REFACTOR 2026-05-16)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT / "python"))

from shared.config_validator import (  # noqa: E402
    ConfigValidationReport,
    validate_config_file,
)


def _write(tmp_path: Path, obj: object) -> Path:
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def test_fichier_absent_report_erreur(tmp_path: Path) -> None:
    rep = validate_config_file(tmp_path / "ghost.json")
    assert not rep.is_ok
    assert any("absent" in e.lower() for e in rep.errors)


def test_json_invalide(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{this is not json", encoding="utf-8")
    rep = validate_config_file(p)
    assert not rep.is_ok
    assert any("invalide" in e.lower() for e in rep.errors)


def test_racine_non_objet(tmp_path: Path) -> None:
    p = _write(tmp_path, [1, 2, 3])
    rep = validate_config_file(p)
    assert not rep.is_ok
    assert any("racine non-objet" in e.lower() for e in rep.errors)


def test_cle_requise_manquante(tmp_path: Path) -> None:
    p = _write(tmp_path, {"a": 1})
    rep = validate_config_file(p, required_keys={"b": int})
    assert "Clé requise manquante : 'b'" in rep.errors


def test_type_invalide(tmp_path: Path) -> None:
    p = _write(tmp_path, {"audio": "string_au_lieu_de_dict"})
    rep = validate_config_file(p, required_keys={"audio": dict})
    assert any("type" in e for e in rep.errors)


def test_defauts_appliques(tmp_path: Path) -> None:
    p = _write(tmp_path, {})
    rep = validate_config_file(p, defaults={"foo": 42})
    assert rep.fixed
    assert rep.data["foo"] == 42


def test_port_hors_borne(tmp_path: Path) -> None:
    p = _write(tmp_path, {"port_a": 70000})
    rep = validate_config_file(p, port_keys=["port_a"])
    assert not rep.is_ok
    assert any("hors borne" in e for e in rep.errors)


def test_port_non_entier(tmp_path: Path) -> None:
    p = _write(tmp_path, {"port_a": "8080"})
    rep = validate_config_file(p, port_keys=["port_a"])
    assert any("non entier" in e for e in rep.errors)


def test_collision_de_ports(tmp_path: Path) -> None:
    p = _write(tmp_path, {"port_a": 8765, "port_b": 8765})
    rep = validate_config_file(p, port_keys=["port_a", "port_b"])
    assert any("Collision" in e for e in rep.errors)


def test_chemin_introuvable_warning_non_bloquant(tmp_path: Path) -> None:
    p = _write(tmp_path, {"model": "Z:/inexistant.bin"})
    rep = validate_config_file(p, path_keys=["model"])
    assert rep.is_ok  # warning seulement
    assert any("introuvable" in w for w in rep.warnings)


def test_chemin_existant(tmp_path: Path) -> None:
    existing = tmp_path / "exists.txt"
    existing.write_text("ok", encoding="utf-8")
    p = _write(tmp_path, {"model": str(existing)})
    rep = validate_config_file(p, path_keys=["model"])
    assert rep.is_ok
    assert not rep.warnings


def test_summary_compte_correct(tmp_path: Path) -> None:
    p = _write(tmp_path, {"a": "x"})
    rep = validate_config_file(
        p,
        required_keys={"a": int, "b": int},  # 2 erreurs (type + manquant)
        defaults={"c": 1},  # 1 default
        path_keys=["unknown_path_key_skipped"],  # ignoree
    )
    s = rep.summary()
    assert "2 erreur(s)" in s
    assert "1 défaut(s)" in s


def test_is_ok_true_par_defaut(tmp_path: Path) -> None:
    p = _write(tmp_path, {"a": 1})
    rep = validate_config_file(p)
    assert rep.is_ok
    assert isinstance(rep, ConfigValidationReport)
