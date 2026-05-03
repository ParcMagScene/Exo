# Index des modules EXO

> Auto-généré par `auto_maintain.py` — 2026-04-12

## Modules Python

| Module | Dossier | Fichiers | Point d'entrée |
|--------|---------|----------|----------------|
| context | `python/context` | 2 | `` |
| domotique | `python/domotique` | 12 | `python/domotique/homegraph_server.py` |
| executor | `python/executor` | 2 | `python/executor/task_executor_server.py` |
| knowledge | `python/knowledge` | 2 | `python/knowledge/knowledge_server.py` |
| memory | `python/memory` | 9 | `python/memory/memory_server.py` |
| network | `python/network` | 10 | `` |
| news | `python/news` | 2 | `python/news/news_server.py` |
| nlu | `python/nlu` | 2 | `python/nlu/nlu_server.py` |
| orchestrator | `python/orchestrator` | 149 | `python/orchestrator/exo_server.py` |
| planner | `python/planner` | 2 | `python/planner/task_planner_server.py` |
| shared | `python/shared` | 12 | `` |
| stt | `python/stt` | 4 | `python/stt/stt_server.py` |
| test | `python/test` | 1 | `` |
| tools | `python/tools` | 5 | `python/tools/tools_server.py` |
| tts | `python/tts` | 3 | `python/tts/tts_server.py` |
| vad | `python/vad` | 2 | `python/vad/vad_server.py` |
| verifier | `python/verifier` | 2 | `python/verifier/task_verifier_server.py` |
| wakeword | `python/wakeword` | 2 | `python/wakeword/wakeword_server.py` |
| websearch | `python/websearch` | 2 | `python/websearch/websearch_server.py` |

## Classes C++

