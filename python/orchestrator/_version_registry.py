"""Lazy-loading registry for EXO cognitive modules v11-v25.

Each version's modules are imported and instantiated on first access,
reducing startup time by deferring heavy imports until actually needed.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger("exo.versions")


# ---------------------------------------------------------------------------
# LazyVersionDict — transparent dict that triggers init on first access
# ---------------------------------------------------------------------------

class LazyVersionDict(dict):
    """Dict proxy that triggers module initialization on first access."""

    def __init__(self, name: str, factory: Callable[..., dict],
                 *args: Any, **kwargs: Any):
        super().__init__()
        self._name = name
        self._factory = factory
        self._args = args
        self._kwargs = kwargs
        self._loaded = False

    def _ensure(self) -> None:
        if not self._loaded:
            self._loaded = True
            result = self._factory(*self._args, **self._kwargs)
            super().update(result)
            logger.info("Lazy-loaded %s (%d modules)", self._name, len(result))

    def get(self, key: str, default: Any = None) -> Any:
        self._ensure()
        return super().get(key, default)

    def items(self):
        self._ensure()
        return super().items()

    def values(self):
        self._ensure()
        return super().values()

    def keys(self):
        self._ensure()
        return super().keys()

    def __getitem__(self, key: str) -> Any:
        self._ensure()
        return super().__getitem__(key)

    def __contains__(self, key: object) -> bool:
        self._ensure()
        return super().__contains__(key)

    def __len__(self) -> int:
        self._ensure()
        return super().__len__()

    def __bool__(self) -> bool:
        return True  # Always truthy so `if self._v11:` checks pass

    def __iter__(self):
        self._ensure()
        return super().__iter__()


# ---------------------------------------------------------------------------
# Factory functions — one per version
# ---------------------------------------------------------------------------

def _init_v11(agent_mgr: Any) -> dict:
    from meta_memory import MetaMemory
    from auto_governance import AutoGovernance
    from learning_engine import LearningEngine
    from feedback_engine import FeedbackEngine
    from self_diagnosis_engine import SelfDiagnosisEngine
    from optimization_engine import OptimizationEngine
    from auto_tuning_engine import AutoTuningEngine
    from meta_planner import MetaPlanner
    from meta_supervisor import MetaSupervisor
    from auto_explanation import AutoExplanation

    meta_memory = MetaMemory()
    governance = AutoGovernance(meta_memory)
    learning = LearningEngine(meta_memory, governance)
    feedback = FeedbackEngine(learning)

    task_memory = getattr(agent_mgr, "_task_memory", None)
    task_optimizer = getattr(agent_mgr, "_task_optimizer", None)

    diagnosis = SelfDiagnosisEngine(meta_memory, task_memory, task_optimizer)
    optimization = OptimizationEngine(meta_memory, diagnosis)
    tuning = AutoTuningEngine(meta_memory, governance)
    planner = MetaPlanner(meta_memory, task_optimizer)
    supervisor = MetaSupervisor(meta_memory, learning, governance)
    explanation = AutoExplanation(meta_memory)

    return {
        "meta_memory": meta_memory,
        "governance": governance,
        "learning": learning,
        "feedback": feedback,
        "diagnosis": diagnosis,
        "optimization": optimization,
        "tuning": tuning,
        "planner": planner,
        "supervisor": supervisor,
        "explanation": explanation,
    }


def _init_v12(v11: dict) -> dict:
    from self_reflection_engine import SelfReflectionEngine
    from meta_reasoning_engine import MetaReasoningEngine
    from meta_planner_v2 import MetaPlannerV2
    from meta_verifier import MetaVerifier
    from self_consistency_engine import SelfConsistencyEngine
    from meta_supervisor_v2 import MetaSupervisorV2
    from explainability_engine_v2 import ExplainabilityEngineV2

    meta_memory = v11["meta_memory"]
    governance = v11["governance"]

    reflection = SelfReflectionEngine(meta_memory, governance)
    meta_reasoning = MetaReasoningEngine(meta_memory, governance)
    planner_v2 = MetaPlannerV2(meta_memory, v11["planner"], reflection)
    verifier = MetaVerifier(meta_memory, governance)
    consistency = SelfConsistencyEngine(meta_memory, verifier, governance)
    supervisor_v2 = MetaSupervisorV2(
        meta_memory, v11["supervisor"], reflection, meta_reasoning, governance)
    explainability_v2 = ExplainabilityEngineV2(meta_memory, v11["explanation"])

    return {
        "reflection": reflection,
        "reasoning": meta_reasoning,
        "planner_v2": planner_v2,
        "verifier": verifier,
        "consistency": consistency,
        "supervisor_v2": supervisor_v2,
        "explainability_v2": explainability_v2,
    }


def _init_v13(v11: dict, v12: dict) -> dict:
    from self_simulation_engine import SelfSimulationEngine
    from prediction_engine import PredictionEngine
    from future_planner import FuturePlanner
    from multi_scenario_engine import MultiScenarioEngine
    from temporal_coherence_engine import TemporalCoherenceEngine
    from anticipation_engine import AnticipationEngine
    from explainability_engine_v3 import ExplainabilityEngineV3
    from meta_supervisor_v3 import MetaSupervisorV3

    meta_memory = v11["meta_memory"]
    governance = v11["governance"]

    simulation_eng = SelfSimulationEngine(meta_memory, governance)
    prediction_eng = PredictionEngine(meta_memory, governance)
    future_planner = FuturePlanner(meta_memory, governance)
    multi_scenario = MultiScenarioEngine(meta_memory, simulation_eng, governance)
    temporal_coherence = TemporalCoherenceEngine(meta_memory, future_planner)
    anticipation = AnticipationEngine(meta_memory, prediction_eng, governance)
    explainability_v3 = ExplainabilityEngineV3(
        meta_memory, v12["explainability_v2"])
    supervisor_v3 = MetaSupervisorV3(
        meta_memory, v12["supervisor_v2"], simulation_eng, governance)

    return {
        "simulation": simulation_eng,
        "prediction": prediction_eng,
        "future_planner": future_planner,
        "multi_scenario": multi_scenario,
        "temporal": temporal_coherence,
        "anticipation": anticipation,
        "explainability_v3": explainability_v3,
        "supervisor_v3": supervisor_v3,
    }


def _init_v14(v11: dict, v13: dict) -> dict:
    from agent_messaging_bus import AgentMessagingBus
    from agent_registry import AgentRegistry
    from specialized_agents import create_default_agents
    from conflict_resolver import ConflictResolver
    from cognitive_orchestrator import CognitiveOrchestrator
    from distributed_consistency_engine import DistributedConsistencyEngine
    from meta_supervisor_v4 import MetaSupervisorV4
    from explainability_engine_v4 import ExplainabilityEngineV4

    meta_memory = v11["meta_memory"]
    governance = v11["governance"]

    msg_bus = AgentMessagingBus(meta_memory)
    registry = AgentRegistry(msg_bus)
    agents = create_default_agents(msg_bus, meta_memory)
    for a in agents:
        registry.register_agent(a)
    conflict_res = ConflictResolver(meta_memory, governance)
    cog_orchestrator = CognitiveOrchestrator(
        registry, msg_bus, conflict_res, meta_memory, governance)
    consistency_eng = DistributedConsistencyEngine(
        registry, msg_bus, conflict_res, meta_memory)
    supervisor_v4 = MetaSupervisorV4(
        meta_memory, registry, msg_bus, consistency_eng,
        v13["supervisor_v3"], governance)
    explainability_v4 = ExplainabilityEngineV4(
        meta_memory, registry, v13["explainability_v3"])

    return {
        "messaging_bus": msg_bus,
        "registry": registry,
        "conflict_resolver": conflict_res,
        "orchestrator": cog_orchestrator,
        "consistency": consistency_eng,
        "supervisor_v4": supervisor_v4,
        "explainability_v4": explainability_v4,
    }


def _init_v15(v11: dict, agent_mgr: Any) -> dict:
    from expert_system_engine import ExpertSystemEngine
    from knowledge_graph import KnowledgeGraph
    from inference_engine import InferenceEngine
    from cognitive_agent_core import CognitiveAgentCore
    from meta_cognition_engine import MetaCognitionEngine
    from prospective_engine import ProspectiveEngine
    from distributed_cognition_layer import DistributedCognitionLayer
    from global_supervisor_v5 import GlobalSupervisorV5
    from explainability_engine_v5 import ExplainabilityEngineV5

    meta_memory = v11["meta_memory"]
    governance = v11["governance"]

    expert_system = ExpertSystemEngine(meta_memory, governance)
    knowledge_graph = KnowledgeGraph(meta_memory)
    inference_eng = InferenceEngine(knowledge_graph, expert_system, meta_memory)
    cognitive_agent = CognitiveAgentCore(meta_memory, governance, inference_eng)
    meta_cognition = MetaCognitionEngine(meta_memory, governance)
    prospective = ProspectiveEngine(meta_memory, inference_eng)
    distrib_cognition = DistributedCognitionLayer(
        meta_memory, governance, agent_mgr)
    supervisor_v5 = GlobalSupervisorV5(
        meta_memory, governance, meta_cognition, distrib_cognition)
    explainability_v5 = ExplainabilityEngineV5(
        meta_memory, knowledge_graph, inference_eng)

    return {
        "expert_system": expert_system,
        "knowledge_graph": knowledge_graph,
        "inference": inference_eng,
        "cognitive_agent": cognitive_agent,
        "meta_cognition": meta_cognition,
        "prospective": prospective,
        "distributed": distrib_cognition,
        "supervisor_v5": supervisor_v5,
        "explainability_v5": explainability_v5,
    }


def _init_v16(v11: dict, v14: dict, v15: dict) -> dict:
    from cognitive_audit_log import CognitiveAuditLog
    from initiative_protocol import InitiativeProtocol
    from cognitive_governor import CognitiveGovernor
    from autonomous_agent_layer import AutonomousAgentLayer
    from emergent_collaboration_bus import EmergentCollaborationBus
    from emergent_reasoning_engine import EmergentReasoningEngine
    from self_regulation_engine import SelfRegulationEngine
    from explainability_engine_v6 import ExplainabilityEngineV6

    meta_memory = v11["meta_memory"]
    governance = v11["governance"]

    cognitive_audit = CognitiveAuditLog(meta_memory)
    initiative_proto = InitiativeProtocol(cognitive_audit, governance)
    cog_governor = CognitiveGovernor(
        initiative_proto, cognitive_audit, governance, meta_memory)
    autonomous_layer = AutonomousAgentLayer(
        cog_governor, initiative_proto, cognitive_audit, meta_memory)
    collab_bus = EmergentCollaborationBus(
        cognitive_audit, v14["messaging_bus"], meta_memory)
    emergent_reasoning = EmergentReasoningEngine(
        collab_bus, cog_governor, cognitive_audit, meta_memory,
        v15["knowledge_graph"], v15["inference"])
    self_regulation = SelfRegulationEngine(
        cog_governor, cognitive_audit, initiative_proto, meta_memory)
    explainability_v6 = ExplainabilityEngineV6(
        meta_memory, v15["explainability_v5"], cognitive_audit)

    return {
        "audit_log": cognitive_audit,
        "initiative_protocol": initiative_proto,
        "governor": cog_governor,
        "autonomous_layer": autonomous_layer,
        "collaboration_bus": collab_bus,
        "emergent_reasoning": emergent_reasoning,
        "self_regulation": self_regulation,
        "explainability_v6": explainability_v6,
    }


def _init_v17(v11: dict, v15: dict, v16: dict) -> dict:
    from reasoning_bridge import ReasoningBridge
    from hybrid_inference_engine import HybridInferenceEngine
    from knowledge_grounded_llm import KnowledgeGroundedLLM
    from neurosymbolic_coherence_engine import NeuroSymbolicCoherenceEngine
    from symbolic_validator import SymbolicValidator
    from semantic_extractor import SemanticExtractor
    from knowledge_augmentor import KnowledgeAugmentor
    from neurosymbolic_explainability_engine import NeuroSymbolicExplainabilityEngine

    meta_memory = v11["meta_memory"]
    governance = v11["governance"]
    knowledge_graph = v15["knowledge_graph"]
    inference_eng = v15["inference"]

    reasoning_bridge = ReasoningBridge(
        knowledge_graph=knowledge_graph, inference_engine=inference_eng,
        meta_memory=meta_memory, governance=governance)
    hybrid_inference = HybridInferenceEngine(
        reasoning_bridge=reasoning_bridge, knowledge_graph=knowledge_graph,
        inference_engine=inference_eng, meta_memory=meta_memory,
        governance=governance)
    knowledge_grounded_llm = KnowledgeGroundedLLM(
        knowledge_graph=knowledge_graph, inference_engine=inference_eng,
        reasoning_bridge=reasoning_bridge, meta_memory=meta_memory,
        governance=governance)
    neurosymbolic_coherence = NeuroSymbolicCoherenceEngine(
        reasoning_bridge=reasoning_bridge, knowledge_graph=knowledge_graph,
        hybrid_inference=hybrid_inference, meta_memory=meta_memory,
        governance=governance)
    symbolic_validator = SymbolicValidator(
        knowledge_graph=knowledge_graph, inference_engine=inference_eng,
        reasoning_bridge=reasoning_bridge, governance=governance,
        meta_memory=meta_memory)
    semantic_extractor = SemanticExtractor(
        knowledge_graph=knowledge_graph, reasoning_bridge=reasoning_bridge,
        meta_memory=meta_memory)
    knowledge_augmentor = KnowledgeAugmentor(
        knowledge_graph=knowledge_graph, semantic_extractor=semantic_extractor,
        reasoning_bridge=reasoning_bridge, governance=governance,
        meta_memory=meta_memory)
    neurosymbolic_explainability = NeuroSymbolicExplainabilityEngine(
        meta_memory=meta_memory, explainability_v6=v16["explainability_v6"],
        reasoning_bridge=reasoning_bridge, hybrid_inference=hybrid_inference,
        symbolic_validator=symbolic_validator,
        coherence_engine=neurosymbolic_coherence)

    return {
        "reasoning_bridge": reasoning_bridge,
        "hybrid_inference": hybrid_inference,
        "knowledge_grounded_llm": knowledge_grounded_llm,
        "coherence_engine": neurosymbolic_coherence,
        "symbolic_validator": symbolic_validator,
        "semantic_extractor": semantic_extractor,
        "knowledge_augmentor": knowledge_augmentor,
        "neurosymbolic_explainability": neurosymbolic_explainability,
    }


def _init_v18(v11: dict, v14: dict) -> dict:
    from macro_agent_layer import MacroAgentLayer
    from micro_agent_layer import MicroAgentLayer
    from cognitive_layer_stack import CognitiveLayerStack
    from vertical_reasoning_flow import VerticalReasoningFlow
    from hierarchical_supervisor import HierarchicalSupervisor
    from priority_engine import PriorityEngine
    from layered_consistency_engine import LayeredConsistencyEngine
    from layered_explainability_engine import LayeredExplainabilityEngine

    meta_memory = v11["meta_memory"]
    governance = v11["governance"]

    macro_layer = MacroAgentLayer(
        meta_memory=meta_memory, governance=governance,
        registry=v14["registry"])
    micro_layer = MicroAgentLayer(
        meta_memory=meta_memory, governance=governance)
    layer_stack = CognitiveLayerStack(
        macro_layer=macro_layer, micro_layer=micro_layer,
        governance=governance, meta_memory=meta_memory)
    vertical_flow = VerticalReasoningFlow(
        layer_stack=layer_stack, governance=governance,
        meta_memory=meta_memory)
    hierarchical_supervisor = HierarchicalSupervisor(
        layer_stack=layer_stack, macro_layer=macro_layer,
        micro_layer=micro_layer, governance=governance,
        meta_memory=meta_memory)
    priority_engine = PriorityEngine(
        layer_stack=layer_stack, macro_layer=macro_layer,
        micro_layer=micro_layer, governance=governance)
    layered_consistency = LayeredConsistencyEngine(
        layer_stack=layer_stack, macro_layer=macro_layer,
        micro_layer=micro_layer, supervisor=hierarchical_supervisor,
        governance=governance)
    layered_explainability = LayeredExplainabilityEngine(
        layer_stack=layer_stack, macro_layer=macro_layer,
        micro_layer=micro_layer, vertical_flow=vertical_flow,
        supervisor=hierarchical_supervisor, governance=governance)

    return {
        "macro_layer": macro_layer,
        "micro_layer": micro_layer,
        "layer_stack": layer_stack,
        "vertical_flow": vertical_flow,
        "hierarchical_supervisor": hierarchical_supervisor,
        "priority_engine": priority_engine,
        "layered_consistency": layered_consistency,
        "layered_explainability": layered_explainability,
    }


def _init_v19(v11: dict, v15: dict, v18: dict) -> dict:
    from meta_optimizer import MetaOptimizer
    from adaptive_heuristics_engine import AdaptiveHeuristicsEngine
    from cognitive_pipeline_optimizer import CognitivePipelineOptimizer
    from cognitive_load_reducer import CognitiveLoadReducer
    from multi_objective_optimizer import MultiObjectiveOptimizer
    from cognitive_profiling_engine import CognitiveProfilingEngine
    from plan_optimizer import PlanOptimizer
    from simulation_optimizer import SimulationOptimizer
    from inference_optimizer import InferenceOptimizer
    from optimization_explainability_engine import OptimizationExplainabilityEngine

    meta_memory = v11["meta_memory"]
    governance = v11["governance"]
    layer_stack = v18["layer_stack"]
    macro_layer = v18["macro_layer"]
    micro_layer = v18["micro_layer"]
    priority_engine = v18["priority_engine"]

    meta_optimizer = MetaOptimizer(
        layer_stack=layer_stack, macro_layer=macro_layer,
        micro_layer=micro_layer, priority_engine=priority_engine,
        governance=governance, meta_memory=meta_memory)
    adaptive_heuristics = AdaptiveHeuristicsEngine(
        meta_optimizer=meta_optimizer, priority_engine=priority_engine,
        governance=governance)
    pipeline_optimizer = CognitivePipelineOptimizer(
        layer_stack=layer_stack, meta_optimizer=meta_optimizer,
        governance=governance)
    load_reducer = CognitiveLoadReducer(
        layer_stack=layer_stack, macro_layer=macro_layer,
        micro_layer=micro_layer, pipeline_optimizer=pipeline_optimizer,
        governance=governance)
    multi_objective = MultiObjectiveOptimizer(
        meta_optimizer=meta_optimizer, heuristics=adaptive_heuristics,
        governance=governance)
    profiling = CognitiveProfilingEngine(
        layer_stack=layer_stack, macro_layer=macro_layer,
        micro_layer=micro_layer, meta_optimizer=meta_optimizer)
    plan_opt = PlanOptimizer(
        meta_optimizer=meta_optimizer, pipeline_optimizer=pipeline_optimizer,
        governance=governance)
    sim_opt = SimulationOptimizer(
        meta_optimizer=meta_optimizer, profiling=profiling,
        governance=governance)
    inf_opt = InferenceOptimizer(
        inference_eng=v15["inference"], knowledge_graph=v15["knowledge_graph"],
        meta_optimizer=meta_optimizer, governance=governance)
    opt_explain = OptimizationExplainabilityEngine(
        meta_optimizer=meta_optimizer, multi_objective=multi_objective,
        profiling=profiling, governance=governance)

    return {
        "meta_optimizer": meta_optimizer,
        "adaptive_heuristics": adaptive_heuristics,
        "pipeline_optimizer": pipeline_optimizer,
        "load_reducer": load_reducer,
        "multi_objective": multi_objective,
        "profiling": profiling,
        "plan_optimizer": plan_opt,
        "simulation_optimizer": sim_opt,
        "inference_optimizer": inf_opt,
        "optimization_explainability": opt_explain,
    }


def _init_v20(v11: dict, v14: dict) -> dict:
    from modular_cognitive_unit import ModularCognitiveUnit
    from plug_and_play_agent_system import PlugAndPlayAgentSystem
    from distributed_orchestrator import DistributedOrchestrator
    from scalable_cognitive_fabric import ScalableCognitiveFabric
    from cognitive_partitioning_engine import CognitivePartitioningEngine
    from module_compatibility_checker import ModuleCompatibilityChecker
    from module_lifecycle_manager import ModuleLifecycleManager
    from hot_swap_engine import HotSwapEngine
    from modular_explainability_engine import ModularExplainabilityEngine

    governance = v11["governance"]
    meta_memory = v11["meta_memory"]

    mcu = ModularCognitiveUnit(
        governance=governance, meta_memory=meta_memory)
    plug_and_play = PlugAndPlayAgentSystem(
        governance=governance, agent_registry=v14["registry"])
    dist_orchestrator = DistributedOrchestrator(
        governance=governance, mcu=mcu)
    scalable_fabric = ScalableCognitiveFabric(
        governance=governance, mcu=mcu)
    cog_partitioning = CognitivePartitioningEngine(
        governance=governance, mcu=mcu, fabric=scalable_fabric)
    mod_compatibility = ModuleCompatibilityChecker(
        governance=governance, mcu=mcu)
    mod_lifecycle = ModuleLifecycleManager(
        governance=governance, mcu=mcu, compatibility_checker=mod_compatibility)
    hot_swap = HotSwapEngine(
        governance=governance, lifecycle=mod_lifecycle,
        compatibility=mod_compatibility)
    mod_explain = ModularExplainabilityEngine(
        governance=governance, mcu=mcu, orchestrator=dist_orchestrator,
        partitioning=cog_partitioning, hot_swap=hot_swap,
        lifecycle=mod_lifecycle)

    return {
        "mcu": mcu,
        "plug_and_play": plug_and_play,
        "distributed_orchestrator": dist_orchestrator,
        "scalable_fabric": scalable_fabric,
        "partitioning": cog_partitioning,
        "lifecycle": mod_lifecycle,
        "hot_swap": hot_swap,
        "compatibility": mod_compatibility,
        "modular_explainability": mod_explain,
    }


def _init_v21(v11: dict, v15: dict) -> dict:
    from advanced_rule_engine import AdvancedRuleEngine
    from causal_graph_engine import CausalGraphEngine
    from deductive_reasoner import DeductiveReasoner
    from inductive_reasoner import InductiveReasoner
    from abductive_reasoner import AbductiveReasoner
    from constraint_solver import ConstraintSolver
    from logical_coherence_engine import LogicalCoherenceEngine
    from knowledge_graph_v2 import KnowledgeGraphV2
    from symbolic_explainability_v2 import SymbolicExplainabilityEngineV2

    governance = v11["governance"]

    rule_engine = AdvancedRuleEngine(governance=governance)
    causal_engine = CausalGraphEngine(governance=governance)
    deductive = DeductiveReasoner(governance=governance)
    inductive = InductiveReasoner(governance=governance)
    abductive = AbductiveReasoner(governance=governance)
    constraint_solver_inst = ConstraintSolver(
        governance=governance, rule_engine=rule_engine)
    coherence = LogicalCoherenceEngine(
        rule_engine=rule_engine, deductive=deductive, governance=governance)
    kg_v2 = KnowledgeGraphV2(
        knowledge_graph=v15["knowledge_graph"],
        causal_engine=causal_engine, governance=governance)
    symbolic_explain_v2 = SymbolicExplainabilityEngineV2(
        deductive=deductive, inductive=inductive, abductive=abductive,
        causal_engine=causal_engine, governance=governance)

    return {
        "rule_engine": rule_engine,
        "causal_engine": causal_engine,
        "deductive": deductive,
        "inductive": inductive,
        "abductive": abductive,
        "constraint_solver": constraint_solver_inst,
        "coherence": coherence,
        "kg_v2": kg_v2,
        "symbolic_explain": symbolic_explain_v2,
    }


def _init_v22(v11: dict, v21: dict) -> dict:
    from strategic_planner import StrategicPlanner
    from htn_plus_engine import HTNPlusEngine
    from multi_objective_planner import MultiObjectivePlanner
    from constraint_aware_planner import ConstraintAwarePlanner
    from scenario_planner import ScenarioPlanner
    from strategic_arbitration_engine import StrategicArbitrationEngine
    from temporal_planning_engine import TemporalPlanningEngine
    from plan_coherence_engine import PlanCoherenceEngine
    from planning_explainability_engine import PlanningExplainabilityEngine

    governance = v11["governance"]

    htn_plus = HTNPlusEngine(governance=governance)
    multi_obj_planner = MultiObjectivePlanner(governance=governance)
    constraint_aware = ConstraintAwarePlanner(
        governance=governance, constraint_solver=v21["constraint_solver"])
    scenario_planner = ScenarioPlanner(governance=governance)
    arbitration = StrategicArbitrationEngine(governance=governance)
    temporal = TemporalPlanningEngine(governance=governance)
    plan_coherence = PlanCoherenceEngine(
        governance=governance, coherence_engine=v21["coherence"])
    planning_explain = PlanningExplainabilityEngine(
        governance=governance, arbitration=arbitration,
        coherence=plan_coherence)
    strategic_planner = StrategicPlanner(
        governance=governance, htn=htn_plus,
        multi_obj=multi_obj_planner,
        constraint_planner=constraint_aware,
        scenario_planner=scenario_planner,
        temporal_planner=temporal,
        arbitration=arbitration)

    return {
        "strategic_planner": strategic_planner,
        "htn_plus": htn_plus,
        "multi_objective": multi_obj_planner,
        "constraint_aware": constraint_aware,
        "scenario_planner": scenario_planner,
        "arbitration": arbitration,
        "temporal": temporal,
        "coherence": plan_coherence,
        "explainability": planning_explain,
    }


def _init_v23(v11: dict) -> dict:
    from simulation_governance_engine import SimulationGovernanceEngine
    from context_simulation_sandbox import ContextSimulationSandbox
    from multi_scenario_simulation_engine import MultiScenarioSimulationEngine
    from predictive_modeling_engine import PredictiveModelingEngine
    from outcome_analysis_engine import OutcomeAnalysisEngine
    from temporal_simulation_engine import TemporalSimulationEngine
    from simulation_coherence_engine import SimulationCoherenceEngine
    from simulation_explainability_engine import SimulationExplainabilityEngine

    sim_governance = SimulationGovernanceEngine(
        governance=v11.get("governance"))
    sim_sandbox = ContextSimulationSandbox(governance=sim_governance)
    multi_scenario = MultiScenarioSimulationEngine(
        governance=sim_governance, sandbox=sim_sandbox)
    predictive = PredictiveModelingEngine(
        governance=sim_governance, sandbox=sim_sandbox)
    outcome_analysis = OutcomeAnalysisEngine(
        governance=sim_governance, sandbox=sim_sandbox)
    temporal_sim = TemporalSimulationEngine(
        governance=sim_governance, sandbox=sim_sandbox)
    sim_coherence = SimulationCoherenceEngine(
        governance=sim_governance, sandbox=sim_sandbox)
    sim_explain = SimulationExplainabilityEngine(
        governance=sim_governance, sandbox=sim_sandbox)

    return {
        "sandbox": sim_sandbox,
        "multi_scenario": multi_scenario,
        "predictive": predictive,
        "outcome_analysis": outcome_analysis,
        "temporal_sim": temporal_sim,
        "coherence": sim_coherence,
        "governance": sim_governance,
        "explainability": sim_explain,
    }


def _init_v24(v11: dict) -> dict:
    from cognitive_telemetry_engine import CognitiveTelemetryEngine
    from structured_tracing_engine import StructuredTracingEngine
    from cognitive_metrics_engine import CognitiveMetricsEngine
    from performance_analysis_engine import PerformanceAnalysisEngine
    from cognitive_anomaly_detector import CognitiveAnomalyDetector
    from observability_aggregator import ObservabilityAggregator
    from observability_dashboard_engine import ObservabilityDashboardEngine
    from observability_explainability_engine import ObservabilityExplainabilityEngine

    governance_v11 = v11.get("governance")

    cog_telemetry = CognitiveTelemetryEngine(governance=governance_v11)
    cog_tracing = StructuredTracingEngine(governance=governance_v11)
    cog_metrics = CognitiveMetricsEngine(governance=governance_v11)
    cog_performance = PerformanceAnalysisEngine(
        governance=governance_v11, telemetry=cog_telemetry, metrics=cog_metrics)
    cog_anomaly = CognitiveAnomalyDetector(
        governance=governance_v11, telemetry=cog_telemetry)
    cog_aggregator = ObservabilityAggregator(
        governance=governance_v11, telemetry=cog_telemetry,
        tracing=cog_tracing, metrics=cog_metrics,
        anomaly=cog_anomaly, performance=cog_performance)
    cog_dashboard = ObservabilityDashboardEngine(
        governance=governance_v11, aggregator=cog_aggregator)
    cog_explainability = ObservabilityExplainabilityEngine(
        governance=governance_v11, metrics=cog_metrics,
        anomaly=cog_anomaly, performance=cog_performance)

    return {
        "telemetry": cog_telemetry,
        "tracing": cog_tracing,
        "metrics": cog_metrics,
        "performance": cog_performance,
        "anomaly": cog_anomaly,
        "aggregator": cog_aggregator,
        "dashboard": cog_dashboard,
        "explainability": cog_explainability,
    }


def _init_v25(v11: dict) -> dict:
    from cognitive_permission_system import CognitivePermissionSystem
    from multi_level_validation_engine import MultiLevelValidationEngine
    from cognitive_audit_engine import CognitiveAuditEngine
    from compliance_engine import ComplianceEngine
    from governance_policy_engine import GovernancePolicyEngine
    from action_control_engine import ActionControlEngine
    from decision_validation_engine import DecisionValidationEngine
    from governance_supervisor import GovernanceSupervisor
    from governance_explainability_engine import GovernanceExplainabilityEngine

    governance_v11 = v11.get("governance")

    gov_permissions = CognitivePermissionSystem(governance=governance_v11)
    gov_validation = MultiLevelValidationEngine(
        governance=governance_v11, permissions=gov_permissions)
    gov_audit = CognitiveAuditEngine(governance=governance_v11)
    gov_policies = GovernancePolicyEngine(governance=governance_v11)
    gov_compliance = ComplianceEngine(
        governance=governance_v11, permissions=gov_permissions,
        policies=gov_policies)
    gov_action_ctrl = ActionControlEngine(
        governance=governance_v11, permissions=gov_permissions,
        validation=gov_validation, compliance=gov_compliance)
    gov_decision_val = DecisionValidationEngine(
        governance=governance_v11, permissions=gov_permissions,
        policies=gov_policies)
    gov_supervisor = GovernanceSupervisor(
        governance=governance_v11, permissions=gov_permissions,
        validation=gov_validation, audit=gov_audit,
        compliance=gov_compliance, policies=gov_policies,
        action_control=gov_action_ctrl,
        decision_validation=gov_decision_val)
    gov_explainability = GovernanceExplainabilityEngine(
        governance=governance_v11, permissions=gov_permissions,
        validation=gov_validation, compliance=gov_compliance,
        action_control=gov_action_ctrl, audit=gov_audit)

    return {
        "permissions": gov_permissions,
        "validation": gov_validation,
        "audit": gov_audit,
        "compliance": gov_compliance,
        "policies": gov_policies,
        "action_control": gov_action_ctrl,
        "decision_validation": gov_decision_val,
        "supervisor": gov_supervisor,
        "explainability": gov_explainability,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_all_versions(agent_mgr: Any) -> dict[str, LazyVersionDict]:
    """Create lazy version dicts for v11-v25.

    No imports or instantiation happen until a version is first accessed.
    """
    v11 = LazyVersionDict("v11", _init_v11, agent_mgr)
    v12 = LazyVersionDict("v12", _init_v12, v11)
    v13 = LazyVersionDict("v13", _init_v13, v11, v12)
    v14 = LazyVersionDict("v14", _init_v14, v11, v13)
    v15 = LazyVersionDict("v15", _init_v15, v11, agent_mgr)
    v16 = LazyVersionDict("v16", _init_v16, v11, v14, v15)
    v17 = LazyVersionDict("v17", _init_v17, v11, v15, v16)
    v18 = LazyVersionDict("v18", _init_v18, v11, v14)
    v19 = LazyVersionDict("v19", _init_v19, v11, v15, v18)
    v20 = LazyVersionDict("v20", _init_v20, v11, v14)
    v21 = LazyVersionDict("v21", _init_v21, v11, v15)
    v22 = LazyVersionDict("v22", _init_v22, v11, v21)
    v23 = LazyVersionDict("v23", _init_v23, v11)
    v24 = LazyVersionDict("v24", _init_v24, v11)
    v25 = LazyVersionDict("v25", _init_v25, v11)

    return {
        "v11": v11, "v12": v12, "v13": v13, "v14": v14, "v15": v15,
        "v16": v16, "v17": v17, "v18": v18, "v19": v19, "v20": v20,
        "v21": v21, "v22": v22, "v23": v23, "v24": v24, "v25": v25,
    }
