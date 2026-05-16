# NOTE : Depuis la migration 2026-05, tous les chemins EXO sont sous D:/EXO/<nom>/ (voir docs/index.md).
# Graphe de dépendances C++

> Auto-généré par `auto_maintain.py` — 2026-04-12

## Matrice d'inclusion

```
  AudioDeviceManager.cpp -> AudioDeviceManager.h
  AudioInputQt.cpp -> AudioInputQt.h
  AudioInputQt.h -> AudioInput.h
  AudioInputRtAudio.cpp -> AudioInputRtAudio.h
  AudioInputRtAudio.h -> AudioInput.h
  TTSBackendQt.cpp -> TTSBackendQt.h
  TTSBackendQt.cpp -> TTSManager.h
  TTSBackendQt.h -> TTSBackend.h
  TTSBackendXTTS.cpp -> TTSBackendXTTS.h
  TTSBackendXTTS.cpp -> TTSManager.h
  TTSBackendXTTS.h -> TTSBackend.h
  TTSManager.cpp -> TTSManager.h
  TTSManager.cpp -> TTSBackend.h
  TTSManager.cpp -> TTSBackendQt.h
  TTSManager.cpp -> TTSBackendXTTS.h
  TTSManager.cpp -> LogManager.h
  TTSManager.cpp -> PipelineEvent.h
  TTSManager.cpp -> LatencyMetrics.h
  VoicePipeline.cpp -> VoicePipeline.h
  VoicePipeline.cpp -> LogManager.h
  VoicePipeline.cpp -> LatencyMetrics.h
  VoicePipeline.h -> AudioInput.h
  VoicePipeline.h -> AudioInputQt.h
  VoicePipeline.h -> AudioInputRtAudio.h
  VoicePipeline.h -> AudioDeviceManager.h
  VoicePipeline.h -> TTSManager.h
  VoicePipeline.h -> WebSocketClient.h
  VoicePipeline.h -> PipelineEvent.h
  AssistantManager.cpp -> AssistantManager.h
  AssistantManager.cpp -> AIMemoryManager.h
  AssistantManager.cpp -> ConfigManager.h
  AssistantManager.cpp -> LogManager.h
  AssistantManager.cpp -> HealthCheck.h
  AssistantManager.cpp -> ClaudeAPI.h
  AssistantManager.cpp -> VoicePipeline.h
  AssistantManager.cpp -> AudioDeviceManager.h
  AssistantManager.cpp -> WeatherManager.h
  AssistantManager.cpp -> PipelineEvent.h
  AssistantManager.cpp -> PipelineTracer.h
  AssistantManager.cpp -> ContextCache.h
  AssistantManager.cpp -> LatencyMetrics.h
  AssistantManager.cpp -> SafeBootController.h
  AssistantManager.h -> ConfigManager.h
  AssistantManager.h -> HealthCheck.h
  ConfigManager.cpp -> ConfigManager.h
  ConfigManager.cpp -> LogManager.h
  ContextCache.cpp -> ContextCache.h
  ContextCache.cpp -> LogManager.h
  ErrorManager.cpp -> ErrorManager.h
  HealthCheck.cpp -> HealthCheck.h
  HealthCheck.cpp -> ConfigManager.h
  HealthCheck.h -> WebSocketClient.h
  LatencyMetrics.cpp -> LatencyMetrics.h
  LatencyMetrics.cpp -> LogManager.h
  LogManager.cpp -> LogManager.h
  MetricsManager.cpp -> MetricsManager.h
  MetricsManager.h -> LatencyMetrics.h
  PipelineEvent.cpp -> PipelineEvent.h
  PipelineEvent.cpp -> LogManager.h
  PipelineEvent.h -> PipelineTypes.h
  PipelineTracer.cpp -> PipelineTracer.h
  PipelineTracer.cpp -> LogManager.h
  PipelineTracer.h -> PipelineEvent.h
  SafeBootManager.cpp -> SafeBootManager.h
  SafeBootManager.cpp -> LogManager.h
  SafeBootManager.h -> ServiceRegistry.h
  SecurityManager.cpp -> SecurityManager.h
  ServiceManager.cpp -> ServiceManager.h
  ServiceManager.h -> WebSocketClient.h
  ServiceRegistry.cpp -> ServiceRegistry.h
  ServiceRegistry.cpp -> LogManager.h
  ServiceRegistry.h -> ServiceState.h
  ServiceRegistry.h -> ServiceDescriptor.h
  ServiceSupervisor.cpp -> ServiceSupervisor.h
  ServiceSupervisor.cpp -> LogManager.h
  ServiceSupervisor.h -> ServiceRegistry.h
  ServiceSupervisor.h -> ServiceDescriptor.h
  ServiceSupervisor.h -> WebSocketClient.h
  TraceManager.cpp -> TraceManager.h
  TraceManager.h -> PipelineTracer.h
  WebSocketClient.cpp -> WebSocketClient.h
  WebSocketClient.cpp -> LogManager.h
  FloorPlanController.cpp -> FloorPlanController.h
  FloorPlanController.h -> FloorPlanModel.h
  FloorPlanItem.cpp -> FloorPlanItem.h
  FloorPlanItem.h -> FloorPlanEnums.h
  FloorPlanModel.cpp -> FloorPlanModel.h
  FloorPlanModel.h -> FloorPlanItem.h
  FloorPlanModel.h -> FloorPlanSerializer.h
  FloorPlanSerializer.cpp -> FloorPlanSerializer.h
  FloorPlanSerializer.h -> FloorPlanItem.h
  AIMemoryManager.cpp -> AIMemoryManager.h
  AIMemoryManager.cpp -> LogManager.h
  AIMemoryManager.h -> WebSocketClient.h
  ClaudeAPI.cpp -> ClaudeAPI.h
  ClaudeAPI.cpp -> LogManager.h
  ClaudeAPI.cpp -> PipelineEvent.h
  ClaudeAPI.cpp -> LatencyMetrics.h
  main.cpp -> AssistantManager.h
  main.cpp -> LogManager.h
  main.cpp -> ServiceSupervisor.h
  main.cpp -> SafeBootController.h
  main.cpp -> SafeBootAutoRepair.h
  main.cpp -> TestController.h
  SafeBootAutoRepair.cpp -> SafeBootAutoRepair.h
  SafeBootAutoRepair.cpp -> ServiceRegistry.h
  SafeBootAutoRepair.cpp -> LogManager.h
  SafeBootAutoRepair.cpp -> SafeBootController.h
  SafeBootController.cpp -> SafeBootController.h
  SafeBootController.cpp -> SafeBootAutoRepair.h
  SafeBootController.cpp -> ServiceRegistry.h
  SafeBootController.cpp -> LogManager.h
  SafeBootController.h -> SafeBootEnums.h
  SafeBootController.h -> SafeBootState.h
  SafeBootController.h -> SafeBootTimeline.h
  SafeBootState.h -> SafeBootEnums.h
  SimulationController.cpp -> SimulationController.h
  SimulationController.h -> SimulationEngine.h
  SimulationController.h -> SimulationEnums.h
  SimulationEngine.cpp -> SimulationEngine.h
  SimulationEngine.cpp -> FloorPlanModel.h
  SimulationEngine.h -> SimulationEnums.h
  SimulationEngine.h -> SimulationScenario.h
  SimulationEngine.h -> SimulationEntity.h
  SimulationEngine.h -> SimulationPropagation.h
  SimulationEngine.h -> SimulationResult.h
  SimulationEntity.cpp -> SimulationEntity.h
  SimulationEntity.h -> SimulationEnums.h
  SimulationPropagation.cpp -> SimulationPropagation.h
  SimulationPropagation.h -> SimulationEnums.h
  SimulationPropagation.h -> SimulationEntity.h
  SimulationResult.cpp -> SimulationResult.h
  SimulationResult.h -> SimulationEnums.h
  SimulationResult.h -> SimulationEntity.h
  SimulationScenario.cpp -> SimulationScenario.h
  SimulationScenario.h -> SimulationEnums.h
  SimulationScenario.h -> SimulationEntity.h
  SpatialCognitiveEngine.cpp -> SpatialCognitiveEngine.h
  SpatialCognitiveEngine.cpp -> FloorPlanModel.h
  SpatialCognitiveEngine.h -> SpatialEnums.h
  SpatialCognitiveEngine.h -> SpatialKnowledgeGraph.h
  SpatialCognitiveEngine.h -> SpatialContext.h
  SpatialCognitiveEngine.h -> SpatialMemory.h
  SpatialCognitiveEngine.h -> SpatialReasoner.h
  SpatialCognitiveEngine.h -> SpatialPlanner.h
  SpatialCognitiveEngine.h -> SpatialSupervisor.h
  SpatialContext.cpp -> SpatialContext.h
  SpatialContext.h -> SpatialEnums.h
  SpatialKnowledgeGraph.cpp -> SpatialKnowledgeGraph.h
  SpatialKnowledgeGraph.cpp -> FloorPlanModel.h
  SpatialKnowledgeGraph.h -> SpatialEnums.h
  SpatialMemory.cpp -> SpatialMemory.h
  SpatialMemory.h -> SpatialEnums.h
  SpatialMemory.h -> SpatialContext.h
  SpatialPlanner.cpp -> SpatialPlanner.h
  SpatialPlanner.h -> SpatialEnums.h
  SpatialPlanner.h -> SpatialReasoner.h
  SpatialReasoner.cpp -> SpatialReasoner.h
  SpatialReasoner.h -> SpatialEnums.h
  SpatialReasoner.h -> SpatialKnowledgeGraph.h
  SpatialReasoner.h -> SpatialContext.h
  SpatialSupervisor.cpp -> SpatialSupervisor.h
  SpatialSupervisor.h -> SpatialEnums.h
  SpatialSupervisor.h -> SpatialPlanner.h
  SpatialSupervisor.h -> SpatialContext.h
  SpatialSupervisor.h -> SpatialMemory.h
  DomoticAnomalyDetector.cpp -> DomoticAnomalyDetector.h
  DomoticAnomalyDetector.h -> SpatialSecurityEnums.h
  DomoticAnomalyDetector.h -> IntrusionDetector.h
  ElectricalRiskDetector.cpp -> ElectricalRiskDetector.h
  ElectricalRiskDetector.h -> SpatialSecurityEnums.h
  ElectricalRiskDetector.h -> IntrusionDetector.h
  FireDetector.cpp -> FireDetector.h
  FireDetector.h -> SpatialSecurityEnums.h
  FireDetector.h -> IntrusionDetector.h
  IntrusionDetector.cpp -> IntrusionDetector.h
  IntrusionDetector.h -> SpatialSecurityEnums.h
  IntrusionDetector.h -> SpatialSecurityContext.h
  NetworkRiskDetector.cpp -> NetworkRiskDetector.h
  NetworkRiskDetector.h -> SpatialSecurityEnums.h
  NetworkRiskDetector.h -> IntrusionDetector.h
  SpatialSecurityContext.cpp -> SpatialSecurityContext.h
  SpatialSecurityContext.h -> SpatialSecurityEnums.h
  SpatialSecurityEngine.cpp -> SpatialSecurityEngine.h
  SpatialSecurityEngine.h -> SpatialSecurityEnums.h
  SpatialSecurityEngine.h -> SpatialSecurityContext.h
  SpatialSecurityEngine.h -> SpatialSecurityMemory.h
  SpatialSecurityEngine.h -> IntrusionDetector.h
  SpatialSecurityEngine.h -> FireDetector.h
  SpatialSecurityEngine.h -> ElectricalRiskDetector.h
  SpatialSecurityEngine.h -> NetworkRiskDetector.h
  SpatialSecurityEngine.h -> DomoticAnomalyDetector.h
  SpatialSecurityMemory.cpp -> SpatialSecurityMemory.h
  SpatialSecurityMemory.h -> SpatialSecurityEnums.h
  TestController.cpp -> TestController.h
  TestController.cpp -> ConfigManager.h
  TestController.h -> WebSocketClient.h
  WeatherManager.cpp -> WeatherManager.h
  CameraStreamManager.cpp -> CameraStreamManager.h
  CameraStreamManager.h -> VisionEnums.h
  CameraVisionEngine.cpp -> CameraVisionEngine.h
  CameraVisionEngine.h -> VisionEnums.h
  CameraVisionEngine.h -> VisionDetections.h
  CameraVisionEngine.h -> CameraStreamManager.h
  CameraVisionEngine.h -> VisionModelRunner.h
  CameraVisionEngine.h -> VisionContext.h
  CameraVisionEngine.h -> VisionMemory.h
  CameraVisionEngine.h -> VisionEventRouter.h
  VisionContext.cpp -> VisionContext.h
  VisionContext.h -> VisionEnums.h
  VisionContext.h -> VisionDetections.h
  VisionDetections.cpp -> VisionDetections.h
  VisionDetections.h -> VisionEnums.h
  VisionEventRouter.cpp -> VisionEventRouter.h
  VisionEventRouter.h -> VisionEnums.h
  VisionEventRouter.h -> VisionDetections.h
  VisionMemory.cpp -> VisionMemory.h
  VisionMemory.h -> VisionEnums.h
  VisionMemory.h -> VisionDetections.h
  VisionModelRunner.cpp -> VisionModelRunner.h
  VisionModelRunner.h -> VisionEnums.h
  VisionModelRunner.h -> VisionDetections.h
```

