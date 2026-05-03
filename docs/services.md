# Services EXO

> Auto-généré par `auto_maintain.py` — 2026-04-12

## Microservices

| Service | Port | Langage | Protocole | Dossier |
|---------|------|---------|-----------|---------|
| exo_server | 8765 | Python | WebSocket | `python/orchestrator` |
| stt_server | 8766 | Python | WebSocket | `python/stt` |
| tts_server | 8767 | Python | WebSocket | `python/tts` |
| vad_server | 8768 | Python | WebSocket | `python/vad` |
| wakeword_server | 8770 | Python | WebSocket | `python/wakeword` |
| memory_server | 8771 | Python | WebSocket | `python/memory` |
| nlu_server | 8772 | Python | WebSocket | `python/nlu` |

## Tests disponibles

### cpp/ (9 fichier(s))

- `tests/cpp/test_audiopreprocessor.cpp`
- `tests/cpp/test_circularaudiobuffer.cpp`
- `tests/cpp/test_configmanager.cpp`
- `tests/cpp/test_healthcheck.cpp`
- `tests/cpp/test_pipelineevent.cpp`
- `tests/cpp/test_pipelinetracer.cpp`
- `tests/cpp/test_safeboot.cpp`
- `tests/cpp/test_simulation.cpp`
- `tests/cpp/test_tts_dsp.cpp`

### integration/ (1 fichier(s))

- `tests/integration/test_pipeline_integration.py`

### performance/ (1 fichier(s))

- `tests/performance/test_performance.py`

### python/ (51 fichier(s))

- `tests/python/test_actions.py`
- `tests/python/test_agent_v10.py`
- `tests/python/test_areas.py`
- `tests/python/test_calendar_service.py`
- `tests/python/test_context_engine.py`
- `tests/python/test_context_engine_v8.py`
- `tests/python/test_devices.py`
- `tests/python/test_domotique.py`
- `tests/python/test_entities.py`
- `tests/python/test_file_service.py`
- `tests/python/test_healthcheck_protocol.py`
- `tests/python/test_home_bridge.py`
- `tests/python/test_knowledge_server.py`
- `tests/python/test_memory_server.py`
- `tests/python/test_memory_v2.py`
- `tests/python/test_memory_v8.py`
- `tests/python/test_news_server.py`
- `tests/python/test_nlu_server.py`
- `tests/python/test_pipeline_v82.py`
- `tests/python/test_stt_server.py`
- `tests/python/test_sync.py`
- `tests/python/test_system_service.py`
- `tests/python/test_task_executor.py`
- `tests/python/test_task_planner.py`
- `tests/python/test_task_planner_v8.py`
- `tests/python/test_task_verifier.py`
- `tests/python/test_tools_server.py`
- `tests/python/test_tts_server.py`
- `tests/python/test_ull.py`
- `tests/python/test_v11_selflearning.py`
- `tests/python/test_v12_metareasoning.py`
- `tests/python/test_v13_prospective.py`
- `tests/python/test_v14_distributed.py`
- `tests/python/test_v15_unified.py`
- `tests/python/test_v16_autonomous.py`
- `tests/python/test_v17_neurosymbolic.py`
- `tests/python/test_v18_hierarchical.py`
- `tests/python/test_v19_optimization.py`
- `tests/python/test_v20_modular.py`
- `tests/python/test_v21_expert_system.py`
- `tests/python/test_v22_strategic_planning.py`
- `tests/python/test_v23_contextual_simulation.py`
- `tests/python/test_v24_cognitive_observability.py`
- `tests/python/test_v25_cognitive_governance.py`
- `tests/python/test_v9_config.py`
- `tests/python/test_v9_integration.py`
- `tests/python/test_v9_observability.py`
- `tests/python/test_v9_resilience.py`
- `tests/python/test_v9_security.py`
- `tests/python/test_vad_server.py`
- `tests/python/test_websearch_server.py`

**Total : 62 fichier(s) de test**
