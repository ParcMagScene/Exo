#!/usr/bin/env python3
"""

# Patch global EXO : forcer le working directory à D:/EXO/ pour tous les services
import os
os.chdir("D:/EXO/")
EXO v5.2 — Tools Server (WebSocket)
Port 8776 — Calculs mathématiques, conversions d'unités, dates

Protocol WebSocket :
  → JSON {"action":"calculate","params":{"expression":"2**10 + sin(pi/4)"}}
  ← JSON {"ok":true,"data":{"expression":"...","result":1025.7071...}}

  → JSON {"action":"convert","params":{"value":100,"from_unit":"km/h","to_unit":"m/s"}}
  ← JSON {"ok":true,"data":{"value":100,"from_unit":"km/h","to_unit":"m/s","result":27.7778}}
"""

import ast
import asyncio
try:
    import ujson as json  # v6.0 perf : 3-5x plus rapide que stdlib (audit perf)
except ImportError:
    import json
import logging
import math
import operator
import sys
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import websockets
except ImportError:
    raise SystemExit("pip install websockets")

# Singleton guard
from shared.singleton_guard import ensure_single_instance
from shared.base_service import init_v9


# --- Logging EXO centralisé (identique C++) ---
import os
from pathlib import Path
def _get_exo_logfile():
    # Correction : tous les logs doivent aller dans D:/EXO/logs/
    log_dir = os.environ.get("EXO_LOGS_DIR", "D:/EXO/logs")
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    ts = os.environ.get("EXO_SESSION_TIMESTAMP")
    if not ts:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(log_dir, f"exo_{ts}.log")

logfile = _get_exo_logfile()

_file_handler = logging.FileHandler(logfile, encoding="utf-8", delay=False)
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [Tools] %(message)s"))
_file_handler.flush = _file_handler.stream.flush

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Tools] %(message)s")
log = logging.getLogger("tools_server")
log.addHandler(_file_handler)
log.propagate = True
log.info("=== EXO TOOLS_SERVER STARTUP ===")
_file_handler.flush()

PORT = 8776

# ─────────────────────────────────────────────────────
#  Calculatrice sécurisée
# ─────────────────────────────────────────────────────

# Fonctions math autorisées (whitelist stricte)
SAFE_MATH = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "int": int,
    "float": float,
    # math module
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "exp": math.exp,
    "pow": math.pow,
    "ceil": math.ceil,
    "floor": math.floor,
    "factorial": math.factorial,
    "gcd": math.gcd,
    "radians": math.radians,
    "degrees": math.degrees,
    "hypot": math.hypot,
    # Constantes
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
}

# Pattern pour valider les expressions (pas d'import, exec, eval, etc.)
FORBIDDEN_PATTERN = re.compile(
    r"(import|exec|eval|compile|open|__\w+__|getattr|setattr|delattr|globals|locals|vars|dir|type|class)",
    re.IGNORECASE,
)

# ── AST-safe operators ──
_SAFE_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_SAFE_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_SAFE_CMPOPS = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}


