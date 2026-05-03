# COSYVOICE FR INSTALL (EXO)

Date: 2026-05-01
Périmètre: installation et exposition des voix FR CosyVoice sous `D:/EXO` uniquement.

## 1) Résumé exécutif

Cette intervention a appliqué les corrections code/config nécessaires pour une chaîne FR cohérente dans EXO, sans créer de fichiers hors `D:/EXO`.

Statut global:
- Chaîne logicielle FR (engine -> server -> TTSManager -> GUI): **corrigée**.
- Registre de voix FR (`voices.json`): **créé**.
- Confinement cache/modèles dans `D:/EXO`: **activé**.
- Artefacts FR complets ONNX/tokenizer/vocab/speaker_embeddings demandés: **non présents localement**, donc installation binaire complète **incomplète** à ce stade.

## 2) Modifications réalisées

### 2.1 Engine CosyVoice FR
Fichier modifié: `D:/EXO/project/python/tts/cosyvoice_engine.py`

Actions:
- Ajout du support prioritaire d'un registre `D:/EXO/models/cosyvoice/voices.json`.
- Déclaration explicite des voix FR dans `self.voices`.
- Gestion des alias de compatibilité (`legacy_id`), ex: `fr_denise -> fr_female_01`.
- Conservation de compatibilité avec `voices/voices_metadata.json` et découverte des WAV.
- `list_voices()` renvoie un ordre stable basé registre FR.

Effet attendu:
- La GUI peut recevoir une liste FR stable et complète.
- Les IDs historiques restent exploitables.

### 2.2 Serveur TTS: confinement strict des caches dans D:/EXO
Fichier modifié: `D:/EXO/project/python/tts/tts_server.py`

Actions:
- Définition par défaut de `EXO_COSYVOICE_MODELS = D:/EXO/models/cosyvoice`.
- Confinement cache dans `D:/EXO/models/cosyvoice/.cache` via:
  - `HF_HOME`
  - `HUGGINGFACE_HUB_CACHE`
  - `TRANSFORMERS_CACHE`
  - `TORCH_HOME`
  - `XDG_CACHE_HOME`

Effet attendu:
- Les téléchargements/caches pilotés par ces variables restent dans `D:/EXO`.

### 2.3 TTSManager: parsing robuste des voix pour GUI
Fichier modifié: `D:/EXO/project/app/audio/TTSManager.cpp`

Actions:
- `fetchAvailableVoices()` accepte désormais:
  - `available: ["id1", "id2", ...]`
  - `available: [{"id":"...","name":"..."}, ...]`
- Déduplication des IDs côté C++ avant publication `ttsVoicesChanged`.

Effet attendu:
- Exposition GUI fiable même si le format de payload évolue.

### 2.4 Registre FR créé
Fichier créé: `D:/EXO/models/cosyvoice/voices.json`

Voix déclarées:
- `fr_female_01` (legacy `fr_denise`)
- `fr_female_02` (legacy `fr_eloise`)
- `fr_female_03` (legacy `fr_vivienne`)
- `fr_male_01` (legacy `fr_henri`)
- `fr_male_02` (legacy `fr_remy`)

Chaque entrée associe:
- `id`
- `name`
- `file`
- `legacy_id`
- `model`
- `speaker_embedding` (chemin cible)
- `prompt_text`

## 3) Vérifications effectuées

### 3.1 Vérification syntaxe code
- `python -m py_compile` sur:
  - `python/tts/cosyvoice_engine.py`
  - `python/tts/tts_server.py`
- Résultat: OK.

### 3.2 Vérification diagnostics IDE
- Aucun problème reporté dans:
  - `python/tts/cosyvoice_engine.py`
  - `python/tts/tts_server.py`
  - `app/audio/TTSManager.cpp`

### 3.3 Vérification prérequis artefacts demandés
Contrôle de présence dans `D:/EXO/models/cosyvoice`:
- `model.onnx`: absent
- `decoder.onnx`: absent
- `tokenizer.json`: absent
- `vocab.json`: absent
- `assets/`: absent
- `speaker_embeddings/`: absent

Remarque:
- Le dossier contient des artefacts CosyVoice existants (`speech_tokenizer_v2*.onnx`, `flow.decoder.estimator.fp32.onnx`, etc.), mais pas les chemins/fichiers minimaux explicitement demandés dans la spécification de cette tâche.

## 4) Conformité aux règles

Règle "pas de création hors D:/EXO": respectée.

Créations/écritures effectuées:
- `D:/EXO/models/cosyvoice/voices.json`
- `D:/EXO/project/python/tts/cosyvoice_engine.py` (modif)
- `D:/EXO/project/python/tts/tts_server.py` (modif)
- `D:/EXO/project/app/audio/TTSManager.cpp` (modif)
- `D:/EXO/project/docs/COSYVOICE_FR_INSTALL.md` (ce rapport)

## 5) Écarts restants pour une installation FR "complète"

À fournir sous `D:/EXO/models/cosyvoice` pour conformité totale au cahier des charges:
- `model.onnx`
- `decoder.onnx`
- `tokenizer.json` (FR)
- `vocab.json` (FR)
- `assets/`
- `speaker_embeddings/fr_*.bin`

Sans ces artefacts sources locaux, l'installation binaire complète ne peut pas être finalisée automatiquement de manière fiable tout en garantissant strictement l'absence d'écritures hors `D:/EXO`.

## 6) Validation fonctionnelle attendue (à exécuter via launcher EXO)

Tests finaux recommandés:
1. Lancer EXO via launcher officiel.
2. Ouvrir paramètres voix et vérifier l'apparition des IDs FR:
   - `fr_female_01`, `fr_female_02`, `fr_female_03`, `fr_male_01`, `fr_male_02`
3. Faire un test TTS par voix et vérifier variation de timbre.
4. Confirmer que la langue est FR sur les synthèses.

## 7) Conclusion

Les adaptations logicielles FR sont en place et la GUI peut exposer un registre FR structuré.
La partie "installation de tous les modèles FR CosyVoice2" reste dépendante des artefacts FR source absents localement (ONNX/tokenizer/vocab/embeddings) à déposer dans `D:/EXO/models/cosyvoice`.
