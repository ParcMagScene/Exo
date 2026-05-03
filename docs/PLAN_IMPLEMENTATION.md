# PLAN D'IMPLÉMENTATION — EXO v30.0

> Dernière mise à jour : 11 avril 2026
> Source de vérité : `PROMPT_MAITRE.md`

---

## État actuel

EXO v30.0 est **opérationnel**. Tous les modules compilent (0 erreur), les 25 services sont configurés, le pipeline vocal fonctionne, 2349 tests passent.

---

## Historique des correctifs (v5.2)

| # | Module | Correction | Fichier |
|---|--------|-----------|---------|
| 1 | ServiceSupervisor | Fix SIGSEGV : `deleteLater()` au lieu de `delete` dans `cleanupProbe()` | `ServiceSupervisor.cpp` |
| 2 | ServiceSupervisor | Ordre shutdown : stop timers AVANT delete client | `ServiceSupervisor.cpp` |
| 3 | ServiceSupervisor | Suppression `close()` avant `open()` sur poll timer | `ServiceSupervisor.cpp` |
| 4 | WebSocketClient | `deleteLater()` dans `destroySocket()` au lieu de `delete` | `WebSocketClient.cpp` |
| 5 | LogManager | Filtre wildcard disconnect warnings | `LogManager.cpp` |
| 6 | TTSManager | Fix volume jump : `kSmooth = 0.7` (était 0.3) | `TTSManager.cpp` |
| 7 | TTSManager | Suppression double appel `setXTTSVoice()` dans `setVoice()` | `TTSManager.cpp` |
| 8 | TTSManager | Log DSP corrigé : `norm -14dBFS` (était -16) | `TTSManager.cpp` |
| 9 | TTSBackendXTTS | `qWarning → qInfo` pour "Connexion Python réinitialisée" | `TTSBackendXTTS.cpp` |
| 10 | TTSBackendXTTS | `qWarning → qInfo` pour backend/URL/voice/language | `TTSBackendXTTS.cpp` |
| 11 | ConfigManager | Géolocalisation désactivée par défaut (IP donne ville ISP) | `ConfigManager.cpp` |
| 12 | ConfigManager | `detectLocation()` ne surcharge plus les villes non-default | `ConfigManager.cpp` |
| 13 | SettingsPage | 10+ contrôles GUI synchronisés (VAD, TTS, audio, etc.) | `SettingsPage.qml` |
| 14 | WeatherManager | Fix localisation FR (réponse API lang=fr) | `WeatherManager.cpp` |
| 15 | AssistantManager | Application pitch/rate/noiseGate/AGC au startup | `AssistantManager.cpp` |

---

## Tâches restantes

### Priorité haute

| # | Tâche | Module | Détail |
|---|-------|--------|--------|
| 1 | Appliquer Noise Reduction live | SettingsPage.qml | Le toggle sauvegarde en config mais n'appelle pas `voiceManager` pour appliquer |

### Priorité moyenne

| # | Tâche | Module | Détail |
|---|-------|--------|--------|
| 2 | Tests E2E pipeline | tests/integration | Tester le cycle complet wake→STT→Claude→TTS |
| 3 | Monitoring VRAM | HealthCheck | Ajouter check VRAM GPU dans le health monitoring |
| 4 | Purge ListModel transcript/logs | QML | Correctifs audit mémoire (voir `docs/audits/AUDIT_GUI_QML_MEMORY_2026-04.md`) |
| 5 | Timers conditionnés à la visibilité | QML | PipelinePage timers tournent même quand invisible |

### Priorité basse

| # | Tâche | Module | Détail |
|---|-------|--------|--------|
| 6 | GUI responsive | QML | Supporter des résolutions autres que 1280×800 |
| 7 | Thème clair | Theme.qml | Ajouter un mode light |
| 8 | i18n | QML/C++ | Internationalisation des textes GUI |

---

## Modules stables (pas de refonte prévue)

| Module | Statut |
|--------|--------|
| VoicePipeline FSM | ✅ Stable |
| PipelineEvent (34 types) | ✅ Stable |
| ClaudeAPI (29 FC tools) | ✅ Stable |
| DSP sortie (5 étages) | ✅ Stable |
| AudioPreprocessor | ✅ Stable |
| ServiceSupervisor | ✅ Stable (post-fix) |
| WebSocketClient | ✅ Stable (post-fix) |
| 25 microservices Python | ✅ Stable |
| FloorPlan (plan d'étage) | ✅ Stable |
| Simulation spatiale (v28) | ✅ Stable |
| Framework cognitif (exo/) | ✅ Stable |

---

## Roadmap

| Objectif | Impact |
|----------|--------|
| Streaming musical | Spotify / Tidal — nouveau FC tool + media player |
| Déploiement Raspberry Pi 5 | Cross-compilation ARM, modèles quantifiés |
| Interface mobile companion | Nouvelle GUI (Flutter ou React Native) |
| Docker | Containerisation des 25 services Python |

---

> Ce plan est mis à jour à chaque itération. Seules les tâches **actives** y figurent.