def _eval_node(node: ast.AST) -> Any:
    """Recursively evaluate an AST node using only whitelisted operations."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Constante non autorisée: {node.value!r}")

    if isinstance(node, ast.Name):
        name = node.id
        if name in SAFE_MATH:
            return SAFE_MATH[name]
        raise ValueError(f"Nom non autorisé: {name}")

    if isinstance(node, ast.BinOp):
        op_func = _SAFE_BINOPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Opérateur non autorisé: {type(node.op).__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return op_func(left, right)

    if isinstance(node, ast.UnaryOp):
        op_func = _SAFE_UNARYOPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Opérateur unaire non autorisé: {type(node.op).__name__}")
        return op_func(_eval_node(node.operand))

    if isinstance(node, ast.Call):
        func = _eval_node(node.func)
        if not callable(func):
            raise ValueError("Appel non autorisé")
        if node.keywords:
            raise ValueError("Arguments nommés non autorisés")
        args = [_eval_node(a) for a in node.args]
        return func(*args)

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            op_func = _SAFE_CMPOPS.get(type(op))
            if op_func is None:
                raise ValueError(f"Comparaison non autorisée: {type(op).__name__}")
            right = _eval_node(comparator)
            if not op_func(left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.IfExp):
        # Ternaire: a if cond else b
        if _eval_node(node.test):
            return _eval_node(node.body)
        return _eval_node(node.orelse)

    raise ValueError(f"Construction non autorisée: {type(node).__name__}")


def safe_calculate(expression: str) -> float | int | str:
    """Évalue une expression mathématique de manière sécurisée via AST."""
    expression = expression.strip()

    if not expression:
        raise ValueError("Expression vide")

    if len(expression) > 500:
        raise ValueError("Expression trop longue (max 500 caractères)")

    if FORBIDDEN_PATTERN.search(expression):
        raise ValueError("Expression contient des termes interdits")

    # Remplacements courants
    expression = expression.replace("^", "**")
    expression = expression.replace("×", "*")
    expression = expression.replace("÷", "/")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        raise ValueError("Syntaxe d'expression invalide")

    try:
        result = _eval_node(tree)
    except ZeroDivisionError:
        raise ValueError("Division par zéro")
    except OverflowError:
        raise ValueError("Résultat trop grand")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Erreur de calcul: {exc}")

    if isinstance(result, float) and result != result:  # NaN check
        raise ValueError("Résultat non défini (NaN)")

    return result


# ─────────────────────────────────────────────────────
#  Convertisseur d'unités
# ─────────────────────────────────────────────────────

# Toutes les conversions passent par une unité de base (SI)
# Format: { catégorie: { unité: facteur_vers_base } }
UNIT_CONVERSIONS: dict[str, dict[str, float]] = {
    # Longueur → mètres
    "length": {
        "m": 1.0, "km": 1000.0, "cm": 0.01, "mm": 0.001,
        "mi": 1609.344, "yd": 0.9144, "ft": 0.3048, "in": 0.0254,
        "nm": 1852.0, "um": 1e-6,
    },
    # Masse → kilogrammes
    "mass": {
        "kg": 1.0, "g": 0.001, "mg": 1e-6, "t": 1000.0,
        "lb": 0.453592, "oz": 0.0283495, "st": 6.35029,
    },
    # Vitesse → m/s
    "speed": {
        "m/s": 1.0, "km/h": 1.0 / 3.6, "mph": 0.44704,
        "kn": 0.514444, "ft/s": 0.3048,
    },
    # Température (spéciale — offset)
    "temperature": {},  # Gérée séparément
    # Volume → litres
    "volume": {
        "l": 1.0, "ml": 0.001, "cl": 0.01, "dl": 0.1,
        "m3": 1000.0, "gal": 3.78541, "qt": 0.946353,
        "pt": 0.473176, "cup": 0.236588, "fl_oz": 0.0295735,
    },
    # Surface → m²
    "area": {
        "m2": 1.0, "km2": 1e6, "cm2": 1e-4, "mm2": 1e-6,
        "ha": 10000.0, "acre": 4046.86, "ft2": 0.092903, "in2": 0.00064516,
    },
    # Temps → secondes
    "time": {
        "s": 1.0, "ms": 0.001, "us": 1e-6, "min": 60.0,
        "h": 3600.0, "day": 86400.0, "week": 604800.0,
        "month": 2629746.0, "year": 31556952.0,
    },
    # Données → octets
    "data": {
        "b": 1.0, "kb": 1024.0, "mb": 1024 ** 2, "gb": 1024 ** 3,
        "tb": 1024 ** 4, "bit": 0.125, "kbit": 128.0, "mbit": 128 * 1024,
    },
    # Énergie → joules
    "energy": {
        "j": 1.0, "kj": 1000.0, "cal": 4.184, "kcal": 4184.0,
        "wh": 3600.0, "kwh": 3.6e6, "ev": 1.602e-19,
    },
}

# Alias normalisés
UNIT_ALIASES: dict[str, str] = {
    "mètre": "m", "mètres": "m", "metre": "m", "meters": "m",
    "kilomètre": "km", "kilomètres": "km", "kilometer": "km",
    "centimètre": "cm", "centimètres": "cm",
    "millimètre": "mm", "millimètres": "mm",
    "mile": "mi", "miles": "mi",
    "yard": "yd", "yards": "yd",
    "foot": "ft", "feet": "ft", "pied": "ft", "pieds": "ft",
    "inch": "in", "inches": "in", "pouce": "in", "pouces": "in",
    "kilogramme": "kg", "kilogrammes": "kg", "kilogram": "kg",
    "gramme": "g", "grammes": "g", "gram": "g",
    "tonne": "t", "tonnes": "t",
    "pound": "lb", "pounds": "lb", "livre": "lb", "livres": "lb",
    "ounce": "oz", "ounces": "oz", "once": "oz",
    "celsius": "c", "fahrenheit": "f", "kelvin": "k",
    "°c": "c", "°f": "f",
    "litre": "l", "litres": "l", "liter": "l",
    "millilitre": "ml", "millilitres": "ml",
    "gallon": "gal", "gallons": "gal",
    "heure": "h", "heures": "h", "hour": "h", "hours": "h",
    "minute": "min", "minutes": "min",
    "seconde": "s", "secondes": "s", "second": "s", "seconds": "s",
    "jour": "day", "jours": "day", "days": "day",
    "semaine": "week", "semaines": "week", "weeks": "week",
    "mois": "month", "months": "month",
    "an": "year", "ans": "year", "année": "year", "années": "year", "years": "year",
    "octet": "b", "octets": "b", "byte": "b", "bytes": "b",
    "kilo-octet": "kb", "ko": "kb", "kilobyte": "kb",
    "mégaoctet": "mb", "mo": "mb", "megabyte": "mb",
    "gigaoctet": "gb", "go": "gb", "gigabyte": "gb",
    "téraoctet": "tb", "to": "tb", "terabyte": "tb",
    "joule": "j", "joules": "j",
    "kilojoule": "kj", "kilojoules": "kj",
    "calorie": "cal", "calories": "cal",
    "kilocalorie": "kcal", "kilocalories": "kcal",
    "watt-heure": "wh", "kilowatt-heure": "kwh",
}


def _normalize_unit(unit: str) -> str:
    """Normalise le nom d'une unité."""
    u = unit.strip().lower().replace(" ", "")
    return UNIT_ALIASES.get(u, u)


