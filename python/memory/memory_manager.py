"""
EXO Mémoire v2 — MemoryManager (Orchestrateur)

Compose tous les sous-modules mémoire :
- MemoryHierarchy (STM/MTM/LTM)
- VectorIndex (FAISS)
- ConsolidationManager (promotion automatique)
- ContextEngine (contexte dynamique)
- ConversationMemory (historique de session)
- FactualMemory (faits persistants)

Expose une API unifiée pour memory_server.py.
Résilience : timeout 5s, retry 1, fallback gracieux.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path

try:
    from .memory_hierarchy import MemoryEntry, MemoryHierarchy
    from .vector_index import VectorIndex
    from .consolidation_manager import ConsolidationManager
    from .memory_context import ContextEngine
    from .conversation_memory import ConversationMemory
    from .factual_memory import FactualMemory
except ImportError:
    from memory_hierarchy import MemoryEntry, MemoryHierarchy
    from vector_index import VectorIndex
    from consolidation_manager import ConsolidationManager
    from memory_context import ContextEngine
    from conversation_memory import ConversationMemory
    from factual_memory import FactualMemory

log = logging.getLogger("memory.manager")

DEFAULT_MODEL = "all-MiniLM-L6-v2"
DEFAULT_DATA_DIR = os.environ.get(
    "EXO_FAISS_DIR",
    r"D:\EXO\faiss\semantic_memory",
)


class MemoryManager:
    """Orchestrateur central de la mémoire EXO v2.

    Compose les sous-modules et expose l'API unifiée.
    Compatible avec le protocole WS v8 (backward compat).
    """

    def __init__(self, model_name: str | None = None,
                 data_dir: str | None = None):
        self._model_name = model_name or DEFAULT_MODEL
        self._data_dir = Path(data_dir or DEFAULT_DATA_DIR)
        self._loaded = False

        # Sous-modules
        self.hierarchy = MemoryHierarchy()
        self.vector = VectorIndex(
            model_name=self._model_name,
            data_dir=self._data_dir,
        )
        self.consolidation = ConsolidationManager(
            hierarchy=self.hierarchy,
            vector_index=self.vector,
        )
        self.context = ContextEngine(
            hierarchy=self.hierarchy,
            vector_index=self.vector,
        )
        self.conversations: dict[str, ConversationMemory] = {}
        self.facts = FactualMemory()

        self._metrics = {
            "adds": 0,
            "searches": 0,
            "removes": 0,
            "errors": 0,
        }

    # ── Chargement ───────────────────────────────────

    def load(self) -> None:
        """Charge le modèle d'encodage et les données persistées."""
        t0 = time.monotonic()

        # Charger le vectoriel
        self.vector.load()

        # Charger les données existantes (v8 + v2)
        self._load_data()

        self._loaded = True
        elapsed = round((time.monotonic() - t0) * 1000)
        total = len(self.hierarchy.get_all())
        log.info("MemoryManager loaded: %d memories (%dms)", total, elapsed)

    def _load_data(self) -> None:
        """Charge les données depuis le disque."""
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # v2 format
        v2_path = self._data_dir / "metadata_v2.json"
        # v8 format (compat)
        v8_path = self._data_dir / "metadata_v8.json"
        # v7 format (compat)
        v7_path = self._data_dir / "metadata.json"

        if v2_path.exists():
            self._load_v2(v2_path)
        elif v8_path.exists():
            self._migrate_v8(v8_path)
        elif v7_path.exists():
            self._migrate_v7(v7_path)
        else:
            log.info("No existing data found, starting fresh")

    def _load_v2(self, path: Path) -> None:
        """Charge le format v2."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Hiérarchie
        hierarchy_data = data.get("hierarchy", {})
        self.hierarchy.import_data(hierarchy_data)

        # Reconstruire les index vectoriels
        for tier in ("stm", "mtm", "ltm"):
            entries = self.hierarchy.get_tier(tier)
            texts = [e.text for e in entries]
            ids = [e.id for e in entries]
            if texts and self.vector.available:
                self.vector.rebuild_tier(tier, texts, ids)

        # Faits
        facts_data = data.get("facts", [])
        self.facts.import_data(facts_data)

        total = len(self.hierarchy.get_all())
        log.info("Loaded v2 data: %d memories, %d facts",
                 total, len(facts_data))

    def _migrate_v8(self, path: Path) -> None:
        """Migre depuis le format v8 vers v2."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # v8: {tier: [entries...]}
        self.hierarchy.import_data(data)

        # Reconstruire les index vectoriels
        for tier in ("stm", "mtm", "ltm"):
            entries = self.hierarchy.get_tier(tier)
            texts = [e.text for e in entries]
            ids = [e.id for e in entries]
            if texts and self.vector.available:
                self.vector.rebuild_tier(tier, texts, ids)

        total = len(self.hierarchy.get_all())
        log.info("Migrated v8 data: %d memories", total)
        self.save()  # Sauvegarder en v2

    def _migrate_v7(self, path: Path) -> None:
        """Migre depuis le format v7 (flat) vers v2."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        old_mems = data.get("memories", [])
        for d in old_mems:
            d["tier"] = "ltm"  # Tout en LTM
        self.hierarchy.import_data({"ltm": old_mems})

        entries = self.hierarchy.get_tier("ltm")
        texts = [e.text for e in entries]
        ids = [e.id for e in entries]
        if texts and self.vector.available:
            self.vector.rebuild_tier("ltm", texts, ids)

        log.info("Migrated %d v7 memories to LTM", len(old_mems))
        self.save()

    # ── Sauvegarde ───────────────────────────────────

    def save(self) -> None:
        """Sauvegarde toutes les données sur disque."""
        self._data_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "version": 2,
            "hierarchy": self.hierarchy.export_data(),
            "facts": self.facts.export_data(),
            "saved_at": time.time(),
        }

        with open(self._data_dir / "metadata_v2.json", "w",
                   encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self.vector.save()
        log.debug("Data saved to %s", self._data_dir)

    # ── API Mémoire principale ───────────────────────

    def add(self, text: str, importance: float = 0.5,
            tags: list[str] | None = None,
            category: str = "", source: str = "user",
            ttl_days: float = 0.0,
            tier: str = "stm") -> MemoryEntry | None:
        """Ajoute un souvenir. Retourne None si doublon."""
        # Détection de doublon via vectoriel
        if self.vector.available and self.vector.is_duplicate(text):
            log.info("Duplicate detected: %s", text[:60])
            return None

        entry_id = str(uuid.uuid4())
        ttl_seconds = ttl_days * 86400 if ttl_days > 0 else 0
        entry = MemoryEntry(
            id=entry_id,
            text=text,
            importance=importance,
            tags=tags or [],
            category=category,
            source=source,
            ttl_seconds=ttl_seconds,
            tier=tier,
        )

        self.hierarchy.add(entry)
        self.vector.add(entry_id, text, tier=tier)
        self._metrics["adds"] += 1

        self.save()
        log.info("Added [%s/%s]: %s", tier, category, text[:60])
        return entry

    def search(self, query: str, top_k: int = 5,
               tiers: list[str] | None = None) -> list[dict]:
        """Recherche sémantique avec scoring dynamique."""
        self._metrics["searches"] += 1

        # Recherche vectorielle
        results = self.vector.search(query, top_k=top_k * 3, tiers=tiers)

        # Enrichir avec les données de la hiérarchie
        enriched = []
        now = time.time()
        for r in results:
            entry = self.hierarchy.get(r["id"])
            if entry and entry.is_expired():
                continue
            if entry:
                age_days = (now - entry.timestamp) / 86400
                recency = 1.0 / (1.0 + age_days / 30.0)
                access_boost = min(0.1, entry.access_count * 0.01)
                tier_w = {"stm": 0.9, "mtm": 1.0, "ltm": 1.1}.get(
                    entry.tier, 1.0)
                dynamic_score = (
                    r["raw_similarity"]
                    * (0.5 + 0.3 * entry.importance + 0.2 * recency + access_boost)
                    * tier_w
                )
                entry.touch()
                result = entry.to_dict()
                result["score"] = dynamic_score
                result["raw_similarity"] = r["raw_similarity"]
                enriched.append(result)
            else:
                # Entrée vectorielle sans données hiérarchie
                enriched.append(r)

        enriched.sort(key=lambda x: x.get("score", 0), reverse=True)
        return enriched[:top_k]

    def remove(self, memory_id: str) -> bool:
        """Supprime un souvenir par ID."""
        self._metrics["removes"] += 1
        removed = self.hierarchy.remove(memory_id)
        if removed:
            self.vector.delete(memory_id)
            self.save()
        return removed

    def clear(self) -> None:
        """Efface toute la mémoire."""
        for tier in ("stm", "mtm", "ltm"):
            self.hierarchy._tiers[tier].clear()
        self.vector.rebuild_all()
        self.save()
        log.info("All memories cleared")

    # ── Renforcement / Affaiblissement ───────────────

    def reinforce(self, memory_id: str,
                  boost: float = 0.1) -> MemoryEntry | None:
        """Renforce un souvenir. Auto-promotion STM→MTM."""
        entry = self.hierarchy.get(memory_id)
        if not entry:
            return None
        entry.reinforce(boost)

        # Auto-promotion STM → MTM
        if (entry.tier == "stm"
                and entry.reinforcements >= ConsolidationManager.STM_TO_MTM_ACCESS):
            self.hierarchy.promote(memory_id, "mtm")
            self.vector.delete(memory_id)
            self.vector.add(memory_id, entry.text, tier="mtm")

        self.save()
        return entry

    def weaken(self, memory_id: str,
               decay: float = 0.1) -> MemoryEntry | None:
        """Affaiblit un souvenir."""
        entry = self.hierarchy.get(memory_id)
        if not entry:
            return None
        entry.weaken(decay)
        self.save()
        return entry

    # ── Promotion ────────────────────────────────────

    def promote(self, memory_id: str,
                target_tier: str) -> MemoryEntry | None:
        """Promeut manuellement un souvenir vers un tier cible."""
        entry = self.hierarchy.promote(memory_id, target_tier)
        if entry:
            self.vector.delete(memory_id)
            self.vector.add(memory_id, entry.text, tier=target_tier)
            self.save()
        return entry

    # ── Consolidation ────────────────────────────────

    def consolidate(self) -> dict:
        """Consolidation complète : expire + merge + promote."""
        result = self.consolidation.consolidate_all()

        # Reconstruire les index après consolidation
        for tier in ("stm", "mtm", "ltm"):
            entries = self.hierarchy.get_tier(tier)
            texts = [e.text for e in entries]
            ids = [e.id for e in entries]
            self.vector.rebuild_tier(tier, texts, ids)

        total = len(self.hierarchy.get_all())
        result["total"] = total
        self.save()
        return result

    # ── Résumé de texte ──────────────────────────────

    def summarize_text(self, text: str) -> dict:
        """Résumé extractif par centroïde sémantique."""
        if not self.vector.available:
            return {"short": text[:100], "medium": text[:500], "long": text}

        import numpy as np

        sentences = [s.strip() for s in text.replace("\n", ". ").split(".")
                     if s.strip() and len(s.strip()) > 10]

        if not sentences:
            return {"short": text[:100], "medium": text[:500], "long": text}

        embs = self.vector.encode(sentences)
        centroid = embs.mean(axis=0, keepdims=True)
        centroid = centroid / (np.linalg.norm(centroid) + 1e-8)
        sims = (embs @ centroid.T).flatten()
        ranked = sorted(range(len(sentences)), key=lambda i: sims[i],
                        reverse=True)

        short_sents = [sentences[i] for i in sorted(ranked[:2])]
        short = ". ".join(short_sents) + "."

        n_med = min(6, len(ranked))
        med_sents = [sentences[i] for i in sorted(ranked[:n_med])]
        medium = ". ".join(med_sents) + "."

        n_long = min(12, len(ranked))
        long_sents = [sentences[i] for i in sorted(ranked[:n_long])]
        long_text = ". ".join(long_sents) + "."

        return {"short": short, "medium": medium, "long": long_text}

    # ── Résumé d'historique conversationnel ───────────

    def summarize_history(self, messages: list[dict]) -> dict:
        """Extrait les faits clés d'une conversation → stocke en MTM."""
        if not messages:
            return {"facts": [], "stored": 0}

        # Construire le texte complet
        lines = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        full_text = "\n".join(lines)

        sentences = [s.strip() for s in full_text.replace("\n", ". ").split(".")
                     if s.strip() and len(s.strip()) > 15]

        if not sentences:
            return {"facts": [], "stored": 0}

        if self.vector.available:
            import numpy as np
            embs = self.vector.encode(sentences)
            centroid = embs.mean(axis=0, keepdims=True)
            centroid = centroid / (np.linalg.norm(centroid) + 1e-8)
            sims = (embs @ centroid.T).flatten()
            n_facts = min(8, len(sentences))
            ranked = sorted(range(len(sentences)),
                            key=lambda i: sims[i], reverse=True)
            facts = [sentences[i] for i in sorted(ranked[:n_facts])]
        else:
            facts = sentences[:8]

        # Stocker en MTM
        stored = 0
        for fact in facts:
            clean = fact
            for prefix in ("user:", "assistant:"):
                if clean.lower().startswith(prefix):
                    clean = clean[len(prefix):].strip()
            if len(clean) < 10:
                continue
            entry = self.add(
                text=clean,
                importance=0.6,
                tags=["conversation_fact", "auto_extracted"],
                category="conversation",
                source="summarizer",
                tier="mtm",
            )
            if entry:
                stored += 1

        log.info("History: %d facts extracted, %d stored", len(facts), stored)
        return {"facts": facts, "stored": stored}

    # ── Détection de contradictions ──────────────────

    def detect_contradictions(self, text: str) -> list[dict]:
        """Trouve les souvenirs qui pourraient contredire le texte."""
        if not self.vector.available:
            return []

        import numpy as np
        emb = self.vector.encode([text])
        pairs = []

        for tier in ("stm", "mtm", "ltm"):
            entries = self.hierarchy.get_tier(tier)
            if not entries:
                continue
            # Encoder tous les textes du tier
            texts = [e.text for e in entries]
            tier_embs = self.vector.encode(texts)
            sims = (emb @ tier_embs.T).flatten()

            for i, sim in enumerate(sims):
                sim_f = float(sim)
                if 0.4 <= sim_f <= 0.75:
                    e = entries[i]
                    pairs.append({
                        "id": e.id,
                        "text": e.text,
                        "similarity": sim_f,
                        "importance": e.importance,
                        "tier": e.tier,
                    })

        return pairs

    # ── Contexte pour LLM ────────────────────────────

    def build_context(self, query: str,
                      max_entries: int = 20) -> list[dict]:
        """Construit le contexte dynamique pour le LLM."""
        return self.context.build_context(query, max_entries=max_entries)

    def inject_context(self, prompt: str, query: str,
                       max_entries: int = 10) -> str:
        """Injecte le contexte mémoire dans un prompt LLM."""
        return self.context.inject_context(prompt, query, max_entries)

    # ── Conversations ────────────────────────────────

    def get_conversation(self, session_id: str = "default") -> ConversationMemory:
        """Retourne (ou crée) la mémoire conversationnelle d'une session."""
        if session_id not in self.conversations:
            self.conversations[session_id] = ConversationMemory(session_id)
        return self.conversations[session_id]

    # ── Stats ────────────────────────────────────────

    def stats(self) -> dict:
        total = len(self.hierarchy.get_all())
        tier_stats = {}
        for t in ("stm", "mtm", "ltm"):
            entries = self.hierarchy.get_tier(t)
            tier_stats[t] = {
                "count": len(entries),
                "avg_importance": (
                    sum(e.importance for e in entries) / len(entries)
                    if entries else 0.0
                ),
            }
        return {
            "count": total,
            "model": self._model_name,
            "dim": self.vector.dim,
            "tiers": tier_stats,
            "facts": self.facts.stats(),
            "vector": self.vector.stats(),
        }

    def tier_stats(self) -> dict:
        return self.hierarchy.tier_stats()

    def health_check(self) -> dict:
        return {
            "status": "ok" if self._loaded else "loading",
            "loaded": self._loaded,
            "vector_available": self.vector.available,
            "memories": len(self.hierarchy.get_all()),
            "facts": len(self.facts.all_facts()),
        }

    def metrics(self) -> dict:
        return {
            **self._metrics,
            "hierarchy": self.hierarchy.metrics(),
            "consolidation": self.consolidation.metrics(),
            "context": self.context.metrics(),
            "vector": self.vector.stats(),
        }
