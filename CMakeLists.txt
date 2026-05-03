# Version simplifiée pour compilation initiale
cmake_minimum_required(VERSION 3.21)

project(RaspberryAssistant VERSION 30.0.0 LANGUAGES CXX)

# ── Options ──
option(ENABLE_RTAUDIO "Enable RtAudio backend (WASAPI on Windows)" ON)
option(ENABLE_XTTS    "Enable legacy XTTS v2 TTS backend"          ON)
option(BUILD_TESTS    "Build unit tests (Qt Test + CTest)"         ON)

# Configuration C++
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Configuration Qt
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 6.5 REQUIRED COMPONENTS 
    Core 
    Quick 
    QuickControls2
    Widgets
    Network
    Multimedia
    MultimediaWidgets
    TextToSpeech
    WebSockets
    Sql
)

# Sources principales — architecture modulaire app/
set(SOURCES
    app/main.cpp
    app/core/AssistantManager.cpp
    app/core/AssistantComponentFactory.cpp
    app/core/AssistantConnectionBinder.cpp
    app/core/AssistantQmlExposer.cpp
    app/core/AssistantPromptBuilder.cpp
    app/core/AssistantToolDispatcher.cpp
    app/core/AssistantFastPathEngine.cpp
    app/core/AssistantSafeBootFacade.cpp
    app/core/ConfigManager.cpp
    app/core/LogManager.cpp
    app/core/PipelineEvent.cpp
    app/core/PipelineTracer.cpp
    app/core/ContextCache.cpp
    app/core/LatencyMetrics.cpp
    app/core/MetricsManager.cpp
    app/core/TraceManager.cpp
    app/core/ErrorManager.cpp
    app/core/SecurityManager.cpp
    app/core/WebSocketClient.cpp
    app/core/HealthCheck.cpp
    app/core/ServiceManager.cpp
    app/core/ServiceSupervisor.cpp
    app/core/ServiceRegistry.cpp
    app/safeboot/SafeBootController.cpp
    app/safeboot/SafeBootAutoRepair.cpp
    app/audio/VoicePipeline.cpp
    app/audio/TTSManager.cpp
    app/audio/TTSBackendQt.cpp
    $<$<BOOL:${ENABLE_XTTS}>:app/audio/TTSBackendXTTS.cpp>
    app/audio/AudioInputQt.cpp
    app/audio/AudioDeviceManager.cpp
    app/llm/ClaudeAPI.cpp
    app/llm/AIMemoryManager.cpp
    app/utils/WeatherManager.cpp
    app/floorplan/FloorPlanItem.cpp
    app/floorplan/FloorPlanSerializer.cpp
    app/floorplan/FloorPlanModel.cpp
    app/floorplan/FloorPlanController.cpp
    app/simulation/SimulationEntity.cpp
    app/simulation/SimulationScenario.cpp
    app/simulation/SimulationPropagation.cpp
    app/simulation/SimulationResult.cpp
    app/simulation/SimulationEngine.cpp
    app/simulation/SimulationController.cpp
    app/spatialcognition/SpatialKnowledgeGraph.cpp
    app/spatialcognition/SpatialContext.cpp
    app/spatialcognition/SpatialMemory.cpp
    app/spatialcognition/SpatialReasoner.cpp
    app/spatialcognition/SpatialPlanner.cpp
    app/spatialcognition/SpatialSupervisor.cpp
    app/spatialcognition/SpatialCognitiveEngine.cpp
    app/spatialsecurity/SpatialSecurityContext.cpp
    app/spatialsecurity/SpatialSecurityMemory.cpp
    app/spatialsecurity/IntrusionDetector.cpp
    app/spatialsecurity/FireDetector.cpp
    app/spatialsecurity/ElectricalRiskDetector.cpp
    app/spatialsecurity/NetworkRiskDetector.cpp
    app/spatialsecurity/DomoticAnomalyDetector.cpp
    app/spatialsecurity/SpatialSecurityEngine.cpp
    app/vision/VisionDetections.cpp
    app/vision/CameraStreamManager.cpp
    app/vision/VisionModelRunner.cpp
    app/vision/VisionContext.cpp
    app/vision/VisionMemory.cpp
    app/vision/VisionEventRouter.cpp
    app/vision/CameraVisionEngine.cpp
    app/test/TestController.cpp
)

