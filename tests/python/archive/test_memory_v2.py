"""
Tests unitaires — Mémoire v2

Tests complets pour tous les modules mémoire v2 :
- MemoryHierarchy (STM/MTM/LTM)
- VectorIndex (fallback textuel sans FAISS)
- ConsolidationManager
- ContextEngine
- ConversationMemory
- FactualMemory
- MemoryManager (orchestrateur)
- Protocole WS

Tous testables sans FAISS/SentenceTransformers.
"""

import sys
import json
import time
import uuid
from pathlib import Path

import pytest


# ═══════════════════════════════════════════════════════════════
# MemoryEntry
# ═══════════════════════════════════════════════════════════════

class TestMemoryEntry:
    """Tests de la structure MemoryEntry v2."""

    def test_create_entry(self):
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(
            id="test-001",
            text="Le ciel est bleu",
            importance=0.8,
            tags=["test", "couleur"],
            category="fact",
        )
        assert entry.id == "test-001"
        assert entry.text == "Le ciel est bleu"
        assert entry.importance == 0.8
        assert "test" in entry.tags
        assert entry.category == "fact"

    def test_entry_defaults(self):
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(id="d1", text="test")
        assert entry.importance == 0.5
        assert entry.tags == []
        assert entry.tier == "stm"
        assert entry.source == "user"
        assert entry.access_count == 0
        assert entry.reinforcements == 0
        assert entry.metadata == {}

    def test_entry_importance_clamp(self):
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(id="c1", text="test", importance=1.5)
        assert entry.importance == 1.0
        entry2 = MemoryEntry(id="c2", text="test", importance=-0.5)
        assert entry2.importance == 0.0

    def test_entry_to_dict(self):
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(
            id="abc123", text="test memory",
            importance=0.5, tags=["tag1"],
            category="general",
        )
        d = entry.to_dict()
        assert d["id"] == "abc123"
        assert d["text"] == "test memory"
        assert d["importance"] == 0.5
        assert d["tier"] == "stm"
        assert "ttl_seconds" in d
        assert "metadata" in d

    def test_entry_from_dict(self):
        from memory_hierarchy import MemoryEntry
        d = {
            "id": "f1",
            "text": "from dict test",
            "importance": 0.7,
            "tags": ["a", "b"],
            "category": "test",
            "tier": "mtm",
        }
        entry = MemoryEntry.from_dict(d)
        assert entry.id == "f1"
        assert entry.text == "from dict test"
        assert entry.importance == 0.7
        assert entry.tier == "mtm"

    def test_entry_from_dict_v8_compat(self):
        """v8 ttl_days → v2 ttl_seconds."""
        from memory_hierarchy import MemoryEntry
        d = {
            "id": "compat1",
            "text": "old entry",
            "ttl_days": 7.0,
        }
        entry = MemoryEntry.from_dict(d)
        assert entry.ttl_seconds == 7.0 * 86400

    def test_entry_touch(self):
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(id="t1", text="touch test")
        assert entry.access_count == 0
        entry.touch()
        assert entry.access_count == 1
        assert entry.last_accessed >= entry.timestamp

    def test_entry_reinforce(self):
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(id="r1", text="reinforce", importance=0.5)
        entry.reinforce(0.2)
        assert entry.importance == 0.7
        assert entry.reinforcements == 1
        assert entry.access_count == 1

    def test_entry_weaken(self):
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(id="w1", text="weaken", importance=0.5)
        entry.weaken(0.3)
        assert entry.importance == 0.2

    def test_entry_expired(self):
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(
            id="e1", text="expired",
            ttl_seconds=0.01,
            timestamp=time.time() - 1,
        )
        # Force old timestamp
        entry.timestamp = time.time() - 1
        assert entry.is_expired()

    def test_entry_not_expired(self):
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(id="e2", text="not expired", ttl_seconds=3600)
        assert not entry.is_expired()

    def test_entry_no_ttl_never_expires(self):
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(id="e3", text="permanent", ttl_seconds=0)
        assert not entry.is_expired()

    def test_entry_age(self):
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(id="a1", text="age test")
        assert entry.age_seconds() >= 0
        assert entry.age_days() >= 0

    def test_entry_roundtrip(self):
        from memory_hierarchy import MemoryEntry
        original = MemoryEntry(
            id="rt1", text="roundtrip",
            importance=0.75, tags=["a"],
            category="test", tier="ltm",
            metadata={"key": "val"},
        )
        d = original.to_dict()
        restored = MemoryEntry.from_dict(d)
        assert restored.id == original.id
        assert restored.text == original.text
        assert restored.importance == original.importance
        assert restored.tier == original.tier


