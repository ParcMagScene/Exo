"""
EXO v15 — KnowledgeGraph (Connaissances structurées)
Graphe de connaissances : nœuds, relations, requêtes, chemins.

API:
  kg_add(node, relation, target)   → str  (edge_id)
  kg_remove(edge_id)               → bool
  kg_query(pattern)                → list[dict]
  kg_explain(node)                 → dict
  kg_get_node(name)                → dict | None
  kg_neighbors(node)               → list[dict]
  kg_path(source, target)          → list[dict]
  health_check()                   → dict
  restart()                        → None
  get_stats()                      → dict
"""

import logging
import time
import uuid
from collections import defaultdict
from typing import Any

log = logging.getLogger("knowledge_graph")


class KnowledgeGraph:
    """Graphe de connaissances structuré EXO v15."""

    def __init__(self, meta_memory=None):
        self._memory = meta_memory
        self._nodes: dict[str, dict] = {}            # name → metadata
        self._edges: dict[str, dict] = {}            # edge_id → edge
        self._adjacency: dict[str, list[str]] = defaultdict(list)  # node → [edge_ids]
        self._stats = {
            "nodes_added": 0,
            "edges_added": 0,
            "edges_removed": 0,
            "queries_run": 0,
            "explanations": 0,
        }

    # ── kg_add ──────────────────────────────────────────────
    def kg_add(self, node: str, relation: str, target: str) -> str:
        """Add a directed edge: node --relation--> target."""
        if not node or not relation or not target:
            return ""

        # Ensure nodes exist
        self._ensure_node(node)
        self._ensure_node(target)

        edge_id = f"e_{uuid.uuid4().hex[:8]}"
        edge = {
            "id": edge_id,
            "source": node,
            "relation": relation,
            "target": target,
            "created": time.time(),
        }
        self._edges[edge_id] = edge
        self._adjacency[node].append(edge_id)
        self._adjacency[target].append(edge_id)
        self._stats["edges_added"] += 1
        return edge_id

    # ── kg_remove ───────────────────────────────────────────
    def kg_remove(self, edge_id: str) -> bool:
        edge = self._edges.pop(edge_id, None)
        if not edge:
            return False
        src = edge["source"]
        tgt = edge["target"]
        if edge_id in self._adjacency.get(src, []):
            self._adjacency[src].remove(edge_id)
        if edge_id in self._adjacency.get(tgt, []):
            self._adjacency[tgt].remove(edge_id)
        self._stats["edges_removed"] += 1
        return True

    # ── kg_query ────────────────────────────────────────────
    def kg_query(self, pattern: dict) -> list[dict]:
        """Query edges matching a pattern.

        pattern = {"source": ..., "relation": ..., "target": ...}
        Any field can be omitted (wildcard).
        """
        self._stats["queries_run"] += 1
        results = []
        src = pattern.get("source")
        rel = pattern.get("relation")
        tgt = pattern.get("target")

        for edge in self._edges.values():
            if src and edge["source"] != src:
                continue
            if rel and edge["relation"] != rel:
                continue
            if tgt and edge["target"] != tgt:
                continue
            results.append(edge)
        return results

    # ── kg_explain ──────────────────────────────────────────
    def kg_explain(self, node: str) -> dict:
        """Explain a node: all edges, neighbors, summary."""
        self._stats["explanations"] += 1
        if node not in self._nodes:
            return {"node": node, "found": False,
                    "explanation": f"Nœud '{node}' introuvable."}

        outgoing = self.kg_query({"source": node})
        incoming = self.kg_query({"target": node})

        lines = [f"Nœud: {node}"]
        meta = self._nodes[node]
        if meta.get("domain"):
            lines.append(f"  Domaine: {meta['domain']}")

        if outgoing:
            lines.append(f"  Relations sortantes ({len(outgoing)}):")
            for e in outgoing[:10]:
                lines.append(f"    → {e['relation']} → {e['target']}")
        if incoming:
            lines.append(f"  Relations entrantes ({len(incoming)}):")
            for e in incoming[:10]:
                lines.append(f"    ← {e['source']} ← {e['relation']}")

        return {
            "node": node,
            "found": True,
            "metadata": meta,
            "outgoing": outgoing,
            "incoming": incoming,
            "explanation": "\n".join(lines),
        }

    # ── kg_get_node ─────────────────────────────────────────
    def kg_get_node(self, name: str) -> dict | None:
        return self._nodes.get(name)

    # ── kg_neighbors ────────────────────────────────────────
    def kg_neighbors(self, node: str) -> list[dict]:
        """Get direct neighbors of a node."""
        neighbors = {}
        for eid in self._adjacency.get(node, []):
            edge = self._edges.get(eid)
            if not edge:
                continue
            other = edge["target"] if edge["source"] == node else edge["source"]
            if other != node:
                neighbors[other] = {
                    "node": other,
                    "relation": edge["relation"],
                    "direction": "out" if edge["source"] == node else "in",
                }
        return list(neighbors.values())

    # ── kg_path ─────────────────────────────────────────────
    def kg_path(self, source: str, target: str, max_depth: int = 5) -> list[dict]:
        """Find a path from source to target (BFS)."""
        if source not in self._nodes or target not in self._nodes:
            return []
        if source == target:
            return [{"node": source}]

        visited: set[str] = {source}
        queue: list[tuple[str, list[dict]]] = [(source, [{"node": source}])]

        while queue:
            current, path = queue.pop(0)
            if len(path) > max_depth:
                continue

            for eid in self._adjacency.get(current, []):
                edge = self._edges.get(eid)
                if not edge:
                    continue
                next_node = (edge["target"]
                             if edge["source"] == current
                             else edge["source"])
                if next_node in visited:
                    continue
                visited.add(next_node)
                new_path = path + [{
                    "node": next_node,
                    "via": edge["relation"],
                    "edge_id": eid,
                }]
                if next_node == target:
                    return new_path
                queue.append((next_node, new_path))
        return []

    # ── internal ────────────────────────────────────────────
    def _ensure_node(self, name: str) -> None:
        if name not in self._nodes:
            self._nodes[name] = {
                "name": name,
                "domain": "",
                "created": time.time(),
            }
            self._stats["nodes_added"] += 1

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "knowledge_graph",
            "status": "ok",
            "nodes": len(self._nodes),
            "edges": len(self._edges),
        }

    def restart(self) -> None:
        self._nodes.clear()
        self._edges.clear()
        self._adjacency.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("KnowledgeGraph restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)
