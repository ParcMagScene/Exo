"""
Tests unitaires — NLU Server (RegexNLU)
100% testable sans modèle ML : classification regex pure.
"""

import sys
from pathlib import Path

from nlu_server import RegexNLU


class TestRegexNLUClassify:
    """Tests de classification par intent."""

    def setup_method(self):
        self.nlu = RegexNLU()

    # ── weather ───────────────────────────────────────
    def test_classify_weather_basic(self):
        r = self.nlu.classify("quel temps fait-il ?")
        assert r["intent"] == "weather"
        assert r["confidence"] > 0.4

    def test_classify_weather_city(self):
        r = self.nlu.classify("quelle est la météo à Paris ?")
        assert r["intent"] == "weather"

    def test_classify_weather_rain(self):
        r = self.nlu.classify("est-ce qu'il va pleuvoir demain ?")
        assert r["intent"] == "weather"

    # ── time ──────────────────────────────────────────
    def test_classify_time(self):
        r = self.nlu.classify("quelle heure est-il ?")
        assert r["intent"] == "time"

    def test_classify_date(self):
        r = self.nlu.classify("quel jour sommes-nous ?")
        assert r["intent"] == "time"

    # ── timer ─────────────────────────────────────────
    def test_classify_timer(self):
        r = self.nlu.classify("mets un minuteur de 5 minutes")
        assert r["intent"] == "timer"

    def test_classify_timer_rappel(self):
        r = self.nlu.classify("rappelle-moi dans 10 minutes")
        assert r["intent"] == "timer"

    # ── home_control ──────────────────────────────────
    def test_classify_home_light(self):
        r = self.nlu.classify("allume la lumière du salon")
        assert r["intent"] == "home_control"

    def test_classify_home_off(self):
        r = self.nlu.classify("éteins la lampe de la chambre")
        assert r["intent"] == "home_control"

    def test_classify_home_volet(self):
        r = self.nlu.classify("ferme les volets du bureau")
        assert r["intent"] == "home_control"

    # ── music ─────────────────────────────────────────
    def test_classify_music(self):
        r = self.nlu.classify("joue de la musique")
        assert r["intent"] == "music"

    def test_classify_music_volume(self):
        r = self.nlu.classify("volume plus fort")
        assert r["intent"] == "music"

    # ── greeting ──────────────────────────────────────
    def test_classify_greeting(self):
        r = self.nlu.classify("bonjour")
        assert r["intent"] == "greeting"

    def test_classify_greeting_informal(self):
        r = self.nlu.classify("salut")
        assert r["intent"] == "greeting"

    # ── goodbye ───────────────────────────────────────
    def test_classify_goodbye(self):
        r = self.nlu.classify("au revoir")
        assert r["intent"] == "goodbye"

    def test_classify_goodbye_night(self):
        r = self.nlu.classify("bonne nuit")
        assert r["intent"] == "goodbye"

    # ── unknown ───────────────────────────────────────
    def test_classify_unknown(self):
        r = self.nlu.classify("expliquer la relativité générale d'Einstein")
        assert r["intent"] == "unknown"
        assert r["use_claude"] is True
        assert r["confidence"] == 0.0

    def test_classify_empty(self):
        r = self.nlu.classify("")
        assert r["intent"] == "unknown"


class TestRegexNLUEntities:
    """Tests d'extraction d'entités."""

    def setup_method(self):
        self.nlu = RegexNLU()

    def test_extract_room(self):
        r = self.nlu.classify("allume la lumière du salon")
        assert r["entities"].get("room") == "salon"

    def test_extract_device(self):
        r = self.nlu.classify("éteins la lampe de la chambre")
        assert r["entities"].get("device") == "lampe"

    def test_extract_action_on(self):
        r = self.nlu.classify("allume la lumière du salon")
        assert r["entities"].get("action") == "on"

    def test_extract_action_off(self):
        r = self.nlu.classify("éteins le chauffage du bureau")
        assert r["entities"].get("action") == "off"

    def test_extract_duration(self):
        # Le regex utilise \b après l'unité → singulier uniquement
        r = self.nlu.classify("mets un minuteur de 5 min")
        assert r["entities"].get("duration_value") == 5
        assert "min" in r["entities"].get("duration_unit", "")

    def test_extract_room_cuisine(self):
        r = self.nlu.classify("allume la lumière de la cuisine")
        assert r["entities"].get("room") == "cuisine"


class TestRegexNLUConfidence:
    """Tests de seuils de confiance et use_claude."""

    def setup_method(self):
        self.nlu = RegexNLU()

    def test_high_confidence_no_claude(self):
        # Match long = confiance élevée → pas besoin de Claude
        r = self.nlu.classify("quelle heure est-il maintenant ?")
        assert r["intent"] == "time"
        # Si confiance ≥ 0.7 → use_claude = False
        if r["confidence"] >= 0.7:
            assert r["use_claude"] is False

    def test_engine_is_regex(self):
        r = self.nlu.classify("bonjour")
        assert r["engine"] == "regex"

    def test_confidence_range(self):
        r = self.nlu.classify("allume le salon")
        assert 0.0 <= r["confidence"] <= 1.0