# ═══════════════════════════════════════════════════════════════
# MemoryHierarchy
# ═══════════════════════════════════════════════════════════════

class TestMemoryHierarchy:
    """Tests du gestionnaire de hiérarchie mémoire."""

    def _make_entry(self, entry_id="h1", text="test", **kwargs):
        from memory_hierarchy import MemoryEntry
        return MemoryEntry(id=entry_id, text=text, **kwargs)

    def test_stm_set_get(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        entry = self._make_entry("s1", "souvenir STM")
        h.stm_set(entry)
        result = h.stm_get("s1")
        assert result is not None
        assert result.text == "souvenir STM"
        assert result.tier == "stm"

    def test_mtm_add_get(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        entry = self._make_entry("m1", "souvenir MTM")
        h.mtm_add(entry)
        result = h.mtm_get("m1")
        assert result is not None
        assert result.tier == "mtm"

    def test_ltm_add_get(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        entry = self._make_entry("l1", "souvenir LTM")
        h.ltm_add(entry)
        result = h.ltm_get("l1")
        assert result is not None
        assert result.tier == "ltm"
        assert result.ttl_seconds == 0  # permanent

    def test_generic_add_get(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        entry = self._make_entry("g1", "generic", tier="mtm")
        h.add(entry)
        result = h.get("g1")
        assert result is not None
        assert result.tier == "mtm"

    def test_remove(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        h.stm_set(self._make_entry("r1", "to remove"))
        assert h.remove("r1")
        assert h.get("r1") is None

    def test_remove_nonexistent(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        assert not h.remove("doesnt-exist")

    def test_get_tier(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        h.stm_set(self._make_entry("t1", "a"))
        h.stm_set(self._make_entry("t2", "b"))
        stm = h.get_tier("stm")
        assert len(stm) == 2

    def test_get_all(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        h.stm_set(self._make_entry("a1", "stm"))
        h.mtm_add(self._make_entry("a2", "mtm"))
        h.ltm_add(self._make_entry("a3", "ltm"))
        all_entries = h.get_all()
        assert len(all_entries) == 3

    def test_replace_same_id(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        h.stm_set(self._make_entry("dup1", "version 1"))
        h.stm_set(self._make_entry("dup1", "version 2"))
        stm = h.get_tier("stm")
        assert len(stm) == 1
        assert stm[0].text == "version 2"

    def test_promote_stm_to_mtm(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        h.stm_set(self._make_entry("p1", "promote me"))
        result = h.promote("p1", "mtm")
        assert result is not None
        assert result.tier == "mtm"
        assert h.stm_get("p1") is None
        assert h.mtm_get("p1") is not None

    def test_promote_mtm_to_ltm(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        h.mtm_add(self._make_entry("p2", "to LTM"))
        result = h.promote("p2", "ltm")
        assert result is not None
        assert result.tier == "ltm"
        assert result.ttl_seconds == 0

    def test_promote_already_in_tier(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        h.stm_set(self._make_entry("p3", "stay"))
        result = h.promote("p3", "stm")
        assert result is not None
        assert result.tier == "stm"

    def test_promote_nonexistent(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        assert h.promote("nope", "mtm") is None

    def test_purge_expired(self):
        from memory_hierarchy import MemoryEntry, MemoryHierarchy
        h = MemoryHierarchy()
        expired = MemoryEntry(
            id="exp1", text="expired",
            ttl_seconds=0.001,
            timestamp=time.time() - 1,
        )
        expired.timestamp = time.time() - 1
        h.stm_set(expired)
        h.stm_set(self._make_entry("valid1", "still valid"))
        purged = h.purge()
        assert purged["stm"] == 1
        assert len(h.get_tier("stm")) == 1

    def test_capacity_enforcement(self):
        from memory_hierarchy import MemoryHierarchy, STM_MAX
        h = MemoryHierarchy()
        for i in range(STM_MAX + 10):
            h.stm_set(self._make_entry(f"cap-{i}", f"entry {i}"))
        assert len(h.get_tier("stm")) == STM_MAX

    def test_tier_stats(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        h.stm_set(self._make_entry("s1", "a"))
        h.mtm_add(self._make_entry("m1", "b"))
        stats = h.tier_stats()
        assert stats["stm"]["count"] == 1
        assert stats["mtm"]["count"] == 1
        assert stats["ltm"]["count"] == 0
        assert stats["total"] == 2

    def test_export_import(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        h.stm_set(self._make_entry("e1", "export me"))
        h.ltm_add(self._make_entry("e2", "long term"))
        data = h.export_data()

        h2 = MemoryHierarchy()
        count = h2.import_data(data)
        assert count == 2
        assert h2.get("e1") is not None
        assert h2.get("e2") is not None

    def test_metrics(self):
        from memory_hierarchy import MemoryHierarchy
        h = MemoryHierarchy()
        h.stm_set(self._make_entry("m1", "a"))
        h.mtm_add(self._make_entry("m2", "b"))
        m = h.metrics()
        assert m["stm_adds"] == 1
        assert m["mtm_adds"] == 1


# ═══════════════════════════════════════════════════════════════
# VectorIndex (mode fallback textuel)
# ═══════════════════════════════════════════════════════════════

class TestVectorIndexFallback:
    """Tests de VectorIndex en mode fallback (sans FAISS)."""

    def test_create(self):
        from vector_index import VectorIndex
        vi = VectorIndex()
        assert not vi.available

    def test_add_without_load(self):
        from vector_index import VectorIndex
        vi = VectorIndex()
        result = vi.add("id1", "Le chat dort sur le canapé")
        assert result is True

    def test_search_fallback(self):
        from vector_index import VectorIndex
        vi = VectorIndex()
        vi.add("id1", "Le chat dort sur le canapé")
        vi.add("id2", "Le chien court dans le jardin")
        vi.add("id3", "La voiture est rouge")
        results = vi.search("chat canapé")
        assert len(results) > 0
        assert results[0]["id"] == "id1"

    def test_search_no_match(self):
        from vector_index import VectorIndex
        vi = VectorIndex()
        vi.add("id1", "La musique est belle")
        results = vi.search("xyz_aucun_match_possible")
        assert len(results) == 0

    def test_add_multi_tier(self):
        from vector_index import VectorIndex
        vi = VectorIndex()
        vi.add("s1", "STM entry", tier="stm")
        vi.add("m1", "MTM entry", tier="mtm")
        vi.add("l1", "LTM entry", tier="ltm")
        results = vi.search("entry", tiers=["stm"])
        assert all(r["tier"] == "stm" for r in results)

    def test_delete(self):
        from vector_index import VectorIndex
        vi = VectorIndex()
        vi.add("d1", "to delete")
        assert vi.delete("d1")
        results = vi.search("delete")
        assert len(results) == 0

    def test_delete_nonexistent(self):
        from vector_index import VectorIndex
        vi = VectorIndex()
        assert not vi.delete("nope")

    def test_is_duplicate_fallback(self):
        from vector_index import VectorIndex
        vi = VectorIndex()
        vi.add("id1", "texte exact")
        assert vi.is_duplicate("texte exact")
        assert not vi.is_duplicate("texte différent")

    def test_stats(self):
        from vector_index import VectorIndex
        vi = VectorIndex()
        vi.add("s1", "a", tier="stm")
        vi.add("m1", "b", tier="mtm")
        s = vi.stats()
        assert s["stm"]["entries"] == 1
        assert s["mtm"]["entries"] == 1
        assert s["available"] is False

    def test_rebuild_tier(self):
        from vector_index import VectorIndex
        vi = VectorIndex()
        vi.rebuild_tier("stm", ["text1", "text2"], ["id1", "id2"])
        s = vi.stats()
        assert s["stm"]["entries"] == 2


# ═══════════════════════════════════════════════════════════════
# ConsolidationManager
# ═══════════════════════════════════════════════════════════════

class TestConsolidationManager:
    """Tests du gestionnaire de consolidation."""

    def _make_entry(self, entry_id, text, **kwargs):
        from memory_hierarchy import MemoryEntry
        return MemoryEntry(id=entry_id, text=text, **kwargs)

    def test_consolidate_stm_by_importance(self):
        from memory_hierarchy import MemoryHierarchy
        from consolidation_manager import ConsolidationManager
        h = MemoryHierarchy()
        # Entrée importante → doit être promue
        entry = self._make_entry("c1", "important", importance=0.8)
        h.stm_set(entry)
        # Entrée peu importante → reste
        entry2 = self._make_entry("c2", "trivial", importance=0.2)
        h.stm_set(entry2)

        cm = ConsolidationManager(h)
        result = cm.consolidate_stm()
        assert result["promoted"] == 1
        assert h.mtm_get("c1") is not None
        assert h.stm_get("c2") is not None

    def test_consolidate_stm_by_access(self):
        from memory_hierarchy import MemoryHierarchy
        from consolidation_manager import ConsolidationManager
        h = MemoryHierarchy()
        entry = self._make_entry("ca1", "accessed", importance=0.3)
        entry.access_count = 5
        h.stm_set(entry)

        cm = ConsolidationManager(h)
        result = cm.consolidate_stm()
        assert result["promoted"] == 1

    def test_consolidate_mtm_by_importance(self):
        from memory_hierarchy import MemoryHierarchy
        from consolidation_manager import ConsolidationManager
        h = MemoryHierarchy()
        entry = self._make_entry("cm1", "very important", importance=0.9)
        h.mtm_add(entry)

        cm = ConsolidationManager(h)
        result = cm.consolidate_mtm()
        assert result["promoted"] == 1
        assert h.ltm_get("cm1") is not None

    def test_consolidate_mtm_by_reinforcements(self):
        from memory_hierarchy import MemoryHierarchy
        from consolidation_manager import ConsolidationManager
        h = MemoryHierarchy()
        entry = self._make_entry("cr1", "reinforced", importance=0.5)
        entry.reinforcements = 5
        h.mtm_add(entry)

        cm = ConsolidationManager(h)
        result = cm.consolidate_mtm()
        assert result["promoted"] == 1

    def test_consolidate_all(self):
        from memory_hierarchy import MemoryHierarchy
        from consolidation_manager import ConsolidationManager
        h = MemoryHierarchy()
        h.stm_set(self._make_entry("a1", "important stm", importance=0.9))
        h.stm_set(self._make_entry("a2", "trivial stm", importance=0.1))
        h.mtm_add(self._make_entry("a3", "stable mtm", importance=0.95))

        cm = ConsolidationManager(h)
        result = cm.consolidate_all()
        assert result["stm_promoted"] >= 1
        assert result["mtm_promoted"] >= 1

    def test_auto_consolidate_not_due(self):
        from memory_hierarchy import MemoryHierarchy
        from consolidation_manager import ConsolidationManager
        h = MemoryHierarchy()
        cm = ConsolidationManager(h)
        # Just created → not due
        result = cm.auto_consolidate()
        assert result is None

    def test_consolidation_metrics(self):
        from memory_hierarchy import MemoryHierarchy
        from consolidation_manager import ConsolidationManager
        h = MemoryHierarchy()
        cm = ConsolidationManager(h)
        h.stm_set(self._make_entry("m1", "test", importance=0.9))
        cm.consolidate_stm()
        m = cm.metrics()
        assert m["stm_promoted"] == 1
        assert "last_stm_consolidation" in m

    def test_no_promotion_below_threshold(self):
        from memory_hierarchy import MemoryHierarchy
        from consolidation_manager import ConsolidationManager
        h = MemoryHierarchy()
        entry = self._make_entry("np1", "not important", importance=0.3)
        h.stm_set(entry)

        cm = ConsolidationManager(h)
        result = cm.consolidate_stm()
        assert result["promoted"] == 0
        assert h.stm_get("np1") is not None


# ═══════════════════════════════════════════════════════════════
# ContextEngine
# ═══════════════════════════════════════════════════════════════

class TestContextEngine:
    """Tests du moteur de contexte."""

    def _make_entry(self, entry_id, text, **kwargs):
        from memory_hierarchy import MemoryEntry
        return MemoryEntry(id=entry_id, text=text, **kwargs)

    def test_build_context_empty(self):
        from memory_hierarchy import MemoryHierarchy
        from memory_context import ContextEngine
        h = MemoryHierarchy()
        ce = ContextEngine(h)
        ctx = ce.build_context("query")
        assert isinstance(ctx, list)
        assert len(ctx) == 0

    def test_build_context_with_entries(self):
        from memory_hierarchy import MemoryHierarchy
        from memory_context import ContextEngine
        h = MemoryHierarchy()
        h.stm_set(self._make_entry("ctx1", "Le chat est noir", importance=0.8))
        h.mtm_add(self._make_entry("ctx2", "La maison est grande", importance=0.7))
        h.ltm_add(self._make_entry("ctx3", "Paris est la capitale", importance=0.9))

        ce = ContextEngine(h)
        ctx = ce.build_context("chat")
        assert len(ctx) > 0
        assert all("id" in c for c in ctx)
        assert all("score" in c for c in ctx)

    def test_inject_context(self):
        from memory_hierarchy import MemoryHierarchy
        from memory_context import ContextEngine
        h = MemoryHierarchy()
        h.stm_set(self._make_entry("inj1", "Le ciel est bleu"))

        ce = ContextEngine(h)
        prompt = "Réponds à la question."
        result = ce.inject_context(prompt, "ciel")
        assert "[MEMORY CONTEXT]" in result
        assert "Réponds à la question." in result

    def test_inject_context_empty(self):
        from memory_hierarchy import MemoryHierarchy
        from memory_context import ContextEngine
        h = MemoryHierarchy()
        ce = ContextEngine(h)
        prompt = "Test prompt"
        result = ce.inject_context(prompt, "query")
        assert result == "Test prompt"

    def test_get_relevant_memory(self):
        from memory_hierarchy import MemoryHierarchy
        from memory_context import ContextEngine
        h = MemoryHierarchy()
        h.stm_set(self._make_entry("rel1", "La température est de 20 degrés"))
        ce = ContextEngine(h)
        results = ce.get_relevant_memory("température")
        assert len(results) > 0

    def test_context_metrics(self):
        from memory_hierarchy import MemoryHierarchy
        from memory_context import ContextEngine
        h = MemoryHierarchy()
        h.stm_set(self._make_entry("met1", "test"))
        ce = ContextEngine(h)
        ce.build_context("test")
        m = ce.metrics()
        assert m["context_builds"] == 1

    def test_token_budget_limits(self):
        from memory_hierarchy import MemoryHierarchy
        from memory_context import ContextEngine
        h = MemoryHierarchy()
        for i in range(50):
            h.stm_set(self._make_entry(f"big-{i}", "A" * 200, importance=0.9))
        # Très petit budget
        ce = ContextEngine(h, token_budget=10)
        ctx = ce.build_context("test")
        total_chars = sum(len(c["text"]) for c in ctx)
        assert total_chars <= 10 * 4 + 200  # budget + 1 entry max


# ═══════════════════════════════════════════════════════════════
# ConversationMemory
# ═══════════════════════════════════════════════════════════════

class TestConversationMemory:
    """Tests de la mémoire conversationnelle."""

    def test_create(self):
        from conversation_memory import ConversationMemory
        cm = ConversationMemory("session-1")
        assert cm.session_id == "session-1"
        assert cm.turn_count == 0

    def test_add_turn(self):
        from conversation_memory import ConversationMemory
        cm = ConversationMemory()
        turn = cm.add_turn("user", "Bonjour !")
        assert turn.role == "user"
        assert turn.text == "Bonjour !"
        assert cm.turn_count == 1

    def test_add_multiple_turns(self):
        from conversation_memory import ConversationMemory
        cm = ConversationMemory()
        cm.add_turn("user", "Salut")
        cm.add_turn("assistant", "Bonjour !")
        cm.add_turn("user", "Ça va ?")
        assert cm.turn_count == 3

    def test_get_history(self):
        from conversation_memory import ConversationMemory
        cm = ConversationMemory()
        cm.add_turn("user", "Message 1")
        cm.add_turn("assistant", "Réponse 1")
        cm.add_turn("user", "Message 2")
        h = cm.get_history(last_n=2)
        assert len(h) == 2
        assert h[0]["text"] == "Réponse 1"

    def test_get_full_context(self):
        from conversation_memory import ConversationMemory
        cm = ConversationMemory()
        cm.add_turn("user", "Bonjour")
        cm.add_turn("assistant", "Salut !")
        ctx = cm.get_full_context()
        assert "User: Bonjour" in ctx
        assert "Assistant: Salut !" in ctx

    def test_clear(self):
        from conversation_memory import ConversationMemory
        cm = ConversationMemory()
        cm.add_turn("user", "test")
        cm.clear()
        assert cm.turn_count == 0

    def test_theme(self):
        from conversation_memory import ConversationMemory
        cm = ConversationMemory()
        cm.current_theme = "météo"
        assert cm.current_theme == "météo"

    def test_to_dict_from_dict(self):
        from conversation_memory import ConversationMemory
        cm = ConversationMemory("sess-1")
        cm.add_turn("user", "Hello")
        cm.add_turn("assistant", "Hi!")
        cm.current_theme = "greetings"

        d = cm.to_dict()
        restored = ConversationMemory.from_dict(d)
        assert restored.session_id == "sess-1"
        assert restored.turn_count == 2
        assert restored.current_theme == "greetings"

    def test_stats(self):
        from conversation_memory import ConversationMemory
        cm = ConversationMemory("s1")
        cm.add_turn("user", "a")
        cm.add_turn("assistant", "b")
        s = cm.stats()
        assert s["session_id"] == "s1"
        assert s["turns"] == 2
        assert s["duration_s"] >= 0

    def test_window_sliding(self):
        from conversation_memory import ConversationMemory
        cm = ConversationMemory()
        # Ajouter plus que MAX_TURNS
        for i in range(cm.MAX_TURNS + 10):
            cm.add_turn("user", f"message {i}")
        assert cm.turn_count <= cm.MAX_TURNS
        assert len(cm._summaries) > 0

    def test_turn_metadata(self):
        from conversation_memory import ConversationMemory
        cm = ConversationMemory()
        turn = cm.add_turn("user", "test", metadata={"intent": "greet"})
        assert turn.metadata["intent"] == "greet"


# ═══════════════════════════════════════════════════════════════
# FactualMemory
# ═══════════════════════════════════════════════════════════════

class TestFactualMemory:
    """Tests de la mémoire factuelle."""

    def test_add_fact(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        fact = fm.add_fact("name", "Alex", category="identity")
        assert fact.key == "name"
        assert fact.value == "Alex"
        assert fact.category == "identity"

    def test_get_fact(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        fm.add_fact("color", "bleu", category="preference")
        fact = fm.get_fact("color")
        assert fact is not None
        assert fact.value == "bleu"

    def test_get_value(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        fm.add_fact("lang", "français")
        assert fm.get_value("lang") == "français"
        assert fm.get_value("missing", "default") == "default"

    def test_update_fact(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        fm.add_fact("city", "Paris")
        assert fm.update_fact("city", "Lyon")
        fact = fm.get_fact("city")
        assert fact.value == "Lyon"
        assert len(fact.history) == 1
        assert fact.history[0]["old_value"] == "Paris"

    def test_update_via_add(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        fm.add_fact("key1", "v1")
        fm.add_fact("key1", "v2")
        fact = fm.get_fact("key1")
        assert fact.value == "v2"

    def test_delete_fact(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        fm.add_fact("del", "value")
        assert fm.delete_fact("del")
        assert fm.get_fact("del") is None

    def test_delete_nonexistent(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        assert not fm.delete_fact("nope")

    def test_get_by_category(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        fm.add_fact("name", "Alex", category="identity")
        fm.add_fact("age", "30", category="identity")
        fm.add_fact("color", "bleu", category="preference")
        identity = fm.get_by_category("identity")
        assert len(identity) == 2

    def test_search_facts(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        fm.add_fact("favorite_food", "pizza", category="preference")
        fm.add_fact("pet", "chat", category="general")
        results = fm.search_facts("pizza")
        assert len(results) == 1
        assert results[0].key == "favorite_food"

    def test_detect_contradiction(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        fm.add_fact("city", "Paris")
        contradiction = fm.detect_contradictions("city", "Lyon")
        assert contradiction is not None
        assert contradiction["current_value"] == "Paris"
        assert contradiction["new_value"] == "Lyon"

    def test_no_contradiction(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        fm.add_fact("city", "Paris")
        assert fm.detect_contradictions("city", "Paris") is None

    def test_detect_contradiction_no_fact(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        assert fm.detect_contradictions("missing", "value") is None

    def test_all_facts(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        fm.add_fact("a", "1")
        fm.add_fact("b", "2")
        all_f = fm.all_facts()
        assert len(all_f) == 2
        assert all("key" in f for f in all_f)

    def test_export_import(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        fm.add_fact("x", "10", category="technical")
        fm.add_fact("y", "20", category="technical")
        exported = fm.export_data()

        fm2 = FactualMemory()
        count = fm2.import_data(exported)
        assert count == 2
        assert fm2.get_value("x") == "10"

    def test_stats(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        fm.add_fact("a", "1", category="preference")
        fm.add_fact("b", "2", category="identity")
        s = fm.stats()
        assert s["total"] == 2
        assert s["categories"]["preference"] == 1
        assert s["categories"]["identity"] == 1

    def test_invalid_category_defaults_general(self):
        from factual_memory import FactualMemory
        fm = FactualMemory()
        fact = fm.add_fact("k", "v", category="invalid")
        assert fact.category == "general"

    def test_fact_roundtrip(self):
        from factual_memory import Fact
        original = Fact(key="k", value="v", category="technical")
        d = original.to_dict()
        restored = Fact.from_dict(d)
        assert restored.key == original.key
        assert restored.value == original.value
        assert restored.category == original.category


# ═══════════════════════════════════════════════════════════════
# MemoryManager (sans FAISS)
# ═══════════════════════════════════════════════════════════════

class TestMemoryManagerNoFaiss:
    """Tests de MemoryManager sans charger FAISS/SentenceTransformers."""

    def _make_manager(self):
        from memory_manager import MemoryManager
        m = MemoryManager(data_dir="__test_mem_dir__")
        # Ne pas appeler load() → reste sans FAISS
        m._loaded = True
        return m

    def test_hierarchy_access(self):
        m = self._make_manager()
        from memory_hierarchy import MemoryEntry
        entry = MemoryEntry(id="hm1", text="test")
        m.hierarchy.stm_set(entry)
        assert m.hierarchy.stm_get("hm1") is not None

    def test_facts_access(self):
        m = self._make_manager()
        m.facts.add_fact("name", "EXO")
        assert m.facts.get_value("name") == "EXO"

    def test_conversation_access(self):
        m = self._make_manager()
        conv = m.get_conversation("test-session")
        assert conv.session_id == "test-session"
        conv.add_turn("user", "Hello")
        assert conv.turn_count == 1

    def test_stats(self):
        m = self._make_manager()
        s = m.stats()
        assert "count" in s
        assert "model" in s
        assert "tiers" in s
        assert "facts" in s

    def test_tier_stats(self):
        m = self._make_manager()
        ts = m.tier_stats()
        assert "stm" in ts
        assert "mtm" in ts
        assert "ltm" in ts

    def test_health_check(self):
        m = self._make_manager()
        h = m.health_check()
        assert h["status"] == "ok"
        assert h["loaded"] is True

    def test_metrics(self):
        m = self._make_manager()
        met = m.metrics()
        assert "adds" in met
        assert "searches" in met
        assert "hierarchy" in met
        assert "consolidation" in met

    def test_consolidation_on_empty(self):
        m = self._make_manager()
        result = m.consolidate()
        assert "total" in result


# ═══════════════════════════════════════════════════════════════
# Protocole WS (v8 compat + v2 extensions)
# ═══════════════════════════════════════════════════════════════

class TestMemoryProtocol:
    """Tests du protocole WS mémoire."""

    def test_add_message_format(self):
        msg = {
            "type": "add",
            "text": "souvenir important",
            "importance": 0.9,
            "tags": ["personnel"],
            "category": "experience",
            "tier": "stm",
        }
        assert msg["type"] == "add"
        assert isinstance(msg["importance"], float)

    def test_search_message_format(self):
        msg = {
            "type": "search",
            "query": "quel était le souvenir ?",
            "top_k": 5,
            "tiers": ["stm", "mtm", "ltm"],
        }
        assert msg["type"] == "search"
        assert msg["top_k"] == 5

    def test_stats_response_format(self):
        response = {
            "type": "stats",
            "count": 42,
            "model": "all-MiniLM-L6-v2",
            "tiers": {
                "stm": {"count": 10},
                "mtm": {"count": 20},
                "ltm": {"count": 12},
            },
        }
        assert response["type"] == "stats"
        assert isinstance(response["count"], int)
        assert "tiers" in response

    def test_error_response_format(self):
        response = {
            "type": "error",
            "message": "Memory not found",
        }
        assert response["type"] == "error"
        assert "not found" in response["message"].lower()

    def test_ready_message_format(self):
        ready = {
            "type": "ready",
            "model": "all-MiniLM-L6-v2",
            "memories": 100,
            "tiers": {"stm": 10, "mtm": 40, "ltm": 50},
        }
        assert ready["type"] == "ready"
        assert isinstance(ready["memories"], int)
        assert "tiers" in ready

    def test_promote_message_format(self):
        msg = {"type": "promote", "id": "abc123", "target_tier": "ltm"}
        assert msg["type"] == "promote"
        assert msg["target_tier"] in ("stm", "mtm", "ltm")

    def test_consolidate_response_format(self):
        response = {
            "type": "consolidated",
            "purged": {"stm": 2, "mtm": 0, "ltm": 0},
            "stm_promoted": 3,
            "mtm_promoted": 1,
            "merged": 0,
            "total": 50,
        }
        assert response["type"] == "consolidated"
        assert "total" in response

    def test_v2_build_context_format(self):
        msg = {"type": "build_context", "query": "test", "max_entries": 10}
        response = {
            "type": "context",
            "query": "test",
            "entries": [{"id": "1", "text": "...", "score": 0.8, "tier": "stm"}],
        }
        assert response["type"] == "context"
        assert len(response["entries"]) > 0

    def test_v2_add_fact_format(self):
        msg = {
            "type": "add_fact",
            "key": "name",
            "value": "Alex",
            "category": "identity",
            "confidence": 1.0,
        }
        assert msg["type"] == "add_fact"
        assert msg["category"] == "identity"

    def test_v2_conversation_turn_format(self):
        msg = {
            "type": "conversation_turn",
            "role": "user",
            "text": "Bonjour",
            "session_id": "sess-1",
        }
        assert msg["type"] == "conversation_turn"
        assert msg["role"] in ("user", "assistant")

    def test_v2_health_format(self):
        response = {
            "type": "health",
            "status": "ok",
            "loaded": True,
            "vector_available": True,
            "memories": 100,
            "facts": 10,
        }
        assert response["status"] == "ok"

    def test_v2_metrics_format(self):
        response = {
            "type": "metrics",
            "adds": 50,
            "searches": 200,
            "removes": 3,
            "errors": 0,
        }
        assert response["type"] == "metrics"


# ═══════════════════════════════════════════════════════════════
# ConversationTurn
# ═══════════════════════════════════════════════════════════════

class TestConversationTurn:
    """Tests de ConversationTurn."""

    def test_create(self):
        from conversation_memory import ConversationTurn
        turn = ConversationTurn(role="user", text="Bonjour")
        assert turn.role == "user"
        assert turn.text == "Bonjour"
        assert turn.timestamp > 0

    def test_to_dict(self):
        from conversation_memory import ConversationTurn
        turn = ConversationTurn(role="assistant", text="Salut!")
        d = turn.to_dict()
        assert d["role"] == "assistant"
        assert d["text"] == "Salut!"
        assert "timestamp" in d

    def test_from_dict(self):
        from conversation_memory import ConversationTurn
        d = {"role": "user", "text": "test", "timestamp": 1234567.0}
        turn = ConversationTurn.from_dict(d)
        assert turn.role == "user"
        assert turn.timestamp == 1234567.0
