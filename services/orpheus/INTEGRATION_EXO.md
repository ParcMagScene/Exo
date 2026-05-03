# Integration Orpheus dans EXO

## Architecture

`server_ws.py` est un **drop-in replacement** WebSocket du TTS CosyVoice2
(`python/tts/tts_server_streaming.py`). Memes :

- protocole WS (synthesize / cancel / ping / list_voices / set_voice)
- format binaire (PCM16 mono 24 kHz LE en chunks)
- messages start / end avec metriques (first_chunk_ms, RTF, chunks)
- endpoint HTTP `/health` multiplexe sur le meme port
- port (8767)

Aucune modification client / Qt / config requise.

## Activation

Via variable d'environnement **avant** de demarrer EXO :

```powershell
$env:EXO_TTS_ENGINE = 'orpheus'   # active Orpheus
# ou
$env:EXO_TTS_ENGINE = 'cosyvoice' # par defaut, restaure CosyVoice
```

Puis lancer EXO normalement (jamais a la main les services Python) :

```powershell
D:\EXO\exo.exe
# ou en dev :
. D:\EXO\project\launch_exo_silent.ps1 ; Start-EXO
```

Les deux launchers (`launch_exo.ps1` et `launch_exo_silent.ps1`) lisent
`$env:EXO_TTS_ENGINE`, choisissent l'interpreteur Python (venv Orpheus
dedie `services/orpheus/venv/`) et le script (`services/orpheus/server_ws.py`)
correspondant, sur le port 8767.

Si la venv Orpheus est manquante, fallback automatique sur CosyVoice avec
warning dans le log.

## Verification

```powershell
# Healthcheck
Invoke-RestMethod http://127.0.0.1:8767/health
# attendu : { engine = "orpheus-gguf" ; sample_rate = 24000 ; ... }

# Test rapide via le client EXO existant :
D:\EXO\project\.venv_stt_tts\Scripts\python.exe -m tts.tts_client --text "Bonjour" --out test.wav
```

## Modeles requis

- GGUF : `D:\EXO\models\orpheus_fr_gguf\Orpheus-3b-French-FT-Q8_0.gguf`
- SNAC : telecharge automatiquement via HF (`hubertsiuzdak/snac_24khz`)

## Performances mesurees (RTX 3070, 8 Go)

- Mode batch HTTP : RTF 1.57 sur 3.18 s d'audio
- Mode WS streaming : voir logs `[ws] DONE first=... RTF=...`

## Variables d'environnement

| Var | Defaut | Effet |
|-----|--------|-------|
| `EXO_TTS_ENGINE` | `cosyvoice` | `orpheus` pour activer |
| `ORPHEUS_GGUF_PATH` | chemin par defaut ci-dessus | override .gguf |
| `ORPHEUS_N_CTX` | 4096 | contexte LLM |
| `ORPHEUS_N_GPU_LAYERS` | -1 | -1 = tout en GPU |
| `ORPHEUS_DEFAULT_VOICE` | `pierre` | pierre/amelie/marie |
| `ORPHEUS_VOICES` | `pierre,amelie,marie` | liste csv |
| `ORPHEUS_WS_CHUNK_BYTES` | 480 | taille chunk PCM (~10 ms) |