## Fichiers par module

### audio/

- `app/audio/AudioDeviceManager.cpp` (1 include(s))
- `app/audio/AudioDeviceManager.h` (0 include(s))
- `app/audio/AudioInput.h` (0 include(s))
- `app/audio/AudioInputQt.cpp` (1 include(s))
- `app/audio/AudioInputQt.h` (1 include(s))
- `app/audio/AudioInputRtAudio.cpp` (1 include(s))
- `app/audio/AudioInputRtAudio.h` (1 include(s))
- `app/audio/TTSBackend.h` (0 include(s))
- `app/audio/TTSBackendQt.cpp` (2 include(s))
- `app/audio/TTSBackendQt.h` (1 include(s))
- `app/audio/TTSBackendXTTS.cpp` (2 include(s))
- `app/audio/TTSBackendXTTS.h` (1 include(s))
- `app/audio/TTSManager.cpp` (7 include(s))
- `app/audio/TTSManager.h` (0 include(s))
- `app/audio/VoicePipeline.cpp` (3 include(s))
- `app/audio/VoicePipeline.h` (7 include(s))

### core/

- `app/core/AssistantManager.cpp` (14 include(s))
- `app/core/AssistantManager.h` (2 include(s))
- `app/core/ConfigManager.cpp` (2 include(s))
- `app/core/ConfigManager.h` (0 include(s))
- `app/core/ContextCache.cpp` (2 include(s))
- `app/core/ContextCache.h` (0 include(s))
- `app/core/ErrorManager.cpp` (1 include(s))
- `app/core/ErrorManager.h` (0 include(s))
- `app/core/HealthCheck.cpp` (2 include(s))
- `app/core/HealthCheck.h` (1 include(s))
- `app/core/LatencyMetrics.cpp` (2 include(s))
- `app/core/LatencyMetrics.h` (0 include(s))
- `app/core/LogManager.cpp` (1 include(s))
- `app/core/LogManager.h` (0 include(s))
- `app/core/MetricsManager.cpp` (1 include(s))
- `app/core/MetricsManager.h` (1 include(s))
- `app/core/PipelineEvent.cpp` (2 include(s))
- `app/core/PipelineEvent.h` (1 include(s))
- `app/core/PipelineTracer.cpp` (2 include(s))
- `app/core/PipelineTracer.h` (1 include(s))
- `app/core/PipelineTypes.h` (0 include(s))
- `app/core/SafeBootManager.cpp` (2 include(s))
- `app/core/SafeBootManager.h` (1 include(s))
- `app/core/SecurityManager.cpp` (1 include(s))
- `app/core/SecurityManager.h` (0 include(s))
- `app/core/ServiceDescriptor.h` (0 include(s))
- `app/core/ServiceManager.cpp` (1 include(s))
- `app/core/ServiceManager.h` (1 include(s))
- `app/core/ServiceRegistry.cpp` (2 include(s))
- `app/core/ServiceRegistry.h` (2 include(s))
- `app/core/ServiceState.h` (0 include(s))
- `app/core/ServiceSupervisor.cpp` (2 include(s))
- `app/core/ServiceSupervisor.h` (3 include(s))
- `app/core/TraceManager.cpp` (1 include(s))
- `app/core/TraceManager.h` (1 include(s))
- `app/core/WebSocketClient.cpp` (2 include(s))
- `app/core/WebSocketClient.h` (0 include(s))