set(HEADERS
    app/core/AssistantManager.h
    app/core/AssistantComponentFactory.h
    app/core/AssistantConnectionBinder.h
    app/core/AssistantQmlExposer.h
    app/core/AssistantPromptBuilder.h
    app/core/AssistantToolDispatcher.h
    app/core/AssistantFastPathEngine.h
    app/core/AssistantSafeBootFacade.h
    app/core/ConfigManager.h
    app/core/LogManager.h
    app/core/PipelineEvent.h
    app/core/PipelineTypes.h
    app/core/PipelineTracer.h
    app/core/ContextCache.h
    app/core/LatencyMetrics.h
    app/core/MetricsManager.h
    app/core/TraceManager.h
    app/core/ErrorManager.h
    app/core/SecurityManager.h
    app/core/WebSocketClient.h
    app/core/HealthCheck.h
    app/core/ServiceManager.h
    app/core/ServiceSupervisor.h
    app/safeboot/SafeBootEnums.h
    app/safeboot/SafeBootState.h
    app/safeboot/SafeBootTimeline.h
    app/safeboot/SafeBootController.h
    app/safeboot/SafeBootAutoRepair.h
    app/core/ServiceState.h
    app/core/ServiceDescriptor.h
    app/core/ServiceRegistry.h
    app/audio/VoicePipeline.h
    app/audio/TTSManager.h
    app/audio/TTSBackend.h
    app/audio/TTSBackendQt.h
    $<$<BOOL:${ENABLE_XTTS}>:app/audio/TTSBackendXTTS.h>
    app/audio/AudioInput.h
    app/audio/AudioInputQt.h
    app/audio/AudioDeviceManager.h
    app/llm/ClaudeAPI.h
    app/llm/AIMemoryManager.h
    app/utils/WeatherManager.h
    app/floorplan/FloorPlanEnums.h
    app/floorplan/FloorPlanItem.h
    app/floorplan/FloorPlanSerializer.h
    app/floorplan/FloorPlanModel.h
    app/floorplan/FloorPlanController.h
    app/simulation/SimulationEnums.h
    app/simulation/SimulationEntity.h
    app/simulation/SimulationScenario.h
    app/simulation/SimulationPropagation.h
    app/simulation/SimulationResult.h
    app/simulation/SimulationEngine.h
    app/simulation/SimulationController.h
    app/spatialcognition/SpatialEnums.h
    app/spatialcognition/SpatialKnowledgeGraph.h
    app/spatialcognition/SpatialContext.h
    app/spatialcognition/SpatialMemory.h
    app/spatialcognition/SpatialReasoner.h
    app/spatialcognition/SpatialPlanner.h
    app/spatialcognition/SpatialSupervisor.h
    app/spatialcognition/SpatialCognitiveEngine.h
    app/spatialsecurity/SpatialSecurityEnums.h
    app/spatialsecurity/SpatialSecurityContext.h
    app/spatialsecurity/SpatialSecurityMemory.h
    app/spatialsecurity/IntrusionDetector.h
    app/spatialsecurity/FireDetector.h
    app/spatialsecurity/ElectricalRiskDetector.h
    app/spatialsecurity/NetworkRiskDetector.h
    app/spatialsecurity/DomoticAnomalyDetector.h
    app/spatialsecurity/SpatialSecurityEngine.h
    app/vision/VisionEnums.h
    app/vision/VisionDetections.h
    app/vision/CameraStreamManager.h
    app/vision/VisionModelRunner.h
    app/vision/VisionContext.h
    app/vision/VisionMemory.h
    app/vision/VisionEventRouter.h
    app/vision/CameraVisionEngine.h
    app/test/TestController.h
)

# ── RtAudio (optional) ──
if(ENABLE_RTAUDIO)
    # Build RtAudio as static lib with WASAPI only
    set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
    set(RTAUDIO_BUILD_PYTHON OFF CACHE BOOL "" FORCE)
    add_subdirectory(rtaudio EXCLUDE_FROM_ALL)

    list(APPEND SOURCES app/audio/AudioInputRtAudio.cpp)
    list(APPEND HEADERS app/audio/AudioInputRtAudio.h)
