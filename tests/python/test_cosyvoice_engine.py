"""
test_cosyvoice_engine.py — Unit tests for CosyVoiceEngine
L11 : tests for text normalization, sentence splitting, resampling,
      voice management, and initialization state.
"""

import sys
import types
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ── Stub heavy dependencies before importing the module ──
# torch and cosyvoice are not available in the test venv.
_torch_mock = MagicMock()
_torch_mock.cuda.is_available.return_value = False
_torch_mock.inference_mode.return_value = MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
_torch_mock.Tensor = MagicMock
_torch_mock.int16 = "torch.int16"
sys.modules.setdefault("torch", _torch_mock)

# Now import the engine
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "python" / "tts"))
from cosyvoice_engine import CosyVoiceEngine, COSYVOICE_SAMPLE_RATE, OUTPUT_SAMPLE_RATE


# ═══════════════════════════════════════════════════════
#  Static helpers — pure functions, no model needed
# ═══════════════════════════════════════════════════════


class TestNormalizeText:
    def test_collapse_whitespace(self):
        assert CosyVoiceEngine._normalize_text("  hello   world  ") == "hello world"

    def test_remove_control_chars(self):
        assert CosyVoiceEngine._normalize_text("hello\x00world") == "helloworld"

    def test_preserve_unicode(self):
        assert CosyVoiceEngine._normalize_text("café résumé") == "café résumé"

    def test_empty_string(self):
        assert CosyVoiceEngine._normalize_text("") == ""

    def test_only_whitespace(self):
        assert CosyVoiceEngine._normalize_text("   \t\n  ") == ""

    def test_newlines_collapsed(self):
        assert CosyVoiceEngine._normalize_text("line1\n\nline2") == "line1 line2"


class TestSplitSentences:
    def test_single_sentence(self):
        result = CosyVoiceEngine._split_sentences("Bonjour le monde")
        assert result == ["Bonjour le monde"]

    def test_multiple_sentences(self):
        result = CosyVoiceEngine._split_sentences("Bonjour. Comment ça va? Très bien!")
        assert len(result) == 3
        assert result[0] == "Bonjour."
        assert result[1] == "Comment ça va?"
        assert result[2] == "Très bien!"

    def test_empty_returns_original(self):
        result = CosyVoiceEngine._split_sentences("")
        assert result == [""]

    def test_no_punctuation(self):
        result = CosyVoiceEngine._split_sentences("pas de ponctuation ici")
        assert result == ["pas de ponctuation ici"]

    def test_trailing_period(self):
        result = CosyVoiceEngine._split_sentences("Une seule phrase.")
        assert result == ["Une seule phrase."]


class TestSplitLongText:
    def test_short_text_unchanged(self):
        text = "Court texte."
        result = CosyVoiceEngine._split_long_text(text, 100)
        assert result == [text]

    def test_splits_at_sentence_boundary(self):
        text = "Première phrase. Deuxième phrase. Troisième phrase."
        result = CosyVoiceEngine._split_long_text(text, 30)
        assert len(result) >= 2
        # Each block should be <= max_len or a single unsplittable sentence
        for block in result:
            assert len(block) <= 30 or "." not in block[:-1]

    def test_single_long_sentence(self):
        text = "A" * 200
        result = CosyVoiceEngine._split_long_text(text, 50)
        # Can't split without sentence boundaries → returns as-is
        assert result == [text]

    def test_exact_boundary(self):
        text = "Hello."
        result = CosyVoiceEngine._split_long_text(text, 6)
        assert result == ["Hello."]


class TestResample:
    def test_same_rate_noop(self):
        samples = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
        result = CosyVoiceEngine._resample(samples, 24000, 24000)
        np.testing.assert_array_equal(result, samples)

    def test_upsample_doubles_length(self):
        samples = np.array([0.0, 1.0, 0.0, 1.0], dtype=np.float32)
        result = CosyVoiceEngine._resample(samples, 12000, 24000)
        assert len(result) == 8

    def test_downsample_halves_length(self):
        samples = np.array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0], dtype=np.float32)
        result = CosyVoiceEngine._resample(samples, 48000, 24000)
        assert len(result) == 4

    def test_preserves_dc_signal(self):
        # Constant signal resampled should stay constant
        samples = np.ones(100, dtype=np.float32) * 0.5
        result = CosyVoiceEngine._resample(samples, 16000, 24000)
        np.testing.assert_allclose(result, 0.5, atol=1e-5)


# ═══════════════════════════════════════════════════════
#  Instance methods — engine state
# ═══════════════════════════════════════════════════════


class TestEngineInit:
    def test_default_state(self):
        engine = CosyVoiceEngine()
        assert engine.phase == CosyVoiceEngine.PHASE_INIT
        assert engine.model is None
        assert engine._loaded is False
        assert engine.device == "cpu"
        assert engine.language == "fr"

    def test_custom_voice_and_lang(self):
        engine = CosyVoiceEngine(voice="test_voice", lang="en")
        assert engine.voice_name == "test_voice"
        assert engine.language == "en"

    def test_phases_constants(self):
        assert CosyVoiceEngine.PHASE_INIT == "ready_init"
        assert CosyVoiceEngine.PHASE_LOADING == "ready_loading"
        assert CosyVoiceEngine.PHASE_WARMUP == "ready_warmup"
        assert CosyVoiceEngine.PHASE_ONLINE == "ready_online"


class TestSetVoice:
    def test_set_known_speaker(self):
        engine = CosyVoiceEngine()
        engine._available_spks = ["alice", "bob", "exo_default"]
        engine._voice_prompts = {}
        result = engine.set_voice("alice")
        assert result is True
        assert engine.voice_name == "alice"

    def test_set_unknown_speaker(self):
        engine = CosyVoiceEngine()
        engine._available_spks = ["alice", "bob"]
        engine._voice_prompts = {}
        result = engine.set_voice("unknown_voice")
        assert result is False

    def test_case_insensitive_fallback(self):
        engine = CosyVoiceEngine()
        engine._available_spks = ["Alice", "Bob"]
        engine._voice_prompts = {}
        result = engine.set_voice("alice")
        assert result is True
        assert engine.voice_name == "Alice"


class TestListVoices:
    def test_returns_sorted(self):
        engine = CosyVoiceEngine()
        engine._available_spks = ["charlie", "alice", "bob"]
        assert engine.list_voices() == ["alice", "bob", "charlie"]

    def test_empty_list(self):
        engine = CosyVoiceEngine()
        engine._available_spks = []
        assert engine.list_voices() == []


class TestSetLanguage:
    def test_set_language(self):
        engine = CosyVoiceEngine()
        engine.set_language("en")
        assert engine.language == "en"


class TestSynthesizeGuards:
    def test_synthesize_stream_not_loaded_raises(self):
        engine = CosyVoiceEngine()
        engine._loaded = False
        with pytest.raises(RuntimeError, match="not loaded"):
            list(engine.synthesize_stream("test"))

    def test_synthesize_stream_empty_text_noop(self):
        engine = CosyVoiceEngine()
        engine._loaded = True
        engine.model = MagicMock()
        result = list(engine.synthesize_stream(""))
        assert result == []

    def test_synthesize_stream_whitespace_only_noop(self):
        engine = CosyVoiceEngine()
        engine._loaded = True
        engine.model = MagicMock()
        result = list(engine.synthesize_stream("   "))
        assert result == []


class TestAudioConstants:
    def test_sample_rates(self):
        assert COSYVOICE_SAMPLE_RATE == 24000
        assert OUTPUT_SAMPLE_RATE == 24000
