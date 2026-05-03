"""
EXO v21 — CausalGraphEngine
Moteur causal : graphes causaux, chaînes causales, propagation,
analyse d'impact, détection de causes racines.

API:
  add_causal_relation(relation: dict)  → dict
  infer_causal_chain(query: dict)      → dict
  analyze_impact(event: dict)          → dict
  health_check() / restart() / get_stats()
"""

import logging
import time
import uuid

log = logging.getLogger("causal_graph_engine")


class CausalGraphEngine:
    """Moteur de graphe causal EXO v21."""

    def __init__(self, governance=None, knowledge_graph=None):
        self._governance = governance
        self._kg = knowledge_graph

        self._nodes: dict[str, dict] = {}
        self._edges: list[dict] = []
        self._stats = {
            "relations_added": 0,
            "chains_inferred": 0,
            "impacts_analyzed": 0,
        }

    # ── add_causal_relation ─────────────────────────────────
    def add_causal_relation(self, relation: dict) -> dict:
        """Ajouter une relation causale A → B."""
        self._stats["relations_added"] += 1

        cause = relation.get("cause", "")
        effect = relation.get("effect", "")
        strength = relation.get("strength", 1.0)
        context = relation.get("context", "global")

        # Ensure nodes exist
        if cause not in self._nodes:
            self._nodes[cause] = {"id": cause, "type": "entity",
                                   "created_at": time.time()}
        if effect not in self._nodes:
            self._nodes[effect] = {"id": effect, "type": "entity",
                                    "created_at": time.time()}

        eid = f"edge_{uuid.uuid4().hex[:8]}"
        edge = {
            "id": eid,
            "cause": cause,
            "effect": effect,
            "strength": strength,
            "context": context,
            "created_at": time.time(),
        }
        self._edges.append(edge)
        self._trim()

        return {
            "id": eid,
            "added": True,
            "cause": cause,
            "effect": effect,
            "strength": strength,
            "timestamp": time.time(),
        }

    # ── infer_causal_chain ──────────────────────────────────
    def infer_causal_chain(self, query: dict) -> dict:
        """Inférer la chaîne causale d'un nœud source à un nœud cible."""
        self._stats["chains_inferred"] += 1

        source = query.get("source", "")
        target = query.get("target", "")
        max_depth = query.get("max_depth", 10)

        chain = self._bfs_chain(source, target, max_depth)
        found = len(chain) > 0

        return {
            "id": f"chain_{uuid.uuid4().hex[:8]}",
            "inferred": True,
            "found": found,
            "source": source,
            "target": target,
            "chain": chain,
            "depth": len(chain),
            "timestamp": time.time(),
        }

    # ── analyze_impact ──────────────────────────────────────
    def analyze_impact(self, event: dict) -> dict:
        """Analyser l'impact causal d'un événement."""
        self._stats["impacts_analyzed"] += 1

        node = event.get("node", "")
        max_depth = event.get("max_depth", 5)

        impacted = self._find_effects(node, max_depth)

        # Find root causes
        root_causes = self._find_root_causes(node)

        return {
            "id": f"imp_{uuid.uuid4().hex[:8]}",
            "analyzed": True,
            "node": node,
            "impacted_nodes": impacted,
            "impact_count": len(impacted),
            "root_causes": root_causes,
            "root_causes_count": len(root_causes),
            "timestamp": time.time(),
        }

    def get_node(self, node_id: str) -> dict | None:
        return self._nodes.get(node_id)

    def list_edges(self) -> list[dict]:
        return [{"id": e["id"], "cause": e["cause"], "effect": e["effect"],
                 "strength": e["strength"]} for e in self._edges]

    # ── internals ───────────────────────────────────────────
    def _build_adjacency(self) -> dict[str, list[str]]:
        adj: dict[str, list[str]] = {}
        for e in self._edges:
            adj.setdefault(e["cause"], []).append(e["effect"])
        return adj

    def _build_reverse_adjacency(self) -> dict[str, list[str]]:
        rev: dict[str, list[str]] = {}
        for e in self._edges:
            rev.setdefault(e["effect"], []).append(e["cause"])
        return rev

    def _bfs_chain(self, source: str, target: str,
                   max_depth: int) -> list[str]:
        if source == target:
            return [source]
        adj = self._build_adjacency()
        visited: set[str] = {source}
        queue: list[tuple[str, list[str]]] = [(source, [source])]
        while queue:
            current, path = queue.pop(0)
            if len(path) > max_depth:
                break
            for neighbor in adj.get(current, []):
                if neighbor == target:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return []

    def _find_effects(self, node: str, max_depth: int) -> list[str]:
        adj = self._build_adjacency()
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(node, 0)]
        impacted: list[str] = []
        while queue:
            current, depth = queue.pop(0)
            if depth > max_depth:
                continue
            for neighbor in adj.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    impacted.append(neighbor)
                    queue.append((neighbor, depth + 1))
        return impacted

    def _find_root_causes(self, node: str) -> list[str]:
        rev = self._build_reverse_adjacency()
        visited: set[str] = set()
        queue = [node]
        roots: list[str] = []
        while queue:
            current = queue.pop(0)
            parents = rev.get(current, [])
            if not parents and current != node:
                roots.append(current)
            for parent in parents:
                if parent not in visited:
                    visited.add(parent)
                    queue.append(parent)
        return roots

    # ── health / restart / stats ────────────────────────────
    def health_check(self) -> dict:
        return {
            "service": "causal_graph_engine",
            "status": "ok",
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "stats": dict(self._stats),
        }

    def restart(self) -> None:
        self._nodes.clear()
        self._edges.clear()
        for k in self._stats:
            self._stats[k] = 0
        log.info("CausalGraphEngine restarted")

    def get_stats(self) -> dict:
        return dict(self._stats)

    def _trim(self) -> None:
        if len(self._edges) > 5000:
            self._edges = self._edges[-2500:]
