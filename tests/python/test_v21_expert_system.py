"""Tests EXO v21 — Système expert étendu (9 modules)."""

import pytest
import sys, os


# ═══════════════════════════════════════════════════════════
# AdvancedRuleEngine
# ═══════════════════════════════════════════════════════════
from advanced_rule_engine import AdvancedRuleEngine


class TestAdvancedRuleEngine:
    def _make(self):
        return AdvancedRuleEngine()

    def test_health_check(self):
        e = self._make()
        h = e.health_check()
        assert h["service"] == "advanced_rule_engine"
        assert h["status"] == "ok"

    def test_add_rule_and_evaluate(self):
        e = self._make()
        rule = {
            "name": "r1",
            "conditions": [{"key": "temp", "op": "gt", "value": 30}],
            "action": "alert_heat",
            "priority": 10,
        }
        r = e.add_rule(rule)
        assert r["added"] is True
        ctx = {"facts": {"temp": 35}}
        ev = e.evaluate_rules(ctx)
        assert ev["evaluated"] is True
        assert ev["fired_count"] >= 1

    def test_evaluate_no_match(self):
        e = self._make()
        e.add_rule({
            "name": "r1",
            "conditions": [{"key": "temp", "op": "gt", "value": 30}],
            "action": "alert_heat",
        })
        ev = e.evaluate_rules({"facts": {"temp": 20}})
        assert ev["evaluated"] is True
        assert ev["fired_count"] == 0

    def test_explain_rule(self):
        e = self._make()
        r = e.add_rule({"name": "r1", "conditions": [], "action": "noop"})
        ex = e.explain_rule({"rule_id": r["id"]})
        assert ex["explained"] is True

    def test_explain_rule_not_found(self):
        e = self._make()
        ex = e.explain_rule({"rule_id": "missing"})
        assert ex["explained"] is False

    def test_restart(self):
        e = self._make()
        e.add_rule({"name": "r1", "conditions": [], "action": "a"})
        e.restart()
        assert e.get_stats()["rules_added"] == 0

    def test_get_stats(self):
        e = self._make()
        s = e.get_stats()
        assert "rules_added" in s

    def test_eq_operator(self):
        e = self._make()
        e.add_rule({
            "name": "eq_test",
            "conditions": [{"key": "x", "op": "eq", "value": 5}],
            "action": "match_eq",
        })
        ev = e.evaluate_rules({"facts": {"x": 5}})
        assert ev["fired_count"] == 1

    def test_contains_operator(self):
        e = self._make()
        e.add_rule({
            "name": "contains_test",
            "conditions": [{"key": "text", "op": "contains", "value": "hello"}],
            "action": "match_contains",
        })
        ev = e.evaluate_rules({"facts": {"text": "say hello world"}})
        assert ev["fired_count"] == 1


# ═══════════════════════════════════════════════════════════
# CausalGraphEngine
# ═══════════════════════════════════════════════════════════
from causal_graph_engine import CausalGraphEngine


class TestCausalGraphEngine:
    def _make(self):
        return CausalGraphEngine()

    def test_health_check(self):
        h = self._make().health_check()
        assert h["service"] == "causal_graph_engine"
        assert h["status"] == "ok"

    def test_add_causal_relation(self):
        e = self._make()
        r = e.add_causal_relation({
            "cause": "rain", "effect": "wet_ground", "weight": 0.9,
        })
        assert r["added"] is True

    def test_infer_causal_chain(self):
        e = self._make()
        e.add_causal_relation({"cause": "A", "effect": "B"})
        e.add_causal_relation({"cause": "B", "effect": "C"})
        chain = e.infer_causal_chain({"source": "A", "target": "C"})
        assert chain["inferred"] is True
        assert chain["depth"] >= 2

    def test_chain_not_found(self):
        e = self._make()
        e.add_causal_relation({"cause": "A", "effect": "B"})
        chain = e.infer_causal_chain({"source": "A", "target": "Z"})
        assert chain["inferred"] is True
        assert chain["depth"] == 0

    def test_analyze_impact(self):
        e = self._make()
        e.add_causal_relation({"cause": "fire", "effect": "smoke", "weight": 0.8})
        imp = e.analyze_impact({"node": "fire"})
        assert imp["analyzed"] is True
        assert imp["impact_count"] >= 1

    def test_restart(self):
        e = self._make()
        e.add_causal_relation({"cause": "A", "effect": "B"})
        e.restart()
        assert e.get_stats()["relations_added"] == 0

    def test_get_stats(self):
        s = self._make().get_stats()
        assert "relations_added" in s


