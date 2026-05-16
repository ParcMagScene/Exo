# Documentation EXO

Bienvenue dans la documentation officielle du projet EXO (Assistant vocal local Qt 6 + Python + Orpheus + Whisper + Claude Opus 4.7).

> Mise à jour : 2026-05-16 (post-nettoyage Phase 1+2+3).

---

## Démarrage

- Lancement standard (silencieux, recommandé) :
  ```powershell
  powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "D:\EXO\launch_exo_silent.ps1"
  ```
- Stop / restart / status : `. D:\EXO\launch_exo_silent.ps1 ; Stop-EXO | Restart-EXO | Get-EXOStatus`
- Logs : `D:\EXO\logs\<service>.log` + `<service>.err.log` + `launcher.log`

Voir aussi : [README.md](../README.md) (racine), [PROMPT_MAITRE.md](../PROMPT_MAITRE.md), [CHANGELOG.md](../CHANGELOG.md).

---

## Architecture

- [architecture/](architecture/) — Graphes et structure du système
- [architecture/services.md](architecture/services.md) — Inventaire des services (ports, venvs, fichiers)
- [architecture/pipeline.md](architecture/pipeline.md) — FSM vocale, flux WS, budgets de latence
- [architecture/modules.md](architecture/modules.md) — Index des modules Python + C++
- [architecture/graph.md](architecture/graph.md) — Graphe de dépendances
- [implementation/](implementation/) — Guides d''implémentation
- [troubleshooting/](troubleshooting/) — Résolution d''incidents

---

## Audits & rapports actifs (2026-05-16)

Tous les audits historiques caducs (avant 2026-05-16) ont été supprimés lors du nettoyage Phase 3.

### Audits structurels
- [audits/AUDIT_PRE_NETTOYAGE_2026-05-16.md](audits/AUDIT_PRE_NETTOYAGE_2026-05-16.md) — Inventaire complet pré-nettoyage
- [audits/NETTOYAGE_RAPPORT_2026-05-16.md](audits/NETTOYAGE_RAPPORT_2026-05-16.md) — Exécution Phase 1+2 (4.89 Go libérés)

### Hardening & optimisation
- [audits/HARDENING_EXO_2026-05-16.md](audits/HARDENING_EXO_2026-05-16.md)
- [audits/OPTIMISATION_FINALE_2026-05-16.md](audits/OPTIMISATION_FINALE_2026-05-16.md)
- [audits/ORCHESTRATOR_OPT_2026-05-16.md](audits/ORCHESTRATOR_OPT_2026-05-16.md)

### Francisation
- [audits/FRANCISATION_BACKEND_2026-05-16.md](audits/FRANCISATION_BACKEND_2026-05-16.md)
- [audits/FRANCISATION_GUI_2026-05-16.md](audits/FRANCISATION_GUI_2026-05-16.md)

### Performance
- [PERF_REPORT_J1-J5.md](PERF_REPORT_J1-J5.md)
- [PERF_REPORT_J2-J3bis-J4bis.md](PERF_REPORT_J2-J3bis-J4bis.md)
- [PROFILING_LOAD_REPORT.md](PROFILING_LOAD_REPORT.md)

### Scans QML (snapshots 2026-05-01)
- [audits/qml_dead_scan_2026-05-01.json](audits/qml_dead_scan_2026-05-01.json)
- [audits/qml_dead_scan_post_cleanup_2026-05-01.json](audits/qml_dead_scan_post_cleanup_2026-05-01.json)

---

## Règles de contribution

Voir [CONTRIBUTING_DOCS.md](CONTRIBUTING_DOCS.md). La structure verrouillée est décrite dans [.structure.lock](.structure.lock).

---

## Politique LLM (verrouillée)

- Modèle unique : `claude-opus-4.7`
- Aucun fallback, aucune température, 10 règles strictes (cf [PROMPT_MAITRE.md](../PROMPT_MAITRE.md)).

## Politique TTS (verrouillée)

- Moteur exclusif : Orpheus 3B FR GGUF Q8 (CUDA, llama.cpp + SNAC) sur port 8767.
- XTTS / QtTTS / SAPI : interdits, références neutralisées.