| Classe | Header | Module |
|--------|--------|--------|
| `AudioDeviceManager` | `app/audio/AudioDeviceManager.h` | audio |
| `AudioInput` | `app/audio/AudioInput.h` | audio |
| `AudioInputQt` | `app/audio/AudioInputQt.h` | audio |
| `AudioInputRtAudio` | `app/audio/AudioInputRtAudio.h` | audio |
| `TTSBackend` | `app/audio/TTSBackend.h` | audio |
| `TTSBackendQt` | `app/audio/TTSBackendQt.h` | audio |
| `name` | `app/audio/TTSBackendXTTS.h` | audio |
| `TTSBackendXTTS` | `app/audio/TTSBackendXTTS.h` | audio |
| `TTSEqualizer` | `app/audio/TTSManager.h` | audio |
| `TTSCompressor` | `app/audio/TTSManager.h` | audio |
| `TTSNormalizer` | `app/audio/TTSManager.h` | audio |
| `TTSFade` | `app/audio/TTSManager.h` | audio |
| `TTSDSPProcessor` | `app/audio/TTSManager.h` | audio |
| `PCMRingBuffer` | `app/audio/TTSManager.h` | audio |
| `TTSWorker` | `app/audio/TTSManager.h` | audio |
| `TTSManager` | `app/audio/TTSManager.h` | audio |
| `CircularAudioBuffer` | `app/audio/VoicePipeline.h` | audio |
| `AudioPreprocessor` | `app/audio/VoicePipeline.h` | audio |
| `VADEngine` | `app/audio/VoicePipeline.h` | audio |
| `StreamingSTT` | `app/audio/VoicePipeline.h` | audio |
| `PipelineState` | `app/audio/VoicePipeline.h` | audio |
| `VoicePipeline` | `app/audio/VoicePipeline.h` | audio |
| `AssistantManager` | `app/core/AssistantManager.h` | core |
| `ConfigManager` | `app/core/ConfigManager.h` | core |
| `ContextCache` | `app/core/ContextCache.h` | core |
| `ErrorManager` | `app/core/ErrorManager.h` | core |
| `HealthCheck` | `app/core/HealthCheck.h` | core |
| `LatencyMetrics` | `app/core/LatencyMetrics.h` | core |
| `LogManager` | `app/core/LogManager.h` | core |
| `MetricsManager` | `app/core/MetricsManager.h` | core |
| `PipelineModule` | `app/core/PipelineEvent.h` | core |
| `ModuleState` | `app/core/PipelineEvent.h` | core |
| `PipelineEventBus` | `app/core/PipelineEvent.h` | core |
| `AnomalyType` | `app/core/PipelineTracer.h` | core |
| `PipelineTracer` | `app/core/PipelineTracer.h` | core |
| `EventType` | `app/core/PipelineTypes.h` | core |
| `SafeBootManager` | `app/core/SafeBootManager.h` | core |
| `SecurityManager` | `app/core/SecurityManager.h` | core |
| `ServiceManager` | `app/core/ServiceManager.h` | core |
| `ServiceRegistry` | `app/core/ServiceRegistry.h` | core |
| `ServiceState` | `app/core/ServiceState.h` | core |
| `ReadinessPhase` | `app/core/ServiceState.h` | core |
| `ServiceSupervisor` | `app/core/ServiceSupervisor.h` | core |
| `TraceManager` | `app/core/TraceManager.h` | core |
| `WebSocketClient` | `app/core/WebSocketClient.h` | core |
| `FloorPlanController` | `app/floorplan/FloorPlanController.h` | floorplan |
| `ItemType` | `app/floorplan/FloorPlanEnums.h` | floorplan |
| `stored` | `app/floorplan/FloorPlanItem.h` | floorplan |
| `FloorPlanItem` | `app/floorplan/FloorPlanItem.h` | floorplan |
| `FloorPlanModel` | `app/floorplan/FloorPlanModel.h` | floorplan |
| `FloorPlanSerializer` | `app/floorplan/FloorPlanSerializer.h` | floorplan |
| `AIMemoryManager` | `app/llm/AIMemoryManager.h` | llm |
| `ClaudeAPI` | `app/llm/ClaudeAPI.h` | llm |
| `SafeBootAutoRepair` | `app/safeboot/SafeBootAutoRepair.h` | safeboot |
| `SafeBootController` | `app/safeboot/SafeBootController.h` | safeboot |
| `ServiceCriticality` | `app/safeboot/SafeBootEnums.h` | safeboot |
| `ServiceStatus` | `app/safeboot/SafeBootEnums.h` | safeboot |
| `SimulationController` | `app/simulation/SimulationController.h` | simulation |
| `SimulationEngine` | `app/simulation/SimulationEngine.h` | simulation |
| `SimulationEntity` | `app/simulation/SimulationEntity.h` | simulation |
| `ScenarioType` | `app/simulation/SimulationEnums.h` | simulation |
| `EntityType` | `app/simulation/SimulationEnums.h` | simulation |
| `PropagationType` | `app/simulation/SimulationEnums.h` | simulation |
| `EntityState` | `app/simulation/SimulationEnums.h` | simulation |
| `SimState` | `app/simulation/SimulationEnums.h` | simulation |
| `Severity` | `app/simulation/SimulationEnums.h` | simulation |
| `CausalNodeType` | `app/simulation/SimulationEnums.h` | simulation |
| `SimulationPropagation` | `app/simulation/SimulationPropagation.h` | simulation |
| `SimulationResult` | `app/simulation/SimulationResult.h` | simulation |
| `SimulationScenario` | `app/simulation/SimulationScenario.h` | simulation |
| `SpatialCognitiveEngine` | `app/spatialcognition/SpatialCognitiveEngine.h` | spatialcognition |
| `SpatialContext` | `app/spatialcognition/SpatialContext.h` | spatialcognition |
| `SpatialRelation` | `app/spatialcognition/SpatialEnums.h` | spatialcognition |
| `KnowledgeNodeType` | `app/spatialcognition/SpatialEnums.h` | spatialcognition |
| `InferenceType` | `app/spatialcognition/SpatialEnums.h` | spatialcognition |
| `CognitiveSeverity` | `app/spatialcognition/SpatialEnums.h` | spatialcognition |
| `GoalType` | `app/spatialcognition/SpatialEnums.h` | spatialcognition |
| `ActionType` | `app/spatialcognition/SpatialEnums.h` | spatialcognition |
| `CognitivePhase` | `app/spatialcognition/SpatialEnums.h` | spatialcognition |
| `SupervisorDecision` | `app/spatialcognition/SpatialEnums.h` | spatialcognition |
| `SpatialKnowledgeGraph` | `app/spatialcognition/SpatialKnowledgeGraph.h` | spatialcognition |
| `SpatialMemory` | `app/spatialcognition/SpatialMemory.h` | spatialcognition |
| `SpatialPlanner` | `app/spatialcognition/SpatialPlanner.h` | spatialcognition |
| `SpatialReasoner` | `app/spatialcognition/SpatialReasoner.h` | spatialcognition |
| `SpatialSupervisor` | `app/spatialcognition/SpatialSupervisor.h` | spatialcognition |
| `DomoticAnomalyDetector` | `app/spatialsecurity/DomoticAnomalyDetector.h` | spatialsecurity |
| `ElectricalRiskDetector` | `app/spatialsecurity/ElectricalRiskDetector.h` | spatialsecurity |
| `FireDetector` | `app/spatialsecurity/FireDetector.h` | spatialsecurity |
| `IntrusionDetector` | `app/spatialsecurity/IntrusionDetector.h` | spatialsecurity |
| `NetworkRiskDetector` | `app/spatialsecurity/NetworkRiskDetector.h` | spatialsecurity |
| `SpatialSecurityContext` | `app/spatialsecurity/SpatialSecurityContext.h` | spatialsecurity |
| `SpatialSecurityEngine` | `app/spatialsecurity/SpatialSecurityEngine.h` | spatialsecurity |
| `RiskType` | `app/spatialsecurity/SpatialSecurityEnums.h` | spatialsecurity |
| `SecuritySeverity` | `app/spatialsecurity/SpatialSecurityEnums.h` | spatialsecurity |
| `SecurityPhase` | `app/spatialsecurity/SpatialSecurityEnums.h` | spatialsecurity |
| `DetectorType` | `app/spatialsecurity/SpatialSecurityEnums.h` | spatialsecurity |
| `SecurityActionType` | `app/spatialsecurity/SpatialSecurityEnums.h` | spatialsecurity |
| `SubsystemStatus` | `app/spatialsecurity/SpatialSecurityEnums.h` | spatialsecurity |
| `SpatialSecurityMemory` | `app/spatialsecurity/SpatialSecurityMemory.h` | spatialsecurity |
| `TestController` | `app/test/TestController.h` | test |
| `WeatherManager` | `app/utils/WeatherManager.h` | utils |
| `CameraStreamManager` | `app/vision/CameraStreamManager.h` | vision |
| `CameraVisionEngine` | `app/vision/CameraVisionEngine.h` | vision |
| `VisionContext` | `app/vision/VisionContext.h` | vision |
| `VisionDetections` | `app/vision/VisionDetections.h` | vision |
| `DetectionType` | `app/vision/VisionEnums.h` | vision |
| `VisionPhase` | `app/vision/VisionEnums.h` | vision |
| `CameraState` | `app/vision/VisionEnums.h` | vision |
| `VisionModel` | `app/vision/VisionEnums.h` | vision |
| `Posture` | `app/vision/VisionEnums.h` | vision |
| `Behavior` | `app/vision/VisionEnums.h` | vision |
| `VisionSeverity` | `app/vision/VisionEnums.h` | vision |
| `VisionEventRouter` | `app/vision/VisionEventRouter.h` | vision |
| `VisionMemory` | `app/vision/VisionMemory.h` | vision |
| `VisionModelRunner` | `app/vision/VisionModelRunner.h` | vision |