# ═══════════════════════════════════════════════════════════
# DeductiveReasoner
# ═══════════════════════════════════════════════════════════
from deductive_reasoner import DeductiveReasoner


class TestDeductiveReasoner:
    def _make(self):
        return DeductiveReasoner()

    def test_health_check(self):
        h = self._make().health_check()
        assert h["service"] == "deductive_reasoner"
        assert h["status"] == "ok"

    def test_deduce_modus_ponens(self):
        e = self._make()
        q = {
            "premises": ["rain"],
            "rules": [
                {"type": "modus_ponens", "antecedent": "rain", "consequent": "wet"},
            ],
        }
        r = e.deduce(q)
        assert r["deduced"] is True
        assert len(r["conclusions"]) >= 1

    def test_deduce_modus_tollens(self):
        e = self._make()
        q = {
            "premises": ["not_wet"],
            "rules": [
                {"type": "modus_tollens", "antecedent": "rain", "consequent": "wet"},
            ],
        }
        r = e.deduce(q)
        assert r["deduced"] is True

    def test_verify_deduction(self):
        e = self._make()
        e.deduce({
            "premises": [{"type": "modus_ponens", "if": "A", "then": "B"}],
            "facts": ["A"],
        })
        v = e.verify_deduction({})
        assert v["verified"] is True

    def test_verify_empty(self):
        e = self._make()
        v = e.verify_deduction({})
        assert v["verified"] is True
        assert v["valid"] is True  # no steps = vacuously valid

    def test_restart(self):
        e = self._make()
        e.deduce({"premises": [], "facts": []})
        e.restart()
        assert e.get_stats()["deductions"] == 0

    def test_get_stats(self):
        s = self._make().get_stats()
        assert "deductions" in s


# ═══════════════════════════════════════════════════════════
# InductiveReasoner
# ═══════════════════════════════════════════════════════════
from inductive_reasoner import InductiveReasoner


class TestInductiveReasoner:
    def _make(self):
        return InductiveReasoner()

    def test_health_check(self):
        h = self._make().health_check()
        assert h["service"] == "inductive_reasoner"
        assert h["status"] == "ok"

    def test_induce(self):
        e = self._make()
        r = e.induce({
            "observations": [
                {"pattern": "bird_flies", "count": 10},
                {"pattern": "bird_flies", "count": 5},
                {"pattern": "fish_swims", "count": 3},
            ],
        })
        assert r["induced"] is True
        assert r["rules_count"] >= 1

    def test_generalize(self):
        e = self._make()
        r = e.generalize({
            "examples": [
                {"color": "red", "shape": "round", "size": 5},
                {"color": "red", "shape": "round", "size": 8},
                {"color": "red", "shape": "square", "size": 3},
            ],
        })
        assert r["generalized"] is True
        assert "common_properties" in r

    def test_restart(self):
        e = self._make()
        e.induce({"observations": []})
        e.restart()
        assert e.get_stats()["inductions"] == 0

    def test_get_stats(self):
        s = self._make().get_stats()
        assert "inductions" in s


# ═══════════════════════════════════════════════════════════
# AbductiveReasoner
# ═══════════════════════════════════════════════════════════
from abductive_reasoner import AbductiveReasoner


