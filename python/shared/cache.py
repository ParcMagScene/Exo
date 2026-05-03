"""Shared LRU phrase cache for TTS servers."""

import hashlib
from typing import Optional


class PhraseCache:
    """LRU cache for short phrases to avoid re-synthesis."""

    def __init__(self, max_entries: int = 64) -> None:
        self._cache: dict[str, bytes] = {}
        self._order: list[str] = []
        self._max = max_entries

    def key(self, text: str, voice: str, lang: str) -> str:
        return hashlib.md5(f"{text}|{voice}|{lang}".encode()).hexdigest()

    def get(self, text: str, voice: str, lang: str) -> Optional[bytes]:
        return self._cache.get(self.key(text, voice, lang))

    def put(self, text: str, voice: str, lang: str, pcm: bytes) -> None:
        if len(text) > 40:
            return
        k = self.key(text, voice, lang)
        if k in self._cache:
            return
        if len(self._cache) >= self._max:
            oldest = self._order.pop(0)
            self._cache.pop(oldest, None)
        self._cache[k] = pcm
        self._order.append(k)