### floorplan/

- `app/floorplan/FloorPlanController.cpp` (1 include(s))
- `app/floorplan/FloorPlanController.h` (1 include(s))
- `app/floorplan/FloorPlanEnums.h` (0 include(s))
- `app/floorplan/FloorPlanItem.cpp` (1 include(s))
- `app/floorplan/FloorPlanItem.h` (1 include(s))
- `app/floorplan/FloorPlanModel.cpp` (1 include(s))
- `app/floorplan/FloorPlanModel.h` (2 include(s))
- `app/floorplan/FloorPlanSerializer.cpp` (1 include(s))
- `app/floorplan/FloorPlanSerializer.h` (1 include(s))

### llm/

- `app/llm/AIMemoryManager.cpp` (2 include(s))
- `app/llm/AIMemoryManager.h` (1 include(s))
- `app/llm/ClaudeAPI.cpp` (4 include(s))
- `app/llm/ClaudeAPI.h` (0 include(s))

### root/

- `app/main.cpp` (6 include(s))

### safeboot/

- `app/safeboot/SafeBootAutoRepair.cpp` (4 include(s))
- `app/safeboot/SafeBootAutoRepair.h` (0 include(s))
- `app/safeboot/SafeBootController.cpp` (4 include(s))
- `app/safeboot/SafeBootController.h` (3 include(s))
- `app/safeboot/SafeBootEnums.h` (0 include(s))
- `app/safeboot/SafeBootState.h` (1 include(s))
- `app/safeboot/SafeBootTimeline.h` (0 include(s))

