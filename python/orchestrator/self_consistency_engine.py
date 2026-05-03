"""
EXO v12 — SelfConsistencyEngine (Auto-cohérence)
Détecte les contradictions, divergences entre modules,
et incohérences entre intention et actions.

API:
  check_consistency(plan)                       → dict
  check_consistency_reasoning(reasoning_trace)  → dict
  enforce_consistency()                         → dict
  get_stats()                                   → dict
"""

import logging
import time
from typing import Any

log = logging.getLogger("self_consistency")


class SelfConsistencyEngine:
    """Moteur d'auto-cohérence EXO v12."""

    def __init__(self, meta_memory, meta_verifier=None, governance=None):
        """
        Args:
            meta_memory: MetaMemory instance.
            meta_verifier: MetaVerifier (optional) for verification support.
            governance: AutoGovernance (optional).
        """
        self._memory = meta_memory
        self._verifier = meta_verifier
        self._governance = governance
        self._history: list[dict] = []
        self._stats = {
            "plan_checks": 0,
            "reasoning_checks": 0,
            "enforcements": 0,
            "inconsistencies_found": 0,
        }

    # ── Plan consistency ─────────────────────────────────────
    def check_consistency(self, plan: dict) -> dict:
        """Check plan for internal consistency.

        Detects contradictions between steps, loops, and broken deps.
        """
        steps = plan.get("steps", [])
        goal = plan.get("goal", "")
        inconsistencies = []

        # 1. Detect circular dependencies
        circular = self._detect_circular_deps(steps)
        inconsistencies.extend(circular)

        # 2. Detect conflicting actions
        conflicts = self._detect_conflicting_actions(steps)
        inconsistencies.extend(conflicts)

        # 3. Detect goal-action misalignment
        if goal:
            misaligned = self._detect_goal_misalignment(steps, goal)
            inconsistencies.extend(misaligned)

        # 4. Cross-check with MetaMemory learned patterns
        memory_conflicts = self._check_memory_consistency(steps)
        inconsistencies.extend(memory_conflicts)

        # 5. Use verifier if available
        verification = None
        if self._verifier:
            verification = self._verifier.meta_verify(plan)

        self._stats["plan_checks"] += 1
        self._stats["inconsistencies_found"] += len(inconsistencies)

        consistent = len(inconsistencies) == 0
        result = {
            "type": "plan_consistency",
            "consistent": consistent,
            "inconsistencies": inconsistencies,
            "verification": verification,
            "step_count": len(steps),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── Reasoning consistency ────────────────────────────────
    def check_consistency_reasoning(self, reasoning_trace: dict) -> dict:
        """Check reasoning trace for internal consistency.

        Detects contradictions between steps, conclusion misalignment.
        """
        steps = reasoning_trace.get("steps", [])
        conclusion = reasoning_trace.get("conclusion", "")
        inconsistencies = []

        # 1. Detect step contradictions
        for i, step_a in enumerate(steps):
            text_a = step_a.get("text", "") if isinstance(step_a, dict) else str(step_a)
            for j, step_b in enumerate(steps[i + 1:], start=i + 1):
                text_b = step_b.get("text", "") if isinstance(step_b, dict) else str(step_b)
                if self._texts_contradict(text_a, text_b):
                    inconsistencies.append({
                        "type": "step_contradiction",
                        "step_indices": [i, j],
                        "detail": f"Steps {i} and {j} appear contradictory",
                    })

        # 2. Check conclusion alignment with steps
        if conclusion and steps:
            conclusion_words = set(conclusion.lower().split())
            supporting_steps = 0
            for step in steps:
                text = step.get("text", "") if isinstance(step, dict) else str(step)
                step_words = set(text.lower().split())
                if step_words & conclusion_words:
                    supporting_steps += 1
            if supporting_steps == 0:
                inconsistencies.append({
                    "type": "unsupported_conclusion",
                    "detail": "Conclusion has no lexical overlap with reasoning steps",
                })

        # 3. Check for logic reversals
        for i, step in enumerate(steps):
            text = step.get("text", "") if isinstance(step, dict) else str(step)
            result_val = step.get("result") if isinstance(step, dict) else None
            if result_val is not None:
                # Check if a later step contradicts the result
                for j, later in enumerate(steps[i + 1:], start=i + 1):
                    later_text = later.get("text", "") if isinstance(later, dict) else str(later)
                    if str(result_val).lower() in later_text.lower() and "pas" in later_text.lower():
                        inconsistencies.append({
                            "type": "result_reversal",
                            "step_indices": [i, j],
                            "detail": f"Step {j} negates result of step {i}",
                        })

        self._stats["reasoning_checks"] += 1
        self._stats["inconsistencies_found"] += len(inconsistencies)

        consistent = len(inconsistencies) == 0
        result = {
            "type": "reasoning_consistency",
            "consistent": consistent,
            "inconsistencies": inconsistencies,
            "step_count": len(steps),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── Enforce consistency ──────────────────────────────────
    def enforce_consistency(self) -> dict:
        """Enforce global consistency across MetaMemory.

        Detects and reports conflicting entries in MetaMemory.
        """
        actions = []

        all_entries = self._memory.list_entries(limit=5000)

        # Group entries by category
        by_category: dict[str, list] = {}
        for entry in all_entries:
            cat = entry.get("category", "unknown")
            by_category.setdefault(cat, []).append(entry)

        # Check for duplicate keys within same category
        for cat, entries in by_category.items():
            seen_keys: dict[str, list] = {}
            for entry in entries:
                key = entry.get("key", "")
                seen_keys.setdefault(key, []).append(entry)
            for key, dupes in seen_keys.items():
                if len(dupes) > 1:
                    # Keep the most recent, flag the rest
                    sorted_dupes = sorted(
                        dupes,
                        key=lambda e: e.get("updated_at", e.get("created_at", 0)),
                        reverse=True,
                    )
                    for old in sorted_dupes[1:]:
                        actions.append({
                            "action": "duplicate_detected",
                            "category": cat,
                            "key": key,
                            "entry_id": old.get("id", ""),
                        })

        # Check for conflicting preferences
        prefs = by_category.get("preference", [])
        pref_map: dict[str, list] = {}
        for p in prefs:
            pref_map.setdefault(p.get("key", ""), []).append(p)
        for key, vals in pref_map.items():
            if len(vals) > 1:
                values = [v.get("value") for v in vals]
                if len(set(str(v) for v in values)) > 1:
                    actions.append({
                        "action": "conflicting_preferences",
                        "key": key,
                        "values": values,
                    })

        self._stats["enforcements"] += 1

        result = {
            "type": "consistency_enforcement",
            "actions": actions,
            "action_count": len(actions),
            "entries_checked": len(all_entries),
            "timestamp": time.time(),
        }
        self._record(result)
        return result

    # ── Stats ────────────────────────────────────────────────
    def get_stats(self) -> dict:
        return dict(self._stats)

    # ── Internal ─────────────────────────────────────────────
    def _detect_circular_deps(self, steps: list) -> list[dict]:
        """Detect circular dependencies in steps."""
        issues = []
        # Build adjacency map
        adj: dict[Any, list] = {}
        id_map: dict[Any, int] = {}
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            sid = step.get("id", i)
            id_map[sid] = i
            deps = step.get("depends_on", [])
            adj[sid] = deps

        # Simple cycle detection via DFS
        visited: set = set()
        in_stack: set = set()

        def dfs(node):
            if node in in_stack:
                return True  # cycle
            if node in visited:
                return False
            visited.add(node)
            in_stack.add(node)
            for dep in adj.get(node, []):
                if dfs(dep):
                    return True
            in_stack.discard(node)
            return False

        for sid in adj:
            if dfs(sid):
                issues.append({
                    "type": "circular_dependency",
                    "detail": f"Circular dependency detected involving step {sid}",
                })
                break  # one report is enough

        return issues

    def _detect_conflicting_actions(self, steps: list) -> list[dict]:
        """Detect conflicting actions (e.g., enable then disable)."""
        issues = []
        opposites = [
            ("enable", "disable"), ("start", "stop"),
            ("create", "delete"), ("add", "remove"),
            ("open", "close"), ("activate", "deactivate"),
        ]
        action_pairs: list[tuple[int, str, str]] = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            action = (step.get("tool", "") or step.get("action", "")).lower()
            target = (step.get("target", "") or step.get("description", "")).lower()
            action_pairs.append((i, action, target))

        for i, (idx_a, act_a, tgt_a) in enumerate(action_pairs):
            for idx_b, act_b, tgt_b in action_pairs[i + 1:]:
                if not tgt_a or not tgt_b or tgt_a != tgt_b:
                    continue
                for pos, neg in opposites:
                    if (pos in act_a and neg in act_b) or (neg in act_a and pos in act_b):
                        issues.append({
                            "type": "conflicting_actions",
                            "step_indices": [idx_a, idx_b],
                            "detail": f"Steps {idx_a} ({act_a}) and {idx_b} ({act_b}) conflict on '{tgt_a}'",
                        })
        return issues

    def _detect_goal_misalignment(self, steps: list, goal: str) -> list[dict]:
        """Detect steps that don't contribute to the goal."""
        issues = []
        goal_words = set(goal.lower().split()) - {
            "le", "la", "les", "de", "du", "des",
            "the", "a", "an", "to", "of", "for", "in",
        }
        if not goal_words:
            return issues

        unaligned_count = 0
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            desc = step.get("description", "")
            tool = step.get("tool", "")
            text = f"{desc} {tool}".lower()
            if not set(text.split()) & goal_words:
                unaligned_count += 1

        if unaligned_count > len(steps) * 0.6 and steps:
            issues.append({
                "type": "goal_misalignment",
                "detail": f"{unaligned_count}/{len(steps)} steps don't align with goal",
            })
        return issues

    def _check_memory_consistency(self, steps: list) -> list[dict]:
        """Cross-check steps with learned patterns in MetaMemory."""
        issues = []
        # Check if any step uses a tool known to fail
        strategies = self._memory.meta_get("strategy")
        failed_tools: set[str] = set()
        for entry in strategies:
            val = entry.get("value", {})
            if isinstance(val, dict) and val.get("feedback_type") == "negative":
                tool = entry.get("key", "")
                if tool:
                    failed_tools.add(tool.lower())

        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            tool = step.get("tool", "").lower()
            if tool and tool in failed_tools:
                issues.append({
                    "type": "known_failure_tool",
                    "step_index": i,
                    "detail": f"Step {i} uses tool '{tool}' known to fail",
                })
        return issues

    def _texts_contradict(self, text_a: str, text_b: str) -> bool:
        """Simple heuristic to check if two texts contradict each other."""
        a = text_a.lower().strip()
        b = text_b.lower().strip()
        if not a or not b:
            return False

        negation_pairs = [
            ("vrai", "faux"), ("true", "false"),
            ("oui", "non"), ("yes", "no"),
            ("possible", "impossible"),
            ("correct", "incorrect"),
        ]
        for pos, neg in negation_pairs:
            if (pos in a and neg in b) or (neg in a and pos in b):
                words_a = set(a.split()) - {pos, neg}
                words_b = set(b.split()) - {pos, neg}
                if len(words_a & words_b) >= 2:
                    return True
        return False

    def _record(self, result: dict) -> None:
        self._history.append(result)
        if len(self._history) > 300:
            self._history = self._history[-300:]
