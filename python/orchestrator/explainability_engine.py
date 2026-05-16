"""ExplainabilityEngine — façade unifiée v2..v6.

Consolide les 5 moteurs d'explainability historiques (v2, v3, v4, v5, v6)
en une seule API publique. Aucune duplication : la façade instancie en
interne les versions historiques (archivées sous `_archived/`) et délègue
chaque méthode publique à la version correspondante.

Construction :
    eng = ExplainabilityEngine(
        meta_memory,
        knowledge_graph=v15["knowledge_graph"],
        inference_eng=v15["inference"],
        autoexplanation=v11["explanation"],
        registry=v14["registry"],
        audit_log=v16["audit_log"],
    )

Les sous-moteurs ne sont créés que si tous leurs collaborateurs sont fournis
(activation progressive selon les versions chargées).

API publique = union des méthodes des 5 versions :
- v2  : explain_plan, explain_reasoning, explain_meta_decision
- v3  : explain_simulation, explain_prediction, explain_future (str)
- v4  : explain_agent_decision, explain_global_decision,
        explain_conflict_resolution, explain_orchestration
- v5  : explain_decision, explain_inference, explain_future (dict),
        explain_conflict, explain_full
- v6  : explain_initiative, explain_emergence, explain_governor_decision,
        explain_regulation, explain_collaboration, explain_full_v16

Conflit `explain_future` : v5 (dict) prime ; pour la signature str de v3
utiliser `explain_future_str()`.
Méthodes communes (`get_stats`, `health_check`, `restart`,
`get_explanations`/`get_explanation_log`) agrégées.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("exo.explainability")

# Imports des versions historiques (zéro duplication de code)
from _archived.explainability_engine_v2 import ExplainabilityEngineV2
from _archived.explainability_engine_v3 import ExplainabilityEngineV3
from _archived.explainability_engine_v4 import ExplainabilityEngineV4
from _archived.explainability_engine_v6 import ExplainabilityEngineV6
from explainability_engine_v5 import ExplainabilityEngineV5


class ExplainabilityEngine:
    """Façade unifiée pour les explainability engines v2..v6."""

    def __init__(
        self,
        meta_memory: Any,
        knowledge_graph: Any = None,
        inference_eng: Any = None,
        autoexplanation: Any = None,
        registry: Any = None,
        audit_log: Any = None,
    ) -> None:
        self._meta_memory = meta_memory

        # v5 = base (signatures dict, méthodes principales)
        self._v5 = (
            ExplainabilityEngineV5(meta_memory, knowledge_graph, inference_eng)
            if knowledge_graph is not None and inference_eng is not None
            else None
        )
        # v2 = explainability historique sur plan/reasoning/meta_decision
        self._v2 = (
            ExplainabilityEngineV2(meta_memory, autoexplanation)
            if autoexplanation is not None
            else None
        )
        # v3 = futur/simulation/prédiction (forme str)
        self._v3 = (
            ExplainabilityEngineV3(meta_memory, self._v2)
            if self._v2 is not None
            else None
        )
        # v4 = explainability multi-agents
        self._v4 = (
            ExplainabilityEngineV4(meta_memory, registry, self._v3)
            if self._v3 is not None and registry is not None
            else None
        )
        # v6 = explainability cognitive autonomie/émergence
        self._v6 = (
            ExplainabilityEngineV6(meta_memory, self._v5, audit_log)
            if self._v5 is not None and audit_log is not None
            else None
        )

        active = [n for n, e in (
            ("v2", self._v2), ("v3", self._v3), ("v4", self._v4),
            ("v5", self._v5), ("v6", self._v6),
        ) if e is not None]
        logger.info("ExplainabilityEngine initialised (active=%s)", active)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _require(engine: Any, name: str) -> Any:
        if engine is None:
            raise RuntimeError(
                f"ExplainabilityEngine: backend '{name}' not available "
                "(missing collaborators at init time)"
            )
        return engine

    # ------------------------------------------------------------------
    # v2 API
    # ------------------------------------------------------------------
    def explain_plan(self, plan: dict) -> str:
        return self._require(self._v2, "v2").explain_plan(plan)

    def explain_reasoning(self, reasoning_trace: dict) -> str:
        return self._require(self._v2, "v2").explain_reasoning(reasoning_trace)

    def explain_meta_decision(self, meta_decision: dict) -> str:
        return self._require(self._v2, "v2").explain_meta_decision(meta_decision)

    # ------------------------------------------------------------------
    # v3 API
    # ------------------------------------------------------------------
    def explain_simulation(self, simulation: dict) -> str:
        return self._require(self._v3, "v3").explain_simulation(simulation)

    def explain_prediction(self, prediction: dict) -> str:
        return self._require(self._v3, "v3").explain_prediction(prediction)

    def explain_future_str(self, future: dict) -> str:
        """v3 forme str (pour rétrocompat). Voir aussi explain_future (dict)."""
        return self._require(self._v3, "v3").explain_future(future)

    # ------------------------------------------------------------------
    # v4 API
    # ------------------------------------------------------------------
    def explain_agent_decision(self, agent_name: str) -> dict:
        return self._require(self._v4, "v4").explain_agent_decision(agent_name)

    def explain_global_decision(self, decision: dict) -> dict:
        return self._require(self._v4, "v4").explain_global_decision(decision)

    def explain_conflict_resolution(self, resolution: dict) -> dict:
        return self._require(self._v4, "v4").explain_conflict_resolution(resolution)

    def explain_orchestration(self, orch_result: dict) -> dict:
        return self._require(self._v4, "v4").explain_orchestration(orch_result)

    # ------------------------------------------------------------------
    # v5 API (base — signatures dict)
    # ------------------------------------------------------------------
    def explain_decision(self, decision: dict) -> dict:
        return self._require(self._v5, "v5").explain_decision(decision)

    def explain_inference(self, inference: dict) -> dict:
        return self._require(self._v5, "v5").explain_inference(inference)

    def explain_future(self, future: dict) -> dict:
        """v5 forme dict (privilégiée). Pour v3 forme str voir explain_future_str."""
        return self._require(self._v5, "v5").explain_future(future)

    def explain_conflict(self, conflict: dict) -> dict:
        return self._require(self._v5, "v5").explain_conflict(conflict)

    def explain_full(self, session: dict) -> dict:
        return self._require(self._v5, "v5").explain_full(session)

    # ------------------------------------------------------------------
    # v6 API
    # ------------------------------------------------------------------
    def explain_initiative(self, initiative: dict) -> dict:
        return self._require(self._v6, "v6").explain_initiative(initiative)

    def explain_emergence(self, emergence: dict) -> dict:
        return self._require(self._v6, "v6").explain_emergence(emergence)

    def explain_governor_decision(self, decision: dict) -> dict:
        return self._require(self._v6, "v6").explain_governor_decision(decision)

    def explain_regulation(self, regulation: dict) -> dict:
        return self._require(self._v6, "v6").explain_regulation(regulation)

    def explain_collaboration(self, collab: dict) -> dict:
        return self._require(self._v6, "v6").explain_collaboration(collab)

    def explain_full_v16(self, session: dict) -> dict:
        return self._require(self._v6, "v6").explain_full_v16(session)

    # ------------------------------------------------------------------
    # API agrégée (cumul des sous-moteurs)
    # ------------------------------------------------------------------
    def get_explanations(self, limit: int = 20) -> list[dict]:
        out: list[dict] = []
        for eng, label in (
            (self._v6, "v6"), (self._v5, "v5"),
            (self._v4, "v4"), (self._v3, "v3"), (self._v2, "v2"),
        ):
            if eng is None:
                continue
            try:
                if hasattr(eng, "get_explanations"):
                    items = eng.get_explanations(limit)
                elif hasattr(eng, "get_explanation_log"):
                    items = eng.get_explanation_log(limit)
                else:
                    continue
                for it in items:
                    if isinstance(it, dict):
                        it.setdefault("_source", label)
                        out.append(it)
            except Exception as exc:  # noqa: BLE001
                logger.warning("get_explanations(%s) failed: %s", label, exc)
        return out[:limit]

    # alias rétrocompat v2/v3
    def get_explanation_log(self, limit: int = 50) -> list[dict]:
        return self.get_explanations(limit)

    def get_stats(self) -> dict:
        stats: dict[str, Any] = {}
        for label, eng in (
            ("v2", self._v2), ("v3", self._v3), ("v4", self._v4),
            ("v5", self._v5), ("v6", self._v6),
        ):
            if eng is None:
                continue
            try:
                stats[label] = eng.get_stats()
            except Exception as exc:  # noqa: BLE001
                stats[label] = {"error": str(exc)}
        return {"backends": stats, "active_count": len(stats)}

    def health_check(self) -> dict:
        report: dict[str, Any] = {}
        for label, eng in (
            ("v4", self._v4), ("v5", self._v5), ("v6", self._v6),
        ):
            if eng is None or not hasattr(eng, "health_check"):
                continue
            try:
                report[label] = eng.health_check()
            except Exception as exc:  # noqa: BLE001
                report[label] = {"healthy": False, "error": str(exc)}
        report["facade"] = {"healthy": True, "backends": list(report.keys())}
        return report

    def restart(self) -> None:
        for label, eng in (
            ("v4", self._v4), ("v5", self._v5), ("v6", self._v6),
        ):
            if eng is None or not hasattr(eng, "restart"):
                continue
            try:
                eng.restart()
            except Exception as exc:  # noqa: BLE001
                logger.warning("restart(%s) failed: %s", label, exc)