### simulation/

- `app/simulation/SimulationController.cpp` (1 include(s))
- `app/simulation/SimulationController.h` (2 include(s))
- `app/simulation/SimulationEngine.cpp` (2 include(s))
- `app/simulation/SimulationEngine.h` (5 include(s))
- `app/simulation/SimulationEntity.cpp` (1 include(s))
- `app/simulation/SimulationEntity.h` (1 include(s))
- `app/simulation/SimulationEnums.h` (0 include(s))
- `app/simulation/SimulationPropagation.cpp` (1 include(s))
- `app/simulation/SimulationPropagation.h` (2 include(s))
- `app/simulation/SimulationResult.cpp` (1 include(s))
- `app/simulation/SimulationResult.h` (2 include(s))
- `app/simulation/SimulationScenario.cpp` (1 include(s))
- `app/simulation/SimulationScenario.h` (2 include(s))

### spatialcognition/

- `app/spatialcognition/SpatialCognitiveEngine.cpp` (2 include(s))
- `app/spatialcognition/SpatialCognitiveEngine.h` (7 include(s))
- `app/spatialcognition/SpatialContext.cpp` (1 include(s))
- `app/spatialcognition/SpatialContext.h` (1 include(s))
- `app/spatialcognition/SpatialEnums.h` (0 include(s))
- `app/spatialcognition/SpatialKnowledgeGraph.cpp` (2 include(s))
- `app/spatialcognition/SpatialKnowledgeGraph.h` (1 include(s))
- `app/spatialcognition/SpatialMemory.cpp` (1 include(s))
- `app/spatialcognition/SpatialMemory.h` (2 include(s))
- `app/spatialcognition/SpatialPlanner.cpp` (1 include(s))
- `app/spatialcognition/SpatialPlanner.h` (2 include(s))
- `app/spatialcognition/SpatialReasoner.cpp` (1 include(s))
- `app/spatialcognition/SpatialReasoner.h` (3 include(s))
- `app/spatialcognition/SpatialSupervisor.cpp` (1 include(s))
- `app/spatialcognition/SpatialSupervisor.h` (4 include(s))

