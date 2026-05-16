"""EXO — helper de log structuré format `[domaine][évènement][ctx]`.

Ajout 2026-05-16 (FULL SAFE REFACTOR).

Pur additif, n'altère pas le `LogManager` existant : c'est un raccourci pour
émettre dans n'importe quel logger standard `logging.Logger` une ligne au
format normalisé du projet, tout en passant le contexte en `extra` pour que
le `JSONFormatter` de `shared.log_manager` continue à produire un champ
``ctx`` exploitable.

Exemple
-------
>>> import logging
>>> logger = logging.getLogger("exo.demo")
>>> log_event(logger, "vad", "frame_dropped", reason="overflow", n=3)

Produit dans la console JSON :
    {"...","msg":"[vad][frame_dropped] reason=overflow n=3","ctx":{...}}
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _format_ctx(ctx: Mapping[str, Any]) -> str:
    """Sérialise le contexte sous forme ``k1=v1 k2=v2`` triée, pour lisibilité."""
    parts: list[str] = []
    for key in sorted(ctx):
        val = ctx[key]
        # Évite les retours à la ligne dans la ligne de log.
        repr_val = repr(val) if isinstance(val, str) and (" " in val or "=" in val) else str(val)
        parts.append(f"{key}={repr_val}")
    return " ".join(parts)


def log_event(
    logger: logging.Logger,
    domain: str,
    event: str,
    *,
    level: str = "INFO",
    **ctx: Any,
) -> None:
    """Émet un évènement structuré au format ``[domaine][évènement] k=v ...``.

    Paramètres
    ----------
    logger:
        Logger standard `logging.Logger` (ex. `logging.getLogger("exo.nlu")`).
    domain:
        Domaine fonctionnel court (``vad``, ``stt``, ``orch``, ``llm`` …).
    event:
        Nom court de l'évènement (``frame_dropped``, ``timeout``, ``ready`` …).
    level:
        Niveau standard (``DEBUG``/``INFO``/``WARNING``/``ERROR``/``CRITICAL``).
        Valeur invalide → ``INFO``.
    **ctx:
        Paires clé/valeur additionnelles, attachées au record via
        ``extra={"exo_context": ctx}`` pour exploitation par le `JSONFormatter`.
    """
    if not isinstance(domain, str) or not domain:
        domain = "unknown"
    if not isinstance(event, str) or not event:
        event = "event"

    lvl = _LEVELS.get(str(level).upper(), logging.INFO)
    suffix = f" {_format_ctx(ctx)}" if ctx else ""
    message = f"[{domain}][{event}]{suffix}"

    extra = {"exo_context": dict(ctx)} if ctx else None
    logger.log(lvl, message, extra=extra) if extra else logger.log(lvl, message)


__all__ = ["log_event"]