endif()

# Exécutable GUI (pas de console Windows)
qt_add_executable(RaspberryAssistant ${SOURCES} ${HEADERS})
set_target_properties(RaspberryAssistant PROPERTIES
    WIN32_EXECUTABLE TRUE
)

# Qt QML policies
qt_policy(SET QTP0001 NEW)
qt_policy(SET QTP0004 OLD)

# Theme singleton property
set_source_files_properties(qml/theme/Theme.qml PROPERTIES QT_QML_SINGLETON_TYPE TRUE)
set_source_files_properties(qml/navigation/MenuStructure.qml PROPERTIES QT_QML_SINGLETON_TYPE TRUE)

# Module QML
qt_add_qml_module(RaspberryAssistant
    URI RaspberryAssistant
    VERSION 4.0
    QML_FILES
        qml/MainWindow.qml
        # ── Pages ──
        qml/pages/HomePage.qml
        qml/pages/SettingsPage.qml
        qml/pages/PipelinePage.qml
        qml/pages/HistoryPage.qml
        qml/pages/FloorPlanPage.qml
        qml/pages/MaisonPage.qml
        qml/pages/ReseauPage.qml
        # ── Pages Expert (Refonte UI v2.0) ──
        qml/pages/ObservabilityPage.qml
        qml/pages/PipelinePageExpert.qml
        qml/pages/VisionPageExpert.qml
        qml/pages/SimulationPageExpert.qml
        qml/pages/SpatialCognitionPageExpert.qml
        qml/pages/SecurityPageExpert.qml
        qml/pages/DevelopmentPageExpert.qml
        # ── Panels ──
        qml/panels/Sidebar.qml
        qml/panels/BottomBar.qml
        qml/panels/HeaderBar.qml
        qml/panels/SafeBootPanel.qml
        # ── Theme ──
        qml/theme/Theme.qml
        # ── Components ──
        qml/components/ExoButton.qml
        qml/components/ExoPanelHeader.qml
        qml/components/ExoProgressBar.qml
        qml/components/ExoPipelineStatus.qml
        qml/components/ExoStatusIndicator.qml
        qml/components/ExoMicrophoneLevel.qml
        qml/components/ExoVisualizer.qml
        qml/components/ExoTranscriptView.qml
        qml/components/ExoResponseView.qml
        qml/components/ExoOrbVisualizer.qml
        qml/components/ExoSplashScreen.qml
        qml/components/AudioWaveformView.qml
        qml/components/FloorPlanTools.qml
        qml/components/FloorPlanProperties.qml
        qml/components/FurniturePalette.qml
        qml/components/CognitiveTimeline.qml
        qml/components/EngineHeatmap.qml
        qml/components/ExoContextPanel.qml
        qml/components/ExoPlanProgress.qml
        qml/components/GovernancePanel.qml
        qml/components/MemoryInspector.qml
        qml/components/ModeSwitch.qml
        qml/components/ObservabilityDashboard.qml
        qml/components/PipelineView.qml
        qml/components/VoicePipelineView.qml
        # ── Core singletons ──
        qml/core/UIState.qml
        # ── Navigation ──
        qml/navigation/MenuStructure.qml
    RESOURCES
        qml/theme/qmldir
        qml/components/qmldir
        qml/pages/qmldir
        qml/panels/qmldir
        qml/core/qmldir
        qml/navigation/qmldir
        qml/icons/chat.svg
        qml/icons/debug.svg
        qml/icons/history.svg
        qml/icons/logs.svg
        qml/icons/pipeline.svg
        qml/icons/send.svg
        qml/icons/settings.svg
        qml/icons/maison.svg
        qml/icons/reseau.svg
        qml/icons/cognition.svg
        qml/icons/securite.svg
        qml/icons/simulation.svg
        qml/icons/heatmap.svg
        # ── App Icon (unifié v30.3) ──
        assets/icons/app/exo.svg
        assets/icons/app/exo.png
)

