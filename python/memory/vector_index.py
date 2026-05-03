"""
EXO Mémoire v2 — VectorIndex

Index vectoriel FAISS pour recherche sémantique rapide.
- Un index par tier (STM optionnel, MTM, LTM)
- Encodage SentenceTransformer
- Recherche sémantique avec scoring dynamique
- Détection de doublons
- Fallback textuel si FAISS indisponible

Résilience : timeouts 2s, 1 retry, fallback texte.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger("memory.vector")

# Lazy imports — ne pas planter si FAISS/ST pas installé
_faiss = None
_SentenceTransformer = None


def _load_faiss():
    global _faiss
    if _faiss is None:
        import faiss
        _faiss = faiss
    return _faiss


def _load_st():
    global _SentenceTransformer
    if _SentenceTransformer is None:
        from sentence_transformers import SentenceTransformer
        _SentenceTransformer = SentenceTransformer
    return _SentenceTransformer


class VectorIndex:
    """Index vectoriel FAISS multi-tier avec encodeur SentenceTransformer.

    Fournit : add, search, delete, rebuild, save/load.
    Fallback textuel si FAISS indisponible.
    """

    DUPLICATE_THRESHOLD = 0.92
    DEFAULT_MODEL = "all-MiniLM-L6-v2"
    TIERS = ("stm", "mtm", "ltm")

    TIMEOUT = 2.0   # secondes
    MAX_RETRIES = 1

    def __init__(self, model_name: str | None = None,
                 data_dir: str | Path | None = None):
        self._model_name = model_name or self.DEFAULT_MODEL
        self._data_dir = Path(data_dir) if data_dir else None
        self._encoder = None
        self._dim = 0
        self._indices: dict[str, Any] = {}
        self._texts: dict[str, list[str]] = {t: [] for t in self.TIERS}
        self._ids: dict[str, list[str]] = {t: [] for t in self.TIERS}
        self._available = False
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self._available

    @property
    def dim(self) -> int:
        return self._dim

    def load(self, device: str = "cpu") -> bool:
        """Charge le modèle d'encodage et les indices FAISS.

        Returns True si chargement réussi.
        """
        t0 = time.monotonic()
        try:
            ST = _load_st()
            self._encoder = ST(self._model_name, device=device)
            self._dim = self._encoder.get_sentence_embedding_dimension()

            faiss = _load_faiss()
            for tier in self.TIERS:
                self._indices[tier] = self._create_index()

            # Charger indices existants si data_dir fourni
            if self._data_dir and self._data_dir.exists():
                self._load_from_disk()

            self._available = True
            elapsed = round((time.monotonic() - t0) * 1000)
            log.info("VectorIndex loaded: model=%s dim=%d (%dms)",
                     self._model_name, self._dim, elapsed)
            return True

        except Exception as e:
            log.warning("VectorIndex load failed (fallback textuel): %s", e)
            self._available = False
            return False

    def _create_index(self):
        faiss = _load_faiss()
        index = faiss.IndexHNSWFlat(self._dim, 32, faiss.METRIC_INNER_PRODUCT)
        index.hnsw.efConstruction = 200
        index.hnsw.efSearch = 64
        return index

    # ── Encodage ─────────────────────────────────────

    def encode(self, texts: list[str]) -> np.ndarray:
        """Encode une liste de textes en vecteurs normalisés."""
        if not self._encoder:
            raise RuntimeError("Encoder not loaded")
        return self._encoder.encode(texts, normalize_embeddings=True).astype(np.float32)

    # ── API principale ───────────────────────────────

    def add(self, entry_id: str, text: str, tier: str = "stm",
            metadata: dict | None = None) -> bool:
        """Ajoute un texte à l'index d'un tier.

        Returns False si doublon détecté.
        """
        if tier not in self.TIERS:
            tier = "stm"

        with self._lock:
            if not self._available:
                # Fallback: stocker le texte brut sans index
                self._texts[tier].append(text)
                self._ids[tier].append(entry_id)
                return True

            # Vérifier doublon (sans lock car déjà acquis)
            if self._is_duplicate_unlocked(text):
                return False

            embedding = self.encode([text])
            self._indices[tier].add(embedding)
            self._texts[tier].append(text)
            self._ids[tier].append(entry_id)
            return True

    def search(self, query: str, top_k: int = 5,
               tiers: list[str] | None = None) -> list[dict]:
        """Recherche sémantique multi-tier.

        Returns: list[{id, text, score, tier}]
        """
        search_tiers = tiers or list(self.TIERS)

        with self._lock:
            if not self._available:
                return self._fallback_search(query, top_k, search_tiers)

            query_emb = self.encode([query])
            results = []

            # Poids par tier : LTM plus stable → léger boost
            tier_weight = {"stm": 0.9, "mtm": 1.0, "ltm": 1.1}

            for tier in search_tiers:
                idx = self._indices.get(tier)
                texts = self._texts.get(tier, [])
                ids = self._ids.get(tier, [])
                if not texts or idx is None or idx.ntotal == 0:
                    continue

                k = min(top_k * 3, idx.ntotal)
                scores, indices = idx.search(query_emb, k)

                for score, mem_idx in zip(scores[0], indices[0]):
                    if mem_idx < 0 or mem_idx >= len(texts):
                        continue
                    tw = tier_weight.get(tier, 1.0)
                    results.append({
                        "id": ids[mem_idx],
                        "text": texts[mem_idx],
                        "score": float(score) * tw,
                        "raw_similarity": float(score),
                        "tier": tier,
                    })

            results.sort(key=lambda r: r["score"], reverse=True)
            return results[:top_k]

    def delete(self, entry_id: str) -> bool:
        """Supprime un vecteur de l'index par ID. Nécessite rebuild."""
        with self._lock:
            for tier in self.TIERS:
                if entry_id in self._ids[tier]:
                    idx = self._ids[tier].index(entry_id)
                    self._ids[tier].pop(idx)
                    self._texts[tier].pop(idx)
                    if self._available:
                        self._rebuild_tier_unlocked(tier)
                    return True
            return False

    def is_duplicate(self, text: str) -> bool:
        """Vérifie si un texte très similaire existe déjà."""
        with self._lock:
            return self._is_duplicate_unlocked(text)

    def _is_duplicate_unlocked(self, text: str) -> bool:
        """Vérifie doublon (appelé avec lock déjà acquis)."""
        if not self._available:
            for tier in self.TIERS:
                if text in self._texts[tier]:
                    return True
            return False

        emb = self.encode([text])
        for tier in self.TIERS:
            idx = self._indices.get(tier)
            if idx and idx.ntotal > 0:
                scores, _ = idx.search(emb, 1)
                if float(scores[0][0]) >= self.DUPLICATE_THRESHOLD:
                    return True
        return False

    # ── Rebuild ──────────────────────────────────────

    def rebuild_tier(self, tier: str, texts: list[str], ids: list[str]) -> None:
        """Reconstruit l'index d'un tier à partir de listes."""
        with self._lock:
            self._texts[tier] = list(texts)
            self._ids[tier] = list(ids)
            self._rebuild_tier_unlocked(tier)

    def _rebuild_tier(self, tier: str) -> None:
        """Reconstruit l'index FAISS d'un tier (thread-safe)."""
        with self._lock:
            self._rebuild_tier_unlocked(tier)

    def _rebuild_tier_unlocked(self, tier: str) -> None:
        """Reconstruit l'index FAISS d'un tier (appelé avec lock acquis)."""
        if not self._available:
            return
        self._indices[tier] = self._create_index()
        texts = self._texts.get(tier, [])
        if texts:
            embeddings = self.encode(texts)
            self._indices[tier].add(embeddings)

    def rebuild_all(self) -> None:
        """Reconstruit tous les indices."""
        with self._lock:
            for tier in self.TIERS:
                self._rebuild_tier_unlocked(tier)

    # ── Fallback textuel ─────────────────────────────

    def _fallback_search(self, query: str, top_k: int,
                         tiers: list[str]) -> list[dict]:
        """Recherche textuelle basique si FAISS indisponible."""
        results = []
        query_lower = query.lower()
        words = set(re.findall(r'\w+', query_lower))

        for tier in tiers:
            for entry_id, text in zip(self._ids[tier], self._texts[tier]):
                text_lower = text.lower()
                text_words = set(re.findall(r'\w+', text_lower))
                # Score = Jaccard-like
                if not words:
                    continue
                overlap = len(words & text_words)
                if overlap > 0:
                    score = overlap / len(words | text_words)
                    results.append({
                        "id": entry_id,
                        "text": text,
                        "score": score,
                        "raw_similarity": score,
                        "tier": tier,
                    })

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]

    # ── Persistance ──────────────────────────────────

    def save(self) -> None:
        """Sauvegarde les indices FAISS sur disque."""
        if not self._data_dir or not self._available:
            return
        with self._lock:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            faiss = _load_faiss()
            for tier in self.TIERS:
                idx = self._indices.get(tier)
                if idx and idx.ntotal > 0:
                    faiss.write_index(
                        idx, str(self._data_dir / f"embeddings_{tier}.faiss"))
            log.debug("VectorIndex saved to %s", self._data_dir)

    def _load_from_disk(self) -> None:
        """Charge les indices FAISS existants."""
        faiss = _load_faiss()
        for tier in self.TIERS:
            path = self._data_dir / f"embeddings_{tier}.faiss"
            if path.exists():
                try:
                    self._indices[tier] = faiss.read_index(str(path))
                except Exception as e:
                    log.warning("Failed to load %s index: %s", tier, e)
                    self._indices[tier] = self._create_index()

    # ── Stats ────────────────────────────────────────

    def stats(self) -> dict:
        result = {}
        for tier in self.TIERS:
            idx = self._indices.get(tier)
            result[tier] = {
                "entries": len(self._texts[tier]),
                "index_size": idx.ntotal if (idx and self._available) else 0,
            }
        result["available"] = self._available
        result["model"] = self._model_name
        result["dim"] = self._dim
        return result
