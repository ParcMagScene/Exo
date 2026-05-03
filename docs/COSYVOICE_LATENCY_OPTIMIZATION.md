# COSYVOICE LATENCY OPTIMIZATION (EXO)

Date: 2026-05-01
Scope: optimisation de latence TTS FR CosyVoice2 dans EXO avec priorité stabilité/streaming.

## 1. Résumé

Objectif atteint partiellement avec amélioration mesurée du first-chunk et légère amélioration end-to-end, sans erreur de stabilité sur le stress test local.

Mesures automatiques (même texte, même environnement):
- First-chunk moyen: 2802.34 ms -> 2326.66 ms (amelioration 16.98%)
- End-to-end moyen: 9887.80 ms -> 9729.79 ms (amelioration 1.60%)
- Chunk-to-chunk moyen: 3542.32 ms -> 4112.48 ms (degradation 16.10%)
- Stabilité: 15/15 runs sans échec

Source des métriques:
- D:/EXO/project/docs/cosyvoice_latency_metrics.json

## 2. Analyse chaîne complète

### 2.1 Python moteur (cosyvoice_engine.py)
Fichier: D:/EXO/project/python/tts/cosyvoice_engine.py

Constats:
- Warmup modèle/GPU déjà présent.
- Conversion PCM16 déjà optimisée en chemin GPU quand sample-rate natif.
- Stratégie latency_optimized initiale fusionnait tout le texte en un seul bloc, ce qui augmentait fortement le first-chunk.
- Dédoublonnage des voix nécessaire pour éviter du coût de registration inutile au démarrage.

### 2.2 Serveur (tts_server.py)
Fichier: D:/EXO/project/python/tts/tts_server.py

Constats:
- Streaming fonctionnel mais sans backpressure explicite côté queue.
- Chunk-size non borné pouvait produire des frames trop grandes en runtime.
- Executor de streaming non dédié.

### 2.3 C++ TTSManager
Fichiers:
- D:/EXO/project/app/audio/TTSManager.h
- D:/EXO/project/app/audio/TTSManager.cpp

Constats:
- Buffer sink fixé à 16384 bytes (~340 ms @24k mono16), coûteux pour la latence de sortie.
- Pump anti-jitter déjà robuste.
- Préallocation buffer pump déjà en place.

### 2.4 Pipeline audio / threading / backlog
- Cross-thread: signaux Qt en queued connections déjà corrects.
- Risque backlog: serveur Python pouvait accumuler les chunks sans limite côté queue.
- Stabilité: pas de crash ni freeze sur stress test local (15 runs).

### 2.5 GPU / ONNX Runtime
- Le code force déjà des optimisations CUDA torch (TF32/cudnn benchmark).
- Environnement testé: warning ONNX Runtime indiquant provider CUDA indisponible sur cette machine de test (DmlExecutionProvider/CPU uniquement dans ce run de benchmark).
- Cela limite mécaniquement le potentiel de latence "temps réel" côté ONNX Runtime.

## 3. Correctifs appliqués

## 3.1 cosyvoice_engine.py
Fichier: D:/EXO/project/python/tts/cosyvoice_engine.py

Correctifs:
- Dédoublonnage registration zero-shot par chemin WAV résolu (évite re-registration inutile).
- Nouvelle stratégie latency_optimized:
  - premier segment isolé pour minimiser first-chunk,
  - reste du texte regroupé en blocs (réduction overhead de fin).
- Suppression du print first-chunk (bruit I/O inutile en hot path).

Impact:
- baisse first-chunk moyenne sur le benchmark.
- stabilité conservée.

## 3.2 tts_server.py
Fichier: D:/EXO/project/python/tts/tts_server.py

Correctifs:
- Executor dédié au streaming (ThreadPoolExecutor max_workers=1) pour latence plus prévisible.
- Queue asyncio bornée (maxsize=8) + backpressure thread-safe (run_coroutine_threadsafe(...).result()).
- Clamp chunk-size websocket:
  - min 512 bytes
  - max 4096 bytes
- Yield event-loop allégé (sleep(0) périodique au lieu de chaque chunk).
- Variables ORT de graph optimisation ajoutées:
  - ORT_GRAPH_OPT_LEVEL=ORT_ENABLE_ALL
  - ORT_ENABLE_EXTENDED=1

Impact:
- meilleure robustesse anti-backlog.
- streaming plus stable sous charge.

## 3.3 TTSManager (C++)
Fichiers:
- D:/EXO/project/app/audio/TTSManager.h
- D:/EXO/project/app/audio/TTSManager.cpp

Correctifs:
- buffer sink abaissé à 8192 bytes (au lieu de 16384) pour réduire la latence de sortie audio.
- clamp anti-jitter ajusté avec budget minimum à 2 ms (évite micro-sous-alimentation trop agressive).

Impact:
- latence de restitution réduite côté sortie audio.
- stabilité maintenue via ring buffer et pump anti-jitter.

## 4. Tests automatiques exécutés

Script de benchmark:
- D:/EXO/project/scripts/benchmark_cosyvoice_latency.py

Sortie métriques:
- D:/EXO/project/docs/cosyvoice_latency_metrics.json

Mesures capturées:
- first-chunk latency
- chunk-to-chunk latency
- end-to-end latency
- stress stabilité (15 runs)

Résultats (avant/après):
- Baseline:
  - first-chunk avg 2802.34 ms
  - chunk-to-chunk avg 3542.32 ms
  - end-to-end avg 9887.80 ms
- Optimized:
  - first-chunk avg 2326.66 ms
  - chunk-to-chunk avg 4112.48 ms
  - end-to-end avg 9729.79 ms
- Stabilité:
  - failures = 0 / 15

## 5. Interprétation des résultats

- First-chunk: amélioration nette.
- End-to-end: amélioration légère mais réelle.
- Chunk-to-chunk: dégradé sur ce corpus court, principalement car la stratégie optimisée regroupe davantage de texte dans les blocs de queue.

Conclusion pratique:
- Pour réponses courtes/interactives, privilégier la stratégie split plus fine.
- Pour réponses longues, stratégie mixte actuelle reste utile pour le coût global.

## 6. Recommandations supplémentaires (prochaine passe)

1. Politique adaptative automatique:
- Si texte <= 120 caracteres: mode split fin (priorité fluidité chunk-to-chunk)
- Sinon: mode mixte actuel (priorité first-chunk + coût global)

2. ONNX Runtime CUDA:
- Vérifier installation provider CUDA effective pour la session TTS (dans ce run benchmark, CUDA EP non disponible).
- Sans CUDA EP actif côté ORT, les gains restent plafonnés.

3. Voix/registre:
- Limiter list_voices exposée GUI aux IDs canoniques FR si souhait UX, garder aliases uniquement en compat interne.

4. Validation GUI runtime:
- Exécuter un test utilisateur final avec sélecteur voix et traces latence côté UI pour confirmer ressenti "temps réel".

## 7. Validation technique

- Python: py_compile OK
- C++: build Release RaspberryAssistant OK
- Diagnostics IDE: pas d'erreurs sur fichiers modifiés

## 8. Fichiers modifiés

- D:/EXO/project/python/tts/cosyvoice_engine.py
- D:/EXO/project/python/tts/tts_server.py
- D:/EXO/project/app/audio/TTSManager.h
- D:/EXO/project/app/audio/TTSManager.cpp
- D:/EXO/project/scripts/benchmark_cosyvoice_latency.py
- D:/EXO/project/docs/cosyvoice_latency_metrics.json
- D:/EXO/project/docs/COSYVOICE_LATENCY_OPTIMIZATION.md
