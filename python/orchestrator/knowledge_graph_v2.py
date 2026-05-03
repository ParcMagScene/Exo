"""
EXO v21 — KnowledgeGraphV2
Extension du KnowledgeGraph v15/v17 avec relations causales,
temporelles, hiérarchiques, contextuelles et multi-agents.

API:
  kg_add(node: dict)        → dict
  kg_query(pattern: dict)   → dict
  kg_explain(node: dict)    → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("knowledge_graph_v2")


class KnowledgeGraphV2:
    """Graphe de connaissances étendu EXO v21."""

    RELATION_TYPES = {
        "causal", "temporal", "hierarchical",
        "contextual", "multi_agent", "semantic",
        "dependency", "equivalence",
    }

    def __init__(self, knowledge_graph=None, causal_engine=None, governance=None):
        self._knowledge_graph = knowledge_graph
        self._causal_engine = causal_engine
        self._governance = governance

        self._nodes: dict[str, dict] = {}
        self._edges: list[dict] = {}
        self._adjacency: dict[str, list[str]] = {}
        self._stats = {
            "nodes_added": 0,
            "queries": 0,
            "explanations": 0,
        }

    # ── kg_add ──────────────────────────────────────────────
    def kg_add(self, node: dict) -> dict:
        """Ajouter un nœud ou une relation au graphe."""
        self._stats["nodes_added"] += 1

        node_id = node.get("id", f"n_{uuid.uuid4().hex[:8]}")
        label = node.get("label", "unknown")
        node_type = node.get("type", "entity")
        properties = node.get("properties", {})
        relations = node.get("relations", [])

        entry = {
            "id": node_id,
            "label": label,
            "type": node_type,
            "properties": properties,
            "relations": [],
            "created_at": time.time(),
        }

        # Add relations (edges)
        added_relations = []
        for rel in relations:
            target = rel.get("target")
            rel_type = rel.get("relation", "semantic")
            if rel_type not in self.RELATION_TYPES:
                rel_type = "semantic"

            edge = {
                "source": node_id,
                "target": target,
                "relation": rel_type,
                "weight": rel.get("weight", 1.0),
                "metadata": rel.get("metadata", {}),
            }
            entry["relations"].append(edge)
            added_relations.append(edge)

            # Update adjacency
            if node_id not in self._adjacency:
                self._adjacency[node_id] = []
            if target and target not in self._adjacency[node_id]:
                self._adjacency[node_id].append(target)

        self._nodes[node_id] = entry
        self._trim()

        return {
            "id": node_id,
            "added": True,
            "label": label,
            "type": node_type,
            "relations_count": len(added_relations),
            "total_nodes": len(self._nodes),
            "timestamp": time.time(),
        }

    # ── kg_query ────────────────────────────────────────────
    def kg_query(self, pattern: dict) -> dict:
        """Chercher dans le graphe par patron."""
        self._stats["queries"] += 1

        node_type = pattern.get("type")
        label_contains = pattern.get("label_contains", "")
        relation_type = pattern.get("relation_type")
        limit = pattern.get("limit", 50)

        matches = []
        for nid, node in self._nodes.items():
            if node_type and node["type"] != node_type:
                continue
            if label_contains and label_contains.lower() not in node["label"].lower():
                continue
            if relation_type:
                has_rel = any(
                    r["relation"] == relation_type for r in node.get("relations", [])
                )
                if not has_rel:
                    continue
            matches.append({
                "id": nid,
                "label": node["label"],
                "type": node["type"],
                "relations_count": len(node.get("relations", [])),
            })
            if len(matches) >= limit:
                break

        return {
            "queried": True,
            "pattern": pattern,
            "matches_count": len(matches),
            "matches": matches,
            "timestamp": time.time(),
        }

    # ── kg_explain ──────────────────────────────────────────
    def kg_explain(self, node: dict) -> dict:
        """Expliquer un nœud et ses connexions."""
        self._stats["explanations"] += 1

        node_id = node.get("id", "")
        entry = self._nodes.get(node_id)

        if not entry:
            return {
                "explained": False,
                "error": "node_not_found",
                "node_id": node_id,
                "timestamp": time.time(),
            }

        neighbors = self._adjacency.get(node_id, [])
        neighbor_details = []
        for n in neighbors:
            n_node = self._nodes.get(n)
            if n_node:
                neighbor_details.append({
                    "id": n,
                    "label": n_node["label"],
                    "type": n_node["type"],
                })

        relations_summary = {}
        for rel in entry.get("relations", []):
            rt = rel["relation"]
            relations_summary[rt] = relations_summary.get(rt, 0) + 1

        explanation = [
            f"Nœud '{entry['label']}' (type: {entry['type']}).",
            f"Connecté à {len(neighbors)} voisins.",
        ]
        for rt, count in relations_summary.items():
            explanation.append(f"  Relation '{rt}': {count} liens.")

        return {
            "id": f"exp_{uuid.uuid4().hex[:8]}",
            "explained": True,
            "node_id": node_id,
            "label": entry["label"],
            "type": entry["type"],
            "neighbors_count": len(neighbors),
            "neighbors": neighbor_details,
            "relations_summary": relations_summary,
            "explanation": explanation,
            "timestamp": time.time(),
        }

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "knowledge_graph_v2",
            "status": "ok",
            "total_nodes": len(self._nodes),
            "total_adjacency": sum(len(v) for v in self._adjacency.values()),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._nodes.clear()
        self._adjacency.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("KnowledgeGraphV2 restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._nodes) > 5000:
            oldest = sorted(self._nodes, key=lambda k: self._nodes[k]["created_at"])
            to_remove = oldest[:2500]
            for nid in to_remove:
                del self._nodes[nid]
                self._adjacency.pop(nid, None)
