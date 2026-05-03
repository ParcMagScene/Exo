from __future__ import annotations

import json
import logging
import re
from functools import partial
from pathlib import Path
from typing import Generator

import gruut

from cosyvoice.utils.frontend_utils import is_only_punctuation, split_paragraph

try:
    from tts.french_text_norm import normalize_fr as _pre_normalize_fr
except Exception:  # pragma: no cover
    _pre_normalize_fr = None  # degrade gracieusement si module absent

logger = logging.getLogger("exo.tts")

_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"\s+([,;:.!?])")


class FrenchFrontendWrapper:
    """French text frontend wrapper for CosyVoice2.

    CosyVoice's stock frontend routes non-Chinese text through the English
    wetext normalizer. This wrapper replaces that path with a French pipeline:
    - normalization via gruut fr-fr
    - spoken-form extraction for French text
    - phoneme extraction for observability and integrity checks
    - optional <|fr|> language tags for multilingual tokenizer guidance
    """

    def __init__(self, base_frontend, assets_dir: str | Path, language: str = "fr") -> None:
        self._base = base_frontend
        self.assets_dir = Path(assets_dir)
        self.language = language.lower()
        self._integrity: dict[str, object] = {}
        self._last_phonemes: list[str] = []
        self._last_normalized: list[str] = []
        self._load_integrity()

    def __getattr__(self, name: str):
        return getattr(self._base, name)

    def _load_integrity(self) -> None:
        tokenizer_path = self.assets_dir / "tokenizer_fr.json"
        vocab_path = self.assets_dir / "vocab_fr.json"
        config_path = self.assets_dir / "config_fr.json"
        normalizer_path = self.assets_dir / "normalizer_fr.py"
        phonemizer_path = self.assets_dir / "phonemizer_fr.py"

        integrity = {
            "tokenizer_fr": tokenizer_path.is_file(),
            "vocab_fr": vocab_path.is_file(),
            "config_fr": config_path.is_file(),
            "normalizer_fr": normalizer_path.is_file(),
            "phonemizer_fr": phonemizer_path.is_file(),
        }

        if tokenizer_path.is_file():
            with tokenizer_path.open("r", encoding="utf-8") as handle:
                json.load(handle)
        if vocab_path.is_file():
            with vocab_path.open("r", encoding="utf-8") as handle:
                json.load(handle)
        if config_path.is_file():
            with config_path.open("r", encoding="utf-8") as handle:
                integrity["config"] = json.load(handle)

        self._integrity = integrity

    @property
    def integrity(self) -> dict[str, object]:
        return dict(self._integrity)

    @property
    def last_phonemes(self) -> list[str]:
        return list(self._last_phonemes)

    @property
    def last_normalized(self) -> list[str]:
        return list(self._last_normalized)

    @staticmethod
    def _clean_text(text: str) -> str:
        text = _SPACE_RE.sub(" ", text).strip()
        text = _PUNCT_RE.sub(r"\1", text)
        return text.strip()

    @staticmethod
    def _ensure_language_tag(text: str) -> str:
        stripped = text.lstrip()
        if stripped.startswith("<|fr|>"):
            return stripped
        return f"<|fr|> {stripped}"

    def _gruut_sentences(self, text: str):
        return list(gruut.sentences(text, lang="fr-fr"))

    def _normalize_french_text(self, text: str) -> tuple[list[str], list[str]]:
        # Pre-normalisation FR (chiffres, abreviations, sigles, micro-pauses)
        # AVANT gruut, pour que gruut voie un texte deja en mots francais.
        if _pre_normalize_fr is not None:
            try:
                pre = _pre_normalize_fr(text)
                if pre:
                    text = pre
                    logger.info("FR pre-normalize: %s", text)
            except Exception:  # pragma: no cover
                logger.exception("FR pre-normalize a echoue (non bloquant)")
        sentences = self._gruut_sentences(text)
        normalized: list[str] = []
        phonemes: list[str] = []

        for sentence in sentences:
            spoken = self._clean_text(sentence.text_spoken or sentence.text)
            if spoken:
                normalized.append(spoken)
            sent_phonemes = []
            for word in sentence.words:
                if getattr(word, "phonemes", None):
                    sent_phonemes.extend(word.phonemes)
            if sent_phonemes:
                phonemes.append(" ".join(sent_phonemes))

        if not normalized:
            fallback = self._clean_text(text)
            if fallback:
                normalized = [fallback]

        return normalized, phonemes

    def text_normalize(self, text, split=True, text_frontend=True):
        if isinstance(text, Generator):
            logger.info("get tts_text generator, will skip fr text_normalize")
            return [text]

        if text_frontend is False or text == "":
            return [text] if split else text

        if self.language != "fr":
            return self._base.text_normalize(text, split=split, text_frontend=text_frontend)

        normalized, phonemes = self._normalize_french_text(text)
        self._last_normalized = list(normalized)
        self._last_phonemes = list(phonemes)

        if not split:
            merged = self._clean_text(" ".join(normalized))
            merged = self._ensure_language_tag(merged)
            logger.info("FR normalize: %s", merged)
            if phonemes:
                logger.info("FR phonemes: %s", phonemes[0])
            return merged

        merged = self._clean_text(" ".join(normalized))
        parts = split_paragraph(
            merged,
            partial(self.tokenizer.encode, allowed_special=self.allowed_special),
            "fr",
            token_max_n=80,
            token_min_n=60,
            merge_len=20,
            comma_split=False,
        )
        parts = [self._ensure_language_tag(self._clean_text(part)) for part in parts if not is_only_punctuation(part)]
        logger.info("FR normalize split: %s", parts)
        if phonemes:
            logger.info("FR phonemes: %s", phonemes[0])
        return parts


def install_french_frontend(model, assets_dir: str | Path, language: str = "fr") -> FrenchFrontendWrapper:
    wrapper = FrenchFrontendWrapper(model.frontend, assets_dir=assets_dir, language=language)
    model.frontend = wrapper
    logger.info("CosyVoice2 frontend FR chargé (tokenizer + vocab + normalisation + phonémisation)")
    return wrapper