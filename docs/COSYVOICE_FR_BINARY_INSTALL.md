# COSYVOICE FR BINARY INSTALL (EXO)

Date: 2026-05-01
Périmètre: installation des artefacts FR CosyVoice2 uniquement sous D:/EXO/models/cosyvoice.

## 1) Résultat global

Installation binaire FR complétée localement dans D:/EXO/models/cosyvoice:
- model.onnx: OK
- decoder.onnx: OK
- tokenizer.json: OK
- vocab.json: OK
- assets/: OK
- speaker_embeddings/fr_*.bin: OK

Contrainte d'écriture hors D:/EXO:
- Respectée pendant l'exécution (variables de cache forcées vers D:/EXO/models/cosyvoice/.cache).

## 2) Fichiers installés / créés

Sources de vérité:
- D:/EXO/models/cosyvoice/fr_install_summary.json
- D:/EXO/models/cosyvoice/fr_audio_test_summary.json

Créations effectuées:
- D:/EXO/models/cosyvoice/model.onnx
- D:/EXO/models/cosyvoice/decoder.onnx
- D:/EXO/models/cosyvoice/tokenizer.json
- D:/EXO/models/cosyvoice/vocab.json
- D:/EXO/models/cosyvoice/assets/dingding.png
- D:/EXO/models/cosyvoice/speaker_embeddings/fr_female_01.bin
- D:/EXO/models/cosyvoice/speaker_embeddings/fr_female_02.bin
- D:/EXO/models/cosyvoice/speaker_embeddings/fr_female_03.bin
- D:/EXO/models/cosyvoice/speaker_embeddings/fr_male_01.bin
- D:/EXO/models/cosyvoice/speaker_embeddings/fr_male_02.bin

## 3) Détails d'installation

### 3.1 Modèles ONNX FR
- model.onnx: provisionné localement
- decoder.onnx: provisionné localement

### 3.2 Tokenizer / vocab
- tokenizer.json: provisionné au root modèle
- vocab.json: provisionné au root modèle

### 3.3 Assets
- assets/ créé et peuplé (resource interne disponible)

### 3.4 Speaker embeddings FR
Embeddings générés depuis les prompts FR et déposés sous:
- D:/EXO/models/cosyvoice/speaker_embeddings/fr_female_01.bin
- D:/EXO/models/cosyvoice/speaker_embeddings/fr_female_02.bin
- D:/EXO/models/cosyvoice/speaker_embeddings/fr_female_03.bin
- D:/EXO/models/cosyvoice/speaker_embeddings/fr_male_01.bin
- D:/EXO/models/cosyvoice/speaker_embeddings/fr_male_02.bin

## 4) Vérification code

### 4.1 cosyvoice_engine.py
Fichier: D:/EXO/project/python/tts/cosyvoice_engine.py

Vérifications/corrections:
- Support prioritaire du registre D:/EXO/models/cosyvoice/voices.json
- Déclaration explicite des voix FR dans self.voices
- Résolution d'alias legacy_id vers IDs FR canoniques
- Validation/résolution du champ speaker_embedding (chemin absolu + warning si absent)

### 4.2 voices.json
Fichier: D:/EXO/models/cosyvoice/voices.json

Chaque voix FR contient:
- id
- name
- model
- speaker_embedding
- prompt_text
- file
- legacy_id

Voix FR canoniques:
- fr_female_01
- fr_female_02
- fr_female_03
- fr_male_01
- fr_male_02

### 4.3 TTSManager / exposition GUI
Fichier: D:/EXO/project/app/audio/TTSManager.cpp

Vérification/correction:
- fetchAvailableVoices() accepte available en liste de strings et en liste d'objets {id,name}
- déduplication d'IDs avant publication vers la GUI

Impact attendu:
- m_ttsVoices expose correctement toutes les voix FR renvoyées par le serveur.

## 5) Tests audio FR

Script de test exécuté:
- génération d'un WAV par voix FR via CosyVoiceEngine (lang=fr)
- sortie dans D:/EXO/models/cosyvoice/test_audio_fr

Résultats:
- fr_female_01.wav: 6.12 s
- fr_female_02.wav: 5.68 s
- fr_female_03.wav: 6.12 s
- fr_male_01.wav: 6.08 s
- fr_male_02.wav: 5.84 s

Résumé détaillé:
- D:/EXO/models/cosyvoice/fr_audio_test_summary.json

## 6) Vérification GUI runtime

Demande: confirmer affichage GUI de toutes les voix FR et sélection fonctionnelle.

Statut:
- Vérification runtime via launcher officiel non exécutée car les deux chemins autorisés sont absents:
  - D:/EXO/exo.exe (absent)
  - D:/EXO/project/scripts/exo_launcher.py (absent)

Conséquence:
- Validation GUI runtime bloquée tant qu'un launcher officiel autorisé n'est pas disponible.
- Validation code/chaîne de données effectuée (engine -> serveur -> TTSManager) avec tests audio positifs.

## 7) Conformité contraintes

- Écritures hors D:/EXO: non détectées pendant l'installation.
- Variables de cache redirigées vers D:/EXO/models/cosyvoice/.cache.
- Aucun service EXO n'a été lancé individuellement pour cette installation binaire.

## 8) Correctifs appliqués (fichiers modifiés)

- D:/EXO/project/python/tts/cosyvoice_engine.py
- D:/EXO/project/python/tts/tts_server.py
- D:/EXO/project/app/audio/TTSManager.cpp
- D:/EXO/models/cosyvoice/voices.json

## 9) Conclusion

Les artefacts binaires FR demandés sont désormais présents sous D:/EXO/models/cosyvoice et les voix FR canoniques sont testées audio localement avec succès.

Le seul point restant pour une garantie complète "GUI affichage + sélection" est la disponibilité d'un launcher officiel autorisé (D:/EXO/exo.exe ou D:/EXO/project/scripts/exo_launcher.py) pour exécuter la vérification runtime de bout en bout côté interface.