# ── Icône Windows (.ico → .rc) ──
if(WIN32)
    set(EXO_RC_FILE "${CMAKE_CURRENT_BINARY_DIR}/exo.rc")
    file(WRITE ${EXO_RC_FILE} "IDI_ICON1 ICON \"${CMAKE_CURRENT_SOURCE_DIR}/assets/icons/app/exo.ico\"\n")
    target_sources(RaspberryAssistant PRIVATE ${EXO_RC_FILE})
endif()

# Chemins d'inclusion — app/ comme racine + sous-dossiers
target_include_directories(RaspberryAssistant PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}/app
    ${CMAKE_CURRENT_SOURCE_DIR}/app/core
    ${CMAKE_CURRENT_SOURCE_DIR}/app/audio
    ${CMAKE_CURRENT_SOURCE_DIR}/app/llm
    ${CMAKE_CURRENT_SOURCE_DIR}/app/utils
    ${CMAKE_CURRENT_SOURCE_DIR}/app/floorplan
    ${CMAKE_CURRENT_SOURCE_DIR}/app/simulation
    ${CMAKE_CURRENT_SOURCE_DIR}/app/spatialcognition
    ${CMAKE_CURRENT_SOURCE_DIR}/app/safeboot
    ${CMAKE_CURRENT_SOURCE_DIR}/app/spatialsecurity
    ${CMAKE_CURRENT_SOURCE_DIR}/app/vision
    ${CMAKE_CURRENT_SOURCE_DIR}/app/test
)

# ── RtAudio include + compile definition ──
if(ENABLE_RTAUDIO)
    target_include_directories(RaspberryAssistant PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/rtaudio
    )
    target_compile_definitions(RaspberryAssistant PRIVATE ENABLE_RTAUDIO)
endif()

# ── XTTS legacy backend ──
if(ENABLE_XTTS)
    target_compile_definitions(RaspberryAssistant PRIVATE ENABLE_XTTS)
endif()

# Liaison des bibliothèques (syntaxe PRIVATE pour éviter les conflits)
target_link_libraries(RaspberryAssistant PRIVATE
    Qt6::Core
    Qt6::Quick  
    Qt6::QuickControls2
    Qt6::Widgets
    Qt6::Network
    Qt6::Multimedia
    Qt6::MultimediaWidgets
    Qt6::TextToSpeech
    Qt6::WebSockets
    Qt6::Sql
)

if(ENABLE_RTAUDIO)
    target_link_libraries(RaspberryAssistant PRIVATE rtaudio)
endif()

# ── Warnings stricts ──
if(MSVC)
    # /W4 strict + disable C4702 (unreachable code in Qt system headers)
    target_compile_options(RaspberryAssistant PRIVATE /W4 /permissive- /wd4702)
else()
    target_compile_options(RaspberryAssistant PRIVATE -Wall -Wextra -Wpedantic)
endif()

# Copier les fichiers de configuration vers le répertoire de build
add_custom_target(${PROJECT_NAME}_copy_config ALL
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        ${CMAKE_SOURCE_DIR}/config
        $<TARGET_FILE_DIR:RaspberryAssistant>/config
    COMMENT "Copie config/ vers le répertoire de sortie"
)
add_dependencies(RaspberryAssistant ${PROJECT_NAME}_copy_config)

# ── Auto-deploy Qt DLLs (Windows) ──
if(WIN32)
    find_program(WINDEPLOYQT windeployqt6 HINTS "${Qt6_DIR}/../../../bin")
    if(WINDEPLOYQT)
        add_custom_command(TARGET RaspberryAssistant POST_BUILD
            COMMAND "${WINDEPLOYQT}"
                --no-translations
                --qmldir "${CMAKE_SOURCE_DIR}/qml"
                "$<TARGET_FILE:RaspberryAssistant>"
            COMMENT "Running windeployqt..."
        )
    endif()
endif()

# Informations de configuration
message(STATUS "=== Configuration du projet ===")
message(STATUS "Système cible: ${CMAKE_SYSTEM_PROCESSOR}")
message(STATUS "Type de build: ${CMAKE_BUILD_TYPE}")
message(STATUS "Qt version: ${Qt6_VERSION}")
message(STATUS "Tests: ${BUILD_TESTS}")
message(STATUS "==============================")

# ── Tests ──
if(BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests/cpp)
endif()