### spatialsecurity/

- `app/spatialsecurity/DomoticAnomalyDetector.cpp` (1 include(s))
- `app/spatialsecurity/DomoticAnomalyDetector.h` (2 include(s))
- `app/spatialsecurity/ElectricalRiskDetector.cpp` (1 include(s))
- `app/spatialsecurity/ElectricalRiskDetector.h` (2 include(s))
- `app/spatialsecurity/FireDetector.cpp` (1 include(s))
- `app/spatialsecurity/FireDetector.h` (2 include(s))
- `app/spatialsecurity/IntrusionDetector.cpp` (1 include(s))
- `app/spatialsecurity/IntrusionDetector.h` (2 include(s))
- `app/spatialsecurity/NetworkRiskDetector.cpp` (1 include(s))
- `app/spatialsecurity/NetworkRiskDetector.h` (2 include(s))
- `app/spatialsecurity/SpatialSecurityContext.cpp` (1 include(s))
- `app/spatialsecurity/SpatialSecurityContext.h` (1 include(s))
- `app/spatialsecurity/SpatialSecurityEngine.cpp` (1 include(s))
- `app/spatialsecurity/SpatialSecurityEngine.h` (8 include(s))
- `app/spatialsecurity/SpatialSecurityEnums.h` (0 include(s))
- `app/spatialsecurity/SpatialSecurityMemory.cpp` (1 include(s))
- `app/spatialsecurity/SpatialSecurityMemory.h` (1 include(s))

### test/

- `app/test/TestController.cpp` (2 include(s))
- `app/test/TestController.h` (1 include(s))

### utils/

- `app/utils/WeatherManager.cpp` (1 include(s))
- `app/utils/WeatherManager.h` (0 include(s))

### vision/

- `app/vision/CameraStreamManager.cpp` (1 include(s))
- `app/vision/CameraStreamManager.h` (1 include(s))
- `app/vision/CameraVisionEngine.cpp` (1 include(s))
- `app/vision/CameraVisionEngine.h` (7 include(s))
- `app/vision/VisionContext.cpp` (1 include(s))
- `app/vision/VisionContext.h` (2 include(s))
- `app/vision/VisionDetections.cpp` (1 include(s))
- `app/vision/VisionDetections.h` (1 include(s))
- `app/vision/VisionEnums.h` (0 include(s))
- `app/vision/VisionEventRouter.cpp` (1 include(s))
- `app/vision/VisionEventRouter.h` (2 include(s))
- `app/vision/VisionMemory.cpp` (1 include(s))
- `app/vision/VisionMemory.h` (2 include(s))
- `app/vision/VisionModelRunner.cpp` (1 include(s))
- `app/vision/VisionModelRunner.h` (2 include(s))