class TestAbductiveReasoner:
    def _make(self):
        return AbductiveReasoner()

    def test_health_check(self):
        h = self._make().health_check()
        assert h["service"] == "abductive_reasoner"
        assert h["status"] == "ok"

    def test_abduct(self):
        e = self._make()
        r = e.abduct({
            "observation": "wet_ground",
            "known_facts": ["rain_causes_wet_ground"],
            "candidate_causes": [
                {"name": "rain", "evidence": ["rain_causes_wet_ground"]},
                {"name": "sprinkler", "evidence": []},
            ],
        })
        assert r["abducted"] is True
        assert r["hypotheses_count"] >= 1

    def test_explain_best_hypothesis(self):
        e = self._make()
        e.abduct({
            "observations": ["smoke"],
            "known_facts": [],
            "candidates": [
                {"cause": "fire", "effects": ["smoke", "heat"]},
            ],
        })
        ex = e.explain_best_hypothesis()
        assert ex["explained"] is True

    def test_explain_no_hypothesis(self):
        e = self._make()
        ex = e.explain_best_hypothesis()
        assert ex["explained"] is False

    def test_restart(self):
        e = self._make()
        e.abduct({"observations": [], "known_facts": [], "candidates": []})
        e.restart()
        assert e.get_stats()["abductions"] == 0

    def test_get_stats(self):
        s = self._make().get_stats()
        assert "abductions" in s


# ═══════════════════════════════════════════════════════════
# ConstraintSolver
# ═══════════════════════════════════════════════════════════
from constraint_solver import ConstraintSolver


class TestConstraintSolver:
    def _make(self):
        return ConstraintSolver()

    def test_health_check(self):
        h = self._make().health_check()
        assert h["service"] == "constraint_solver"
        assert h["status"] == "ok"

    def test_solve_constraints_satisfied(self):
        e = self._make()
        r = e.solve_constraints({
            "variables": {"x": 10, "y": 5},
            "constraints": [
                {"name": "c1", "variable": "x", "op": "gt", "value": 5},
                {"name": "c2", "variable": "y", "op": "eq", "value": 5},
            ],
        })
        assert r["solved"] is True
        assert r["solvable"] is True
        assert r["violated_count"] == 0

    def test_solve_constraints_violated(self):
        e = self._make()
        r = e.solve_constraints({
            "variables": {"x": 3},
            "constraints": [
                {"name": "c1", "variable": "x", "op": "gt", "value": 5},
            ],
        })
        assert r["solved"] is True
        assert r["solvable"] is False
        assert r["violated_count"] == 1

    def test_check_constraints(self):
        e = self._make()
        r = e.check_constraints({
            "variables": {"x": 10},
            "constraints": [
                {"name": "c1", "variable": "x", "op": "gte", "value": 10},
            ],
        })
        assert r["checked"] is True
        assert r["consistent"] is True

    def test_explain_constraints(self):
        e = self._make()
        e.solve_constraints({
            "variables": {"x": 10},
            "constraints": [
                {"name": "c1", "variable": "x", "op": "eq", "value": 10},
            ],
        })
        ex = e.explain_constraints()
        assert ex["explained"] is True

    def test_explain_no_solutions(self):
        e = self._make()
        ex = e.explain_constraints()
        assert ex["explained"] is False

    def test_restart(self):
        e = self._make()
        e.solve_constraints({"variables": {}, "constraints": []})
        e.restart()
        assert e.get_stats()["solved"] == 0

    def test_get_stats(self):
        s = self._make().get_stats()
        assert "solved" in s


# ═══════════════════════════════════════════════════════════
# LogicalCoherenceEngine
# ═══════════════════════════════════════════════════════════
from logical_coherence_engine import LogicalCoherenceEngine


class TestLogicalCoherenceEngine:
    def _make(self):
        return LogicalCoherenceEngine()

    def test_health_check(self):
        h = self._make().health_check()
        assert h["service"] == "logical_coherence_engine"
        assert h["status"] == "ok"

    def test_check_logical_consistency(self):
        e = self._make()
        r = e.check_logical_consistency()
        assert r["checked"] is True
        assert r["consistent"] is True

    def test_enforce_logical_consistency(self):
        e = self._make()
        r = e.enforce_logical_consistency()
        assert r["enforced"] is True
        assert r["consistent_after"] is True

    def test_with_rule_engine(self):
        re = AdvancedRuleEngine()
        e = LogicalCoherenceEngine(rule_engine=re)
        r = e.check_logical_consistency()
        assert r["checked"] is True

    def test_with_deductive(self):
        d = DeductiveReasoner()
        e = LogicalCoherenceEngine(deductive=d)
        r = e.check_logical_consistency()
        assert r["checked"] is True

    def test_restart(self):
        e = self._make()
        e.check_logical_consistency()
        e.restart()
        assert e.get_stats()["checks"] == 0

    def test_get_stats(self):
        s = self._make().get_stats()
        assert "checks" in s


