"""EXO 2026 — Validateur de configuration JSON.

Charge ``config/*.json`` et vérifie :
- existence + JSON parsable,
- types attendus (string/int/bool/list/dict),
- valeurs par défaut injectées si manquant,
- chemins de modèles / binaires existants,
- ports cohérents (1..65535, sans collision).

Conçu pour être appelé au démarrage d'EXO. Ne lève jamais d'exception :
retourne un ``ConfigValidationReport`` qui agrège erreurs/avertissements.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

_log = logging.getLogger("exo.config_validator")
if not _log.handlers:
    _log.addHandler(logging.NullHandler())


@dataclass
class ConfigValidationReport:
    file: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return (
            f"Config {self.file}: "
            f"{len(self.errors)} erreur(s), "
            f"{len(self.warnings)} avertissement(s), "
            f"{len(self.fixed)} défaut(s) appliqué(s)"
        )


def _check_type(report: ConfigValidationReport, key: str, value: Any, expected: type) -> bool:
    if not isinstance(value, expected):
        report.errors.append(
            f"Clé '{key}' : type {type(value).__name__} (attendu {expected.__name__})"
        )
        return False
    return True


def _check_port(report: ConfigValidationReport, key: str, value: Any) -> bool:
    if not isinstance(value, int):
        report.errors.append(f"Port '{key}' non entier : {value!r}")
        return False
    if not (1 <= value <= 65535):
        report.errors.append(f"Port '{key}' hors borne (1..65535) : {value}")
        return False
    return True


def _check_path(
    report: ConfigValidationReport,
    key: str,
    value: Any,
    *,
    must_exist: bool = True,
) -> bool:
    if not isinstance(value, str) or not value:
        report.errors.append(f"Chemin '{key}' vide ou non-string")
        return False
    if must_exist and not Path(value).exists():
        report.warnings.append(f"Chemin '{key}' introuvable : {value}")
        return False
    return True


def validate_config_file(
    path: str | Path,
    *,
    required_keys: dict[str, type] | None = None,
    port_keys: Iterable[str] = (),
    path_keys: Iterable[str] = (),
    defaults: dict[str, Any] | None = None,
) -> ConfigValidationReport:
    """Charge un JSON et applique les contrôles déclarés.

    ``required_keys`` : mapping clé → type attendu.
    ``port_keys``     : clés à valider comme ports.
    ``path_keys``     : clés à valider comme chemins existants.
    ``defaults``      : valeurs par défaut appliquées si clé absente.
    """
    p = Path(path)
    report = ConfigValidationReport(file=str(p))
    if not p.exists():
        report.errors.append(f"Fichier absent : {p}")
        return report
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        report.errors.append(f"JSON invalide : {exc.__class__.__name__} — {exc}")
        return report
    if not isinstance(data, dict):
        report.errors.append(f"Racine non-objet : {type(data).__name__}")
        return report
    report.data = data

    # Defaults
    if defaults:
        for k, v in defaults.items():
            if k not in data:
                data[k] = v
                report.fixed.append(f"Défaut appliqué : {k} = {v!r}")

    # Required + types
    if required_keys:
        for key, expected in required_keys.items():
            if key not in data:
                report.errors.append(f"Clé requise manquante : '{key}'")
                continue
            _check_type(report, key, data[key], expected)

    # Ports
    seen_ports: dict[int, str] = {}
    for key in port_keys:
        if key not in data:
            continue
        if _check_port(report, key, data[key]):
            port = int(data[key])
            if port in seen_ports:
                report.errors.append(
                    f"Collision de ports : '{key}' et '{seen_ports[port]}' = {port}"
                )
            else:
                seen_ports[port] = key

    # Paths
    for key in path_keys:
        if key not in data:
            continue
        _check_path(report, key, data[key], must_exist=True)

    return report
