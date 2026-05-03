"""
Tests unitaires — Tools Server (Calculatrice + Convertisseur)
Teste le calcul sécurisé et les conversions d'unités.
"""

import sys
import math
from pathlib import Path

from tools_server import safe_calculate, convert_units, _normalize_unit
import pytest


class TestSafeCalculate:
    """Tests de la calculatrice sécurisée."""

    # ── Arithmétique de base ──────────────────────────
    def test_addition(self):
        assert safe_calculate("2 + 3") == 5

    def test_subtraction(self):
        assert safe_calculate("10 - 4") == 6

    def test_multiplication(self):
        assert safe_calculate("6 * 7") == 42

    def test_division(self):
        assert safe_calculate("15 / 3") == 5.0

    def test_power_caret(self):
        assert safe_calculate("2^10") == 1024

    def test_power_double_star(self):
        assert safe_calculate("2**10") == 1024

    def test_modulo(self):
        assert safe_calculate("17 % 5") == 2

    # ── Fonctions mathématiques ───────────────────────
    def test_sqrt(self):
        assert safe_calculate("sqrt(144)") == 12.0

    def test_sin_pi(self):
        result = safe_calculate("sin(pi/2)")
        assert abs(result - 1.0) < 1e-10

    def test_cos_zero(self):
        assert safe_calculate("cos(0)") == 1.0

    def test_log(self):
        result = safe_calculate("log(e)")
        assert abs(result - 1.0) < 1e-10

    def test_factorial(self):
        assert safe_calculate("factorial(5)") == 120

    def test_abs_negative(self):
        assert safe_calculate("abs(-42)") == 42

    def test_ceil(self):
        assert safe_calculate("ceil(3.2)") == 4

    def test_floor(self):
        assert safe_calculate("floor(3.8)") == 3

    # ── Expressions complexes ─────────────────────────
    def test_complex_expression(self):
        result = safe_calculate("sqrt(3**2 + 4**2)")
        assert abs(result - 5.0) < 1e-10

    def test_nested_functions(self):
        result = safe_calculate("round(pi, 2)")
        assert result == 3.14

    # ── Sécurité ──────────────────────────────────────
    def test_reject_import(self):
        with pytest.raises(ValueError, match="interdits"):
            safe_calculate("import os")

    def test_reject_exec(self):
        with pytest.raises(ValueError, match="interdits"):
            safe_calculate("exec('print(1)')")

    def test_reject_dunder(self):
        with pytest.raises(ValueError, match="interdits"):
            safe_calculate("__import__('os')")

    def test_reject_empty(self):
        with pytest.raises(ValueError, match="vide"):
            safe_calculate("")

    def test_reject_too_long(self):
        with pytest.raises(ValueError, match="trop longue"):
            safe_calculate("1+" * 300)

    def test_division_by_zero(self):
        with pytest.raises(ValueError, match="Division par zéro"):
            safe_calculate("1/0")

    # ── Symboles alternatifs ──────────────────────────
    def test_multiply_symbol(self):
        assert safe_calculate("6 × 7") == 42

    def test_divide_symbol(self):
        assert safe_calculate("15 ÷ 3") == 5.0


class TestConvertUnits:
    """Tests du convertisseur d'unités."""

    # ── Longueur ──────────────────────────────────────
    def test_km_to_mi(self):
        result = convert_units(1.0, "km", "mi")
        assert abs(result - 0.621371) < 0.001

    def test_m_to_ft(self):
        result = convert_units(1.0, "m", "ft")
        assert abs(result - 3.28084) < 0.001

    def test_in_to_cm(self):
        result = convert_units(1.0, "in", "cm")
        assert abs(result - 2.54) < 0.001

    # ── Masse ─────────────────────────────────────────
    def test_kg_to_lb(self):
        result = convert_units(1.0, "kg", "lb")
        assert abs(result - 2.20462) < 0.001

    def test_g_to_oz(self):
        result = convert_units(100.0, "g", "oz")
        assert abs(result - 3.5274) < 0.01

    # ── Température ───────────────────────────────────
    def test_celsius_to_fahrenheit(self):
        result = convert_units(100.0, "c", "f")
        assert abs(result - 212.0) < 0.01

    def test_fahrenheit_to_celsius(self):
        result = convert_units(32.0, "f", "c")
        assert abs(result - 0.0) < 0.01

    def test_celsius_to_kelvin(self):
        result = convert_units(0.0, "c", "k")
        assert abs(result - 273.15) < 0.01

    # ── Vitesse ───────────────────────────────────────
    def test_kmh_to_ms(self):
        result = convert_units(100.0, "km/h", "m/s")
        assert abs(result - 27.7778) < 0.01

    def test_mph_to_kmh(self):
        result = convert_units(60.0, "mph", "km/h")
        assert abs(result - 96.5606) < 0.01

    # ── Données ───────────────────────────────────────
    def test_gb_to_mb(self):
        result = convert_units(1.0, "gb", "mb")
        assert abs(result - 1024.0) < 0.01

    # ── Énergie ───────────────────────────────────────
    def test_kcal_to_kj(self):
        result = convert_units(1.0, "kcal", "kj")
        assert abs(result - 4.184) < 0.001

    # ── Identité ──────────────────────────────────────
    def test_same_unit(self):
        assert convert_units(42.0, "m", "m") == 42.0

    # ── Erreurs ───────────────────────────────────────
    def test_unknown_unit(self):
        with pytest.raises(ValueError, match="inconnue"):
            convert_units(1.0, "foo", "bar")

    def test_incompatible_units(self):
        with pytest.raises(ValueError, match="impossible"):
            convert_units(1.0, "km", "kg")


class TestNormalizeUnit:
    """Tests de normalisation des noms d'unités."""

    def test_alias_french(self):
        assert _normalize_unit("kilomètre") == "km"
        assert _normalize_unit("mètres") == "m"
        assert _normalize_unit("livres") == "lb"

    def test_alias_english(self):
        assert _normalize_unit("mile") == "mi"
        assert _normalize_unit("pound") == "lb"
        assert _normalize_unit("inch") == "in"

    def test_celsius_aliases(self):
        assert _normalize_unit("celsius") == "c"
        assert _normalize_unit("°C") == "c"

    def test_data_aliases(self):
        assert _normalize_unit("Go") == "gb"
        assert _normalize_unit("Mo") == "mb"
        assert _normalize_unit("Ko") == "kb"

    def test_already_normalized(self):
        assert _normalize_unit("km") == "km"
        assert _normalize_unit("m/s") == "m/s"
