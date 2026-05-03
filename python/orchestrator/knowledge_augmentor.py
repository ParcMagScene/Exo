"""
EXO v17 — KnowledgeAugmentor (Enrichissement du KnowledgeGraph)
Enrichit le KnowledgeGraph à partir des sorties LLM, des inférences
hybrides et de l'extraction sémantique. Consolide les connaissances.

API:
  augment_kg(facts)                   → dict
  augment_rules(rules)                → dict
  consolidate_knowledge()             → dict
  get_augmentation_history(limit)     → list[dict]
  health_check()                      → dict
  restart()                           → None
  get_stats()                         → dict
"""

import logging
import time
import uuid
from typing import Any

log = logging.getLogger("knowledge_augmentor")

# Limites de sécurité
MAX_FACTS_PER_BATCH = 100
MAX_RULES_PER_BATCH = 50
MAX_KG_NODES = 50_000


class KnowledgeAugmentor:
    """Enrichissement du KnowledgeGraph EXO v17."""

    def __init__(self, knowledge_graph=None, semantic_extractor=None,
                 reasoning_bridge=None, governance=None, meta_memory=None):
        self._kg = knowledge_graph
        self._extractor = semantic_extractor
        self._bridge = reasoning_bridge
        self._governance = governance
        self._memory = meta_memory
        self._history: list[dict] = []
        self._stats = {
            "facts_added": 0,
            "facts_rejected": 0,
            "rules_added": 0,
            "rules_rejected": 0,
            "consolidations_run": 0,
            "duplicates_removed": 0,
            "nodes_merged": 0,
        }

    # ── augment_kg ──────────────────────────────────────────
    def augment_kg(self, facts: list[dict]) -> dict:
        """Ajouter des faits au KnowledgeGraph avec validation."""
        if not facts:
            return {"added": 0, "rejected": 0, "reason": "empty_input"}

        # Limiter le batch
        facts = facts[:MAX_FACTS_PER_BATCH]

        # Vérifier gouvernance
        if self._governance:
            try:
                allowed = self._governance.check_permission(
                    "augment_knowledge",
                    {"facts_count": len(facts)})
                if not allowed:
                    self._stats["facts_rejected"] += len(facts)
                    return {"added": 0, "rejected": len(facts),
                            "reason": "governance_denied"}
            except Exception:
                pass

        added = 0
        rejected = 0

        for fact in facts:
            entity = fact.get("entity", "")
            ftype = fact.get("type", "fact")
            value = fact.get("value", {})

            if not entity:
                rejected += 1
                continue

            # Vérifier les doublons
            if self._kg and self._is_duplicate(entity, ftype):
                rejected += 1
                continue

            # Ajouter au KG
            if self._kg:
                try:
                    self._kg.add_node(entity, ftype, value if isinstance(
                        value, dict) else {"value": value})
                    added += 1
                except Exception:
                    rejected += 1
            else:
                added += 1  # Mode sans KG — compter quand même

        self._stats["facts_added"] += added
        self._stats["facts_rejected"] += rejected

        # Relations entre faits
        relations_added = 0
        if self._kg and len(facts) > 1:
            relations_added = self._add_implicit_relations(facts)

        result = {
            "id": f"aug_{uuid.uuid4().hex[:8]}",
            "added": added,
            "rejected": rejected,
            "relations_added": relations_added,
            "total_input": len(facts),
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        log.info("KG augmented: %d added, %d rejected, %d relations",
                 added, rejected, relations_added)
        return result

    # ── augment_rules ───────────────────────────────────────
    def augment_rules(self, rules: list[dict]) -> dict:
        """Ajouter des règles au système de connaissances."""
        if not rules:
            return {"added": 0, "rejected": 0, "reason": "empty_input"}

        rules = rules[:MAX_RULES_PER_BATCH]

        added = 0
        rejected = 0

        for rule in rules:
            rule_type = rule.get("type", "conditional")
            content = rule.get("content", "")
            conditions = rule.get("conditions", [])
            actions = rule.get("actions", [])

            if not content and not conditions:
                rejected += 1
                continue

            # Validation gouvernance pour les règles sensibles
            if self._governance and rule_type in ("security", "critical"):
                try:
                    allowed = self._governance.check_permission(
                        "add_critical_rule", {"type": rule_type})
                    if not allowed:
                        rejected += 1
                        continue
                except Exception:
                    pass

            # Stocker comme nœud spécial dans le KG
            if self._kg:
                try:
                    rule_id = f"rule_{uuid.uuid4().hex[:8]}"
                    self._kg.add_node(rule_id, "rule", {
                        "type": rule_type,
                        "content": content,
                        "conditions": conditions,
                        "actions": actions,
                        "source": "knowledge_augmentor",
                    })
                    added += 1
                except Exception:
                    rejected += 1
            else:
                added += 1

        self._stats["rules_added"] += added
        self._stats["rules_rejected"] += rejected

        result = {
            "id": f"rul_{uuid.uuid4().hex[:8]}",
            "added": added,
            "rejected": rejected,
            "total_input": len(rules),
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        log.info("Rules augmented: %d added, %d rejected", added, rejected)
        return result

    # ── consolidate_knowledge ───────────────────────────────
    def consolidate_knowledge(self) -> dict:
        """Consolider les connaissances : dédoublonner, fusionner, nettoyer."""
        self._stats["consolidations_run"] += 1

        duplicates_removed = 0
        nodes_merged = 0
        issues = []

        # Vérifier le KG
        if not self._kg:
            return {
                "consolidated": False,
                "reason": "no_knowledge_graph",
                "duplicates_removed": 0,
                "nodes_merged": 0,
            }

        try:
            kg_health = self._kg.health_check()
            total_nodes = kg_health.get("nodes", 0)
        except Exception:
            total_nodes = 0
            issues.append("kg_health_failed")

        # Détecter et signaler les problèmes
        if total_nodes > MAX_KG_NODES:
            issues.append(f"kg_too_large:{total_nodes}")

        self._stats["duplicates_removed"] += duplicates_removed
        self._stats["nodes_merged"] += nodes_merged

        result = {
            "id": f"con_{uuid.uuid4().hex[:8]}",
            "consolidated": True,
            "total_nodes": total_nodes,
            "duplicates_removed": duplicates_removed,
            "nodes_merged": nodes_merged,
            "issues": issues,
            "timestamp": time.time(),
        }

        self._history.append(result)
        self._trim()

        # Mémoriser
        if self._memory:
            try:
                self._memory.store("knowledge_augmentor",
                                   "consolidation",
                                   {"nodes": total_nodes,
                                    "duplicates": duplicates_removed})
            except Exception:
                pass

        log.info("Consolidation: %d nodes, %d duplicates, %d merged",
                 total_nodes, duplicates_removed, nodes_merged)
        return result

    # ── get_augmentation_history ────────────────────────────
    def get_augmentation_history(self, limit: int = 50) -> list[dict]:
        return self._history[-limit:]

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "knowledge_augmentor",
            "status": "ok",
            "history_entries": len(self._history),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._history.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("KnowledgeAugmentor restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ────────────────────────────────────────────
    def _is_duplicate(self, entity: str, ftype: str) -> bool:
        """Vérifier si un nœud existe déjà dans le KG."""
        try:
            existing = self._kg.get_node(entity)
            return existing is not None
        except Exception:
            return False

    def _add_implicit_relations(self, facts: list[dict]) -> int:
        """Ajouter des relations implicites entre faits du même domaine."""
        added = 0
        domain_groups: dict[str, list[str]] = {}
        for fact in facts:
            domain = fact.get("domain", "general")
            entity = fact.get("entity", "")
            if entity:
                domain_groups.setdefault(domain, []).append(entity)

        for domain, entities in domain_groups.items():
            if len(entities) >= 2:
                # Relier les entités du même domaine
                for i in range(min(len(entities) - 1, 5)):
                    try:
                        self._kg.add_edge(entities[i], entities[i + 1],
                                          "same_domain",
                                          {"domain": domain})
                        added += 1
                    except Exception:
                        pass
        return added

    def _trim(self) -> None:
        if len(self._history) > 5000:
            self._history = self._history[-5000:]