def _find_category(unit: str) -> str | None:
    """Trouve la catégorie d'une unité."""
    for cat, units in UNIT_CONVERSIONS.items():
        if unit in units:
            return cat
    return None


def _convert_temperature(value: float, from_u: str, to_u: str) -> float:
    """Conversion de température (offset non-linéaire)."""
    # Convertir en Celsius d'abord
    if from_u == "c":
        celsius = value
    elif from_u == "f":
        celsius = (value - 32) * 5 / 9
    elif from_u == "k":
        celsius = value - 273.15
    else:
        raise ValueError(f"Unité de température inconnue: {from_u}")

    # Convertir de Celsius vers cible
    if to_u == "c":
        return celsius
    elif to_u == "f":
        return celsius * 9 / 5 + 32
    elif to_u == "k":
        return celsius + 273.15
    else:
        raise ValueError(f"Unité de température inconnue: {to_u}")


def convert_units(value: float, from_unit: str, to_unit: str) -> float:
    """Convertit une valeur entre deux unités."""
    from_u = _normalize_unit(from_unit)
    to_u = _normalize_unit(to_unit)

    if from_u == to_u:
        return value

    # Température — cas spécial
    if from_u in ("c", "f", "k") and to_u in ("c", "f", "k"):
        return _convert_temperature(value, from_u, to_u)

    # Trouver les catégories
    cat_from = _find_category(from_u)
    cat_to = _find_category(to_u)

    if cat_from is None:
        raise ValueError(f"Unité inconnue: {from_unit}")
    if cat_to is None:
        raise ValueError(f"Unité inconnue: {to_unit}")
    if cat_from != cat_to:
        raise ValueError(f"Conversion impossible: {from_unit} ({cat_from}) → {to_unit} ({cat_to})")

    # Conversion via unité de base
    base_value = value * UNIT_CONVERSIONS[cat_from][from_u]
    result = base_value / UNIT_CONVERSIONS[cat_to][to_u]

    return result


# ─────────────────────────────────────────────────────
#  WebSocket handler
# ─────────────────────────────────────────────────────

async def handle_client(ws: Any) -> None:
    peer = ws.remote_address
    log.info("Client connecté: %s", peer)

    # ReadinessProtocol v5
    await ws.send(json.dumps({
        "type": "ready",
        "service": "tools",
        "port": PORT,
    }))

    async for raw in ws:
        # v9 protocol: ping, health, metrics, traces, errors
        v9_resp = await _v9.handle_ws_message(ws, raw)
        if v9_resp is not None:
            await ws.send(v9_resp)
            continue

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await ws.send(json.dumps({"ok": False, "error": "JSON invalide"}))
            continue

        action = msg.get("action", "")
        params = msg.get("params", {})

        if action == "calculate":
            expression = params.get("expression", "").strip()
            if not expression:
                await ws.send(json.dumps({"ok": False, "error": "expression manquante"}))
                continue

            log.info("Calcul: %r", expression)
            try:
                result = safe_calculate(expression)
                await ws.send(json.dumps({
                    "ok": True,
                    "data": {
                        "expression": expression,
                        "result": result,
                    },
                }, ensure_ascii=False))
            except ValueError as exc:
                await ws.send(json.dumps({"ok": False, "error": str(exc)}))

        elif action == "convert":
            try:
                value = float(params.get("value", 0))
                from_unit = params.get("from_unit", "").strip()
                to_unit = params.get("to_unit", "").strip()

                if not from_unit or not to_unit:
                    await ws.send(json.dumps({"ok": False, "error": "from_unit et to_unit requis"}))
                    continue

                log.info("Conversion: %s %s → %s", value, from_unit, to_unit)
                result = convert_units(value, from_unit, to_unit)

                # Arrondir intelligemment
                if isinstance(result, float) and abs(result) > 0.01:
                    result = round(result, 6)

                await ws.send(json.dumps({
                    "ok": True,
                    "data": {
                        "value": value,
                        "from_unit": from_unit,
                        "to_unit": to_unit,
                        "result": result,
                    },
                }, ensure_ascii=False))
            except (ValueError, TypeError) as exc:
                await ws.send(json.dumps({"ok": False, "error": str(exc)}))

        else:
            await ws.send(json.dumps({"ok": False, "error": f"action inconnue: {action}"}))

    log.info("Client déconnecté: %s", peer)


async def main() -> None:
    global _v9
    ensure_single_instance(PORT, "tools_server")
    _v9 = init_v9("tools_server", PORT)
    log.info("Démarrage Tools Server sur le port %d", PORT)

    async with websockets.serve(handle_client, "localhost", PORT,
                                **_v9.ws_serve_kwargs()):
        log.info("Tools Server prêt — ws://localhost:%d", PORT)
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Arrêt Tools Server")
