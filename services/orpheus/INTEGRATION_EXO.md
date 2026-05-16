# Integration Orpheus dans EXO

## Architecture

`services/orpheus/server_ws.py` est l'unique serveur TTS d'EXO depuis la
politique 2026-05-03. Il fournit :

- protocole WS (`synthesize` / `cancel` / `ping` / `list_voices` / `set_voice`)
- format binaire (PCM16 mono 24 kHz LE en chunks de 1920 octets / 40 ms)
- messages `start` / `end` avec metriques (`first_chunk_ms`, RTF, `chunks`)
- endpoint HTTP `/health` multiplexe sur le meme port
- port 8767

Aucun fallback alternatif : Orpheus 3B FR (GGUF Q8) CUDA est le seul moteur.

## Activation

Le serveur est demarre automatiquement par `launch_exo_silent.ps1`
(via le venv dedie `services/orpheus/venv/`) :

```powershell
. D:\EXO\project\launch_exo_silent.ps1 ; Start-EXO
```

Si la venv Orpheus est manquante, le launcher logue un `FAIL` et le
TTS est indisponible (pas de fallback silencieux).

## Verification

```powershell
# Healthcheck
Invoke-RestMethod http://127.0.0.1:8767/health
# attendu : { engine = "orpheus-gguf" ; sample_rate = 24000 ; ... }

# Test rapide via le client EXO :
D:\EXO\project\.venv_stt_tts\Scripts\python.exe -m tts.tts_client --text "Bonjour" --out test.wav
```

## Modeles requis

- GGUF : `D:\EXO\models\orpheus_fr_gguf\Orpheus-3b-French-FT-Q8_0.gguf`
- SNAC : telecharge automatiquement via HF (`hubertsiuzdak/snac_24khz`)

## Performances mesurees (RTX 3070, 8 Go)

- Mode batch HTTP : RTF ~1.57 sur 3.18 s d'audio
- Mode WS streaming : voir logs `[ws] DONE first=... RTF=...`

## Variables d'environnement

| Var | Defaut | Effet |
|-----|--------|-------|
| `ORPHEUS_GGUF_PATH` | chemin par defaut ci-dessus | override .gguf |
| `ORPHEUS_N_CTX` | 4096 | contexte LLM |
| `ORPHEUS_N_GPU_LAYERS` | -1 | -1 = tout en GPU |
| `ORPHEUS_DEFAULT_VOICE` | `pierre` | pierre / amelie / marie |
| `ORPHEUS_VOICES` | `pierre,amelie,marie` | liste csv |
| `ORPHEUS_WS_CHUNK_BYTES` | 1920 | taille chunk PCM (40 ms @ 24 kHz) |
| `EXO_ORPHEUS_MODELS` | `D:\EXO\models\orpheus_fr_gguf` | racine modeles Orpheus |
