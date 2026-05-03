# EXO - Audit Arborescence et Corrections

Date: 2026-05-01
Perimetre analyse: D:/EXO (models, project, whispercpp, faiss, cache, logs, files)

## 1. Analyse complete de l'arborescence actuelle

Arborescence racine detectee:

- D:/EXO/cache
- D:/EXO/config
- D:/EXO/CosyVoice
- D:/EXO/faiss
- D:/EXO/files
- D:/EXO/logs
- D:/EXO/models
- D:/EXO/project
- D:/EXO/venv
- D:/EXO/whispercpp

Etat du dossier models apres correction:

- D:/EXO/models/cosyvoice
- D:/EXO/models/whisper
- D:/EXO/models/wakeword
- D:/EXO/models/huggingface

Etat ressources critiques:

- Whisper models presents (small, medium, large-v3)
- Wakeword models presents (dont hey_jarvis_v0.1.onnx, silero_vad.onnx)
- whisper.cpp binaire present (D:/EXO/whispercpp/build_vk/bin/Release/whisper-server.exe)
- FAISS present dans D:/EXO/faiss/semantic_memory (embeddings.faiss, metadata_v2.json, exa_memory.json)

## 2. Liste des erreurs detectees

1. Dossier D:/EXO/CosyVoice contient un depot source complet (avec .git), pas un dossier modele.
2. Les chemins actifs pointaient vers D:/EXO/models/CosyVoice2-0.5B au lieu de D:/EXO/models/cosyvoice.
3. Dependance explicite a sys.path.insert dans python/tts/cosyvoice_engine.py.
4. Variables COSYVOICE_ROOT encore diffusees dans plusieurs chemins d'execution.
5. Le schema cible demande (model.onnx, decoder.onnx, config.json, tokenizer.json, vocab.json, assets, speaker_embeddings) n'est pas present dans D:/EXO/models/cosyvoice.

## 3. Liste des dossiers a supprimer

Suppression recommandee (apres phase de migration TTS finalisee):

- D:/EXO/CosyVoice

Justification:

- Depot source complet non conforme a l'objectif de production.
- A conserver temporairement uniquement tant qu'un runtime CosyVoice installable n'est pas disponible autrement.

## 4. Liste des dossiers a deplacer

Corrections appliquees:

1. Deplacement effectue:
- D:/EXO/models/CosyVoice2-0.5B -> D:/EXO/models/cosyvoice

A verifier ensuite:

2. Legacy potentiel:
- D:/EXO/venv (si non utilise)

## 5. Liste des modeles manquants

Structure demandee mais absente dans D:/EXO/models/cosyvoice:

- model.onnx (manquant)
- decoder.onnx (manquant)
- config.json (manquant)
- tokenizer.json (manquant)
- vocab.json (manquant)
- assets/ (manquant; actuellement asset/)
- speaker_embeddings/ (manquant)

Contenu actuellement present (extraits):

- campplus.onnx
- flow.decoder.estimator.fp32.onnx
- speech_tokenizer_v2.onnx
- configuration.json
- cosyvoice2.yaml
- llm.pt, flow.pt, hift.pt
- asset/, voices/

## 6. Liste des corrections a appliquer

Corrections appliquees dans ce cycle:

1. Normalisation des chemins CosyVoice vers D:/EXO/models/cosyvoice.
2. Suppression des injections sys.path.insert dans cosyvoice_engine.py.
3. Fallback d'import sans sys.path.insert (site.addsitedir) pour compatibilite transitoire.
4. Nettoyage de COSYVOICE_ROOT des variables d'environnement d'orchestration.
5. Correction de 2 f-strings invalides dans python/test/exo_test_runner.py.

Corrections restantes (obligatoires pour cloture complete):

1. Installer un runtime CosyVoice packaging-compatible (ou refactorer vers ONNX pur) pour supprimer definitivement la dependance au repo D:/EXO/CosyVoice.
2. Harmoniser le format des modeles cosyvoice avec le schema exige (ou ajuster le schema cible aux fichiers reels de CosyVoice2).
3. Purger le dossier D:/EXO/CosyVoice une fois le point 1 valide.

## 7. Liste des fichiers modifies

Fichiers modifies:

- app/core/ServiceSupervisor.cpp
- app/core/ServiceManager.cpp
- app/safeboot/SafeBootAutoRepair.cpp
- launch_exo.ps1
- python/start_missing_services.py
- python/tts/cosyvoice_engine.py
- python/test/exo_test_runner.py
- .env
- .vscode/settings.json

Fichiers de configuration verifies sans modification necessaire immediate:

- config/services.json
- config/assistant.conf

## 8. Liste des chemins incorrects

Chemins corriges:

- /models/CosyVoice2-0.5B -> /models/cosyvoice
- suppression des injections explicites COSYVOICE_ROOT dans l'environnement de lancement principal

Chemins encore a traiter selon politique finale deprod:

- D:/EXO/CosyVoice (depot source runtime, a supprimer apres migration runtime)

## 9. Plan de correction complet

Phase A - Terminee (effectuee)

1. Normalisation des chemins CosyVoice dans C++, Python, scripts et env.
2. Deplacement du dossier modele vers D:/EXO/models/cosyvoice.
3. Retrait de sys.path.insert et correction syntaxique du runner de tests.

Phase B - A faire (bloquant suppression repo)

1. Rendre l'import cosyvoice independant du depot D:/EXO/CosyVoice:
- option 1: package installable officiel
- option 2: backend ONNX autonome
2. Verifier un demarrage complet tts_server sans COSYVOICE_ROOT.
3. Supprimer D:/EXO/CosyVoice.

Phase C - Finalisation conformite modele

1. Aligner le contenu de D:/EXO/models/cosyvoice avec la spec cible exacte.
2. Valider voix, synthese streaming et latence.
3. Mettre a jour la documentation d'exploitation.

## 10. Verification finale du pipeline vocal

Verifications executees:

1. STT/WakeWord/TTS scripts demarrables en mode CLI (--help) avec PYTHONPATH=project/python.
2. Presence des artefacts STT:
- D:/EXO/models/whisper/*.bin
- D:/EXO/whispercpp/build_vk/bin/Release/whisper-server.exe
3. Presence des artefacts WakeWord:
- D:/EXO/models/wakeword/hey_jarvis_v0.1.onnx
- D:/EXO/models/wakeword/silero_vad.onnx
4. Verification code pipeline:
- TTS streaming chunks PCM16 dans python/tts/tts_server.py
- reception/traitement chunk cote C++ dans app/audio/TTSManager.cpp
- orchestration STT/VAD/WakeWord/TTS dans app/audio/VoicePipeline.cpp

Resultat actuel:

- Pipeline code-level coherent: OUI
- Ressources STT/WakeWord/whisper.cpp: OK
- Conformite stricte modele cosyvoice a la spec demandee: NON (ecart de format)
- Suppression securisee de D:/EXO/CosyVoice sans regression TTS: PAS ENCORE VALIDE

Conclusion:

La base est remise en coherence de chemins et d'arborescence pour le runtime EXO, mais la suppression definitive du depot D:/EXO/CosyVoice exige un runtime CosyVoice packaging-compatible ou un backend ONNX autonome pour rester pleinement fonctionnel.