# ═══════════════════════════════════════════════════════════
# KnowledgeGraphV2
# ═══════════════════════════════════════════════════════════
from knowledge_graph_v2 import KnowledgeGraphV2


class TestKnowledgeGraphV2:
    def _make(self):
        return KnowledgeGraphV2()

    def test_health_check(self):
        h = self._make().health_check()
        assert h["service"] == "knowledge_graph_v2"
        assert h["status"] == "ok"

    def test_kg_add(self):
        e = self._make()
        r = e.kg_add({
            "id": "n1", "label": "Paris", "type": "city",
            "relations": [{"target": "n2", "relation": "hierarchical"}],
        })
        assert r["added"] is True
        assert r["id"] == "n1"

    def test_kg_query_by_type(self):
        e = self._make()
        e.kg_add({"id": "n1", "label": "Paris", "type": "city"})
        e.kg_add({"id": "n2", "label": "France", "type": "country"})
        r = e.kg_query({"type": "city"})
        assert r["queried"] is True
        assert r["matches_count"] == 1

    def test_kg_query_by_label(self):
        e = self._make()
        e.kg_add({"id": "n1", "label": "Paris", "type": "city"})
        r = e.kg_query({"label_contains": "par"})
        assert r["matches_count"] == 1

    def test_kg_explain(self):
        e = self._make()
        e.kg_add({
            "id": "n1", "label": "Paris", "type": "city",
            "relations": [{"target": "n2", "relation": "hierarchical"}],
        })
        e.kg_add({"id": "n2", "label": "France", "type": "country"})
        ex = e.kg_explain({"id": "n1"})
        assert ex["explained"] is True
        assert ex["neighbors_count"] >= 1

    def test_kg_explain_not_found(self):
        e = self._make()
        ex = e.kg_explain({"id": "missing"})
        assert ex["explained"] is False

    def test_restart(self):
        e = self._make()
        e.kg_add({"id": "n1", "label": "X", "type": "t"})
        e.restart()
        assert e.get_stats()["nodes_added"] == 0

    def test_get_stats(self):
        s = self._make().get_stats()
        assert "nodes_added" in s

    def test_relation_types(self):
        e = self._make()
        r = e.kg_add({
            "id": "n1", "label": "A", "type": "x",
            "relations": [{"target": "n2", "relation": "causal"}],
        })
        assert r["relations_count"] == 1


# ═══════════════════════════════════════════════════════════
# SymbolicExplainabilityEngineV2
# ═══════════════════════════════════════════════════════════
from symbolic_explainability_v2 import SymbolicExplainabilityEngineV2


class TestSymbolicExplainabilityEngineV2:
    def _make(self):
        d = DeductiveReasoner()
        i = InductiveReasoner()
        a = AbductiveReasoner()
        c = CausalGraphEngine()
        return SymbolicExplainabilityEngineV2(
            deductive=d, inductive=i, abductive=a, causal_engine=c)

    def test_health_check(self):
        h = self._make().health_check()
        assert h["service"] == "symbolic_explainability_v2"
        assert h["status"] == "ok"

    def test_explain_deduction(self):
        e = self._make()
        r = e.explain_deduction()
        assert r["explained"] is True
        assert r["type"] == "deduction"

    def test_explain_induction(self):
        e = self._make()
        r = e.explain_induction()
        assert r["explained"] is True
        assert r["type"] == "induction"

    def test_explain_abduction(self):
        e = self._make()
        r = e.explain_abduction()
        assert r["explained"] is True
        assert r["type"] == "abduction"

    def test_explain_causal_chain(self):
        e = self._make()
        r = e.explain_causal_chain()
        assert r["explained"] is True
        assert r["type"] == "causal_chain"

    def test_restart(self):
        e = self._make()
        e.explain_deduction()
        e.restart()
        assert e.get_stats()["deduction_explanations"] == 0

    def test_get_stats(self):
        s = self._make().get_stats()
        assert "deduction_explanations" in s

    def test_no_deps(self):
        e = SymbolicExplainabilityEngineV2()
        r = e.explain_deduction()
        assert r["explained"] is True
