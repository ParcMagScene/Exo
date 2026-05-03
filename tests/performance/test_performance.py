"""
Tests de performance — benchmarks latence pipeline
Exécuter avec : pytest tests/performance/ -m performance -v
"""

import time
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.performance


class TestNLUPerformance:
    """Benchmarks de latence NLU (régression de performance)."""

    def setup_method(self):
        from nlu_server import RegexNLU
        self.nlu = RegexNLU()

    def test_classify_latency_under_1ms(self):
        """La classification regex doit prendre < 1ms."""
        text = "allume la lumière du salon"
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            self.nlu.classify(text)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 1.0, f"NLU classify too slow: {avg_ms:.3f}ms (limit: 1ms)"

    def test_classify_throughput(self):
        """Le NLU doit traiter > 5000 classifications/seconde."""
        texts = [
            "allume la lumière du salon",
            "quelle heure est-il ?",
            "mets un minuteur de 5 minutes",
            "bonjour comment ça va",
            "joue de la musique",
        ]

        iterations = 2000
        start = time.perf_counter()
        for i in range(iterations):
            self.nlu.classify(texts[i % len(texts)])
        elapsed = time.perf_counter() - start

        throughput = iterations / elapsed
        assert throughput > 5000, f"NLU throughput too low: {throughput:.0f}/s (limit: 5000/s)"

    def test_entity_extraction_latency(self):
        """L'extraction d'entités ne doit pas ajouter > 0.5ms."""
        text = "éteins la lampe de la cuisine dans 5 minutes"
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            r = self.nlu.classify(text)
            _ = r["entities"]
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 1.5, f"Entity extraction too slow: {avg_ms:.3f}ms"

    def test_unknown_intent_latency(self):
        """Même pour un intent inconnu, < 1ms."""
        text = "expliquer la mécanique quantique en termes simples"
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            self.nlu.classify(text)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 1.0, f"Unknown intent too slow: {avg_ms:.3f}ms"
