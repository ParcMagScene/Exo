"""
EXO Mémoire v2 — ConversationMemory

Mémoire conversationnelle : cohérence au sein d'une session.
- Historique des échanges (user/assistant) avec horodatage
- Résumé automatique pour compression
- Détection de thème courant
- Fenêtre glissante configurable

Durée de vie : session uniquement, stocké en STM.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

log = logging.getLogger("memory.conversation")


@dataclass
class ConversationTurn:
    """Un échange dans la conversation."""
    role: str  # "user" ou "assistant"
    text: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "text": self.text,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ConversationTurn:
        return cls(
            role=d["role"],
            text=d["text"],
            timestamp=d.get("timestamp", time.time()),
            metadata=d.get("metadata", {}),
        )


class ConversationMemory:
    """Gère l'historique conversationnel d'une session."""

    MAX_TURNS = 100
    SUMMARY_THRESHOLD = 20  # Résumer après N tours

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self._turns: list[ConversationTurn] = []
        self._summaries: list[str] = []
        self._current_theme: str = ""
        self._started_at: float = time.time()

    def add_turn(self, role: str, text: str,
                 metadata: dict | None = None) -> ConversationTurn:
        """Ajoute un tour de conversation."""
        turn = ConversationTurn(
            role=role,
            text=text,
            metadata=metadata or {},
        )
        self._turns.append(turn)

        # Fenêtre glissante
        if len(self._turns) > self.MAX_TURNS:
            # Archiver les vieux tours en résumé
            old_turns = self._turns[:self.SUMMARY_THRESHOLD]
            summary = self._summarize_turns(old_turns)
            self._summaries.append(summary)
            self._turns = self._turns[self.SUMMARY_THRESHOLD:]

        return turn

    def get_history(self, last_n: int | None = None) -> list[dict]:
        """Retourne l'historique des N derniers tours."""
        turns = self._turns
        if last_n:
            turns = turns[-last_n:]
        return [t.to_dict() for t in turns]

    def get_full_context(self) -> str:
        """Retourne le contexte complet (résumés + historique récent)."""
        parts = []
        if self._summaries:
            parts.append("[Résumé précédent]")
            parts.extend(self._summaries)
            parts.append("")
        for turn in self._turns:
            role_tag = "User" if turn.role == "user" else "Assistant"
            parts.append(f"{role_tag}: {turn.text}")
        return "\n".join(parts)

    def get_summary(self) -> str:
        """Retourne un résumé de la conversation."""
        if self._summaries:
            return " | ".join(self._summaries)
        return self._summarize_turns(self._turns)

    def clear(self) -> None:
        """Vide l'historique de conversation."""
        self._turns.clear()
        self._summaries.clear()
        self._current_theme = ""
        self._started_at = time.time()

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    @property
    def current_theme(self) -> str:
        return self._current_theme

    @current_theme.setter
    def current_theme(self, theme: str) -> None:
        self._current_theme = theme

    def _summarize_turns(self, turns: list[ConversationTurn]) -> str:
        """Résumé simple par extraction des derniers mots-clés."""
        if not turns:
            return ""
        texts = [t.text for t in turns if t.role == "user"]
        if not texts:
            texts = [t.text for t in turns]
        # Résumé basique : concaténation tronquée
        combined = " | ".join(texts)
        if len(combined) > 500:
            combined = combined[:497] + "..."
        return combined

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "turns": [t.to_dict() for t in self._turns],
            "summaries": list(self._summaries),
            "current_theme": self._current_theme,
            "started_at": self._started_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ConversationMemory:
        mem = cls(session_id=d.get("session_id", "default"))
        mem._turns = [ConversationTurn.from_dict(t)
                      for t in d.get("turns", [])]
        mem._summaries = d.get("summaries", [])
        mem._current_theme = d.get("current_theme", "")
        mem._started_at = d.get("started_at", time.time())
        return mem

    def stats(self) -> dict:
        return {
            "session_id": self.session_id,
            "turns": len(self._turns),
            "summaries": len(self._summaries),
            "current_theme": self._current_theme,
            "duration_s": round(time.time() - self._started_at),
        }
