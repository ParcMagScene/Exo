# Validation complete TTS EXO apres bascule GPU

Date: 2026-05-01
Mode: validation automatique post-purge logs
Verdict global: PAS OK

## 1. Inventaire et venv TTS actif

- Python detectes:
  - D:/EXO/project/.venv/Scripts/python.exe
  - D:/EXO/project/.venv_stt_tts/Scripts/python.exe
  - D:/EXO/venv/exo/Scripts/python.exe
  - D:/EXO/venv/stt_tts/Scripts/python.exe
- Venv TTS configure:
  - config/services.json -> TTS -> venv=.venv_stt_tts
  - build/Release/config/services.json -> TTS -> venv=.venv_stt_tts
- Resolution runtime C++:
  - app/core/ServiceSupervisor.cpp pythonExeForVenv(venv) => projectDir()/venv/Scripts/python.exe

Conclusion:

- EXO pointe bien sur D:/EXO/project/.venv_stt_tts pour TTS.

## 2. Validation ORT dans le venv TTS actif

Probe execute dans D:/EXO/project/.venv_stt_tts:

- onnxruntime-gpu present: version 1.18.0
- ORT version importee: 1.18.0
- providers annonces: ['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']

Conclusion:

- Le venv est correctement equipe pour CUDA/TensorRT au niveau import/probe.

## 3. Purge et regeneration logs

Purge executee:

- D:/EXO/logs/tts_stderr.log supprime puis regenere
- D:/EXO/logs/tts_stdout.log supprime puis regenere
- D:/EXO/logs/tts_server.jsonl absent
- D:/EXO/project/logs/tts_* supprimes

Nouveaux logs verifies:

- D:/EXO/logs/tts_stderr.log (CreationTime 2026-05-01 19:26:48)
- D:/EXO/logs/tts_stdout.log (CreationTime 2026-05-01 19:26:48)
- D:/EXO/logs/tts_server.jsonl absent

## 4. Test TTS reel

Test execute:

- python test_tts_client.py
- resultat client: SUCCESS: Received 0 chunks

Observation stderr TTS:

- CosyVoice CUDA device detecte
- Stream worker error: Model not loaded

Conclusion:

- Le pipeline TTS ne produit pas d audio utile (0 chunks), donc la generation n est pas validee.

## 5. Verification des criteres demandes

- CUDAExecutionProvider actif (venv probe): OK
- TensorrtExecutionProvider actif (venv probe): OK
- EXO utilise le bon venv TTS: OK
- Aucune trace DmlExecutionProvider dans nouveaux logs: OK
- Aucune trace fallback explicite dans nouveaux logs: OK
- CPUExecutionProvider en mode CPU-only dans logs: NON OBSERVE
- CosyVoice charge en CUDA (ligne device): OK
- CosyVoice2 pret et inference validee (device=cuda + audio reel): PAS OK
- InferenceSession created with providers: ['CUDAExecutionProvider', ...] dans logs: PAS TROUVE

## 6. Verdict final

PAS OK

Motif principal:

- Le venv expose bien CUDA/TensorRT, mais le runtime TTS reel ne valide pas une inference fonctionnelle (Model not loaded, 0 chunks).

## 7. Corrections exactes a appliquer

1. Ajouter un log explicite des providers effectifs lors de la creation de session ONNX dans le code TTS/CosyVoice (au moment de l InferenceSession).
2. Forcer l echec dur si le modele n est pas charge, avant acceptation de requetes websocket (ne pas retourner end avec 0 chunk).
3. Verifier l ordre d initialisation CosyVoice2 et la completion de phase online avant traitement client.
4. Ajouter un test de sante TTS post-ready qui genere une phrase courte et verifie au moins 1 chunk audio.
5. Reexecuter la meme validation post-purge; le statut passe a OK uniquement si:
   - au moins 1 chunk audio recu,
   - aucune trace DML/fallback,
   - trace explicite providers effectifs CUDA/TensorRT dans logs.
