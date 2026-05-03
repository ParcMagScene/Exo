"""
EXO v17 — SemanticExtractor (Extraction sémantique)
Transforme les sorties LLM en faits symboliques structurés :
entités, relations, dépendances et patterns.

API:
  extract_entities(text)              → dict
  extract_relations(text)             → dict
  extract_semantic_graph(text)        → dict
  extract_patterns(text)              → dict
  get_extraction_history(limit)       → list[dict]
  health_check()                      → dict
  restart()                           → None
  get_stats()                         → dict
"""

import logging
import re
import time
import uuid
from typing import Any

log = logging.getLogger("semantic_extractor")

# Patterns d'extraction d'entités
ENTITY_PATTERNS = {
    "device": re.compile(
        r"\b(lampe|lumière|thermostat|capteur|volet|prise|caméra|enceinte"
        r"|light|sensor|switch|camera|speaker)\b", re.IGNORECASE),
    "room": re.compile(
        r"\b(salon|cuisine|chambre|salle de bain|bureau|garage|jardin|entrée"
        r"|living room|kitchen|bedroom|bathroom|office|garage|garden)\b",
        re.IGNORECASE),
    "action": re.compile(
        r"\b(allumer|éteindre|ouvrir|fermer|augmenter|diminuer|activer|désactiver"
        r"|turn on|turn off|open|close|increase|decrease|activate|deactivate)\b",
        re.IGNORECASE),
    "value": re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:°C|°F|%|W|kWh|lux)\b"),
    "time": re.compile(
        r"\b(\d{1,2}[h:]\d{2}|matin|midi|soir|nuit"
        r"|morning|noon|evening|night)\b", re.IGNORECASE),
}

# Patterns de relations
RELATION_PATTERNS = {
    "is_in": re.compile(
        r"(\w+)\s+(?:est dans|is in|se trouve dans)\s+(\w+)", re.IGNORECASE),
    "controls": re.compile(
        r"(\w+)\s+(?:contrôle|controls|gère|manages)\s+(\w+)", re.IGNORECASE),
    "depends_on": re.compile(
        r"(\w+)\s+(?:dépend de|depends on|nécessite|requires)\s+(\w+)",
        re.IGNORECASE),
    "triggers": re.compile(
        r"(\w+)\s+(?:déclenche|triggers|provoque|causes)\s+(\w+)",
        re.IGNORECASE),
}


class SemanticExtractor:
    """Extracteur sémantique EXO v17."""

    def __init__(self, knowledge_graph=None, reasoning_bridge=None,
                 meta_memory=None):
        self._kg = knowledge_graph
        self._bridge = reasoning_bridge
        self._memory = meta_memory
        self._history: list[dict] = []
        self._stats = {
            "entities_extracted": 0,
            "relations_extracted": 0,
            "graphs_built": 0,
            "patterns_detected": 0,
            "total_extractions": 0,
        }

    # ── extract_entities ────────────────────────────────────
    def extract_entities(self, text: str) -> dict:
        """Extraire les entités nommées d'un texte."""
        self._stats["total_extractions"] += 1

        entities = {}
        for etype, pattern in ENTITY_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                entities[etype] = [
                    {"value": m, "type": etype} for m in set(matches)
                ]

        total = sum(len(v) for v in entities.values())
        self._stats["entities_extracted"] += total

        result = {
            "id": f"ent_{uuid.uuid4().hex[:8]}",
            "entities": entities,
            "entity_count": total,
            "types_found": list(entities.keys()),
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        # Injecter dans le KG si disponible
        if self._kg and total > 0:
            for etype, elist in entities.items():
                for ent in elist:
                    try:
                        self._kg.add_node(
                            ent["value"], etype,
                            {"source": "semantic_extractor"})
                    except Exception:
                        pass

        log.info("Entities extracted: %d across %d types",
                 total, len(entities))
        return result

    # ── extract_relations ───────────────────────────────────
    def extract_relations(self, text: str) -> dict:
        """Extraire les relations entre entités."""
        self._stats["total_extractions"] += 1

        relations = []
        for rtype, pattern in RELATION_PATTERNS.items():
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple) and len(match) >= 2:
                    relations.append({
                        "subject": match[0],
                        "predicate": rtype,
                        "object": match[1],
                        "source": "semantic_extractor",
                    })

        self._stats["relations_extracted"] += len(relations)

        result = {
            "id": f"rel_{uuid.uuid4().hex[:8]}",
            "relations": relations,
            "relation_count": len(relations),
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        # Injecter dans le KG
        if self._kg and relations:
            for rel in relations:
                try:
                    self._kg.add_edge(
                        rel["subject"], rel["object"],
                        rel["predicate"],
                        {"source": "semantic_extractor"})
                except Exception:
                    pass

        log.info("Relations extracted: %d", len(relations))
        return result

    # ── extract_semantic_graph ──────────────────────────────
    def extract_semantic_graph(self, text: str) -> dict:
        """Construire un graphe sémantique complet depuis un texte."""
        self._stats["graphs_built"] += 1
        self._stats["total_extractions"] += 1

        # Extraire entités et relations
        entities = self.extract_entities(text)
        relations = self.extract_relations(text)

        # Construire le graphe
        nodes = {}
        edges = []

        for etype, elist in entities.get("entities", {}).items():
            for ent in elist:
                node_id = ent["value"].lower().replace(" ", "_")
                nodes[node_id] = {
                    "id": node_id,
                    "label": ent["value"],
                    "type": etype,
                }

        for rel in relations.get("relations", []):
            edges.append({
                "source": rel["subject"].lower().replace(" ", "_"),
                "target": rel["object"].lower().replace(" ", "_"),
                "relation": rel["predicate"],
            })

        result = {
            "id": f"sg_{uuid.uuid4().hex[:8]}",
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "entity_types": entities.get("types_found", []),
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        log.info("Semantic graph: %d nodes, %d edges",
                 len(nodes), len(edges))
        return result

    # ── extract_patterns ────────────────────────────────────
    def extract_patterns(self, text: str) -> dict:
        """Détecter des patterns récurrents dans le texte."""
        self._stats["total_extractions"] += 1

        patterns = []

        # Pattern conditionnel (si/alors)
        cond_matches = re.findall(
            r"(?:si|if|quand|when)\s+(.{5,80}?)(?:alors|then|,)",
            text, re.IGNORECASE)
        for m in cond_matches:
            patterns.append({"type": "conditional", "content": m.strip()})

        # Pattern temporel
        time_matches = re.findall(
            r"(?:chaque|every|tous les|à)\s+(.{3,40}?)(?:\.|,|$)",
            text, re.IGNORECASE)
        for m in time_matches:
            patterns.append({"type": "temporal", "content": m.strip()})

        # Pattern causal
        cause_matches = re.findall(
            r"(?:parce que|because|car|puisque|since)\s+(.{5,80}?)(?:\.|,|$)",
            text, re.IGNORECASE)
        for m in cause_matches:
            patterns.append({"type": "causal", "content": m.strip()})

        self._stats["patterns_detected"] += len(patterns)

        result = {
            "id": f"pat_{uuid.uuid4().hex[:8]}",
            "patterns": patterns,
            "pattern_count": len(patterns),
            "types_found": list(set(p["type"] for p in patterns)),
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()
        return result

    # ── get_extraction_history ──────────────────────────────
    def get_extraction_history(self, limit: int = 50) -> list[dict]:
        return self._history[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "semantic_extractor",
            "status": "ok",
            "history_entries": len(self._history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("SemanticExtractor restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-5000:]
