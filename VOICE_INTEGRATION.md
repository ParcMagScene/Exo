# 🎤 Pipeline Vocal — Architecture Audio d'EXO

## Vue d'ensemble

Pipeline vocal complet : capture micro → détection voix → transcription → LLM → synthèse → playback.

**Status :** ✅ Implémenté et opérationnel

## Pipeline

```
┌──────────────┐
│  Microphone  │  PyAudio (16kHz, mono, PCM16)
│   (PyAudio)  │
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│  VAD Adaptatif   │  wake_word.py — calibration bruit ambiant
│  (RMS energy)    │  seuil dynamique = noise_floor × multiplicateur
└──────┬───────────┘
       │ bytes (utterance complète)
       ▼
┌──────────────────┐
│  Faster-Whisper  │  STT — modèle "base" (configurable)
│  (beam_size=1)   │  langue: FR, exécution dans executor thread
└──────┬───────────┘
       │ str (transcription)
       ▼
┌──────────────────┐
│  Wake Word       │  Détection "Exo" (13 variantes phonétiques)
│  + Extraction    │  Extraction commande après wake word
└──────┬───────────┘
       │ str (commande)
       ▼
┌──────────────────┐
│  BrainEngine     │  GPT-4o-mini + RAG ChromaDB + Function Calling
│  (GPT-4o-mini)   │  max_tokens=80, contexte local (heure, météo)
└──────┬───────────┘
       │ str (réponse)
       ▼
┌──────────────────┐
│  Kokoro TTS      │  Synthèse locale 24kHz, voix ff_siwis
│  (cascade)       │  Fallback: Piper → OpenAI → Fish-Speech → Coqui
└──────┬───────────┘
       │ bytes (WAV)
       ▼
┌──────────────────┐
│  Pygame mixer    │  Playback synchrone, micro coupé pendant réponse
│  (playback)      │
└──────────────────┘
```

## Composants

### 1. VAD — Voice Activity Detection (`src/audio/wake_word.py`)

Détection d'activité vocale par énergie RMS avec seuil adaptatif.

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| `VOICE_THRESHOLD` | 300 RMS | Seuil fixe (ajusté par l'adaptatif) |
| `SILENCE_CHUNKS` | 8 (~0.5s) | Silence requis pour fin d'utterance |
| `MIN_UTTERANCE_SEC` | 0.5s | Durée minimum d'une utterance valide |
| `MIN_VOICE_CHUNKS` | 4 | Chunks vocaux minimum (filtre bruit) |
| `EXO_VAD_MULTIPLIER` | 2.5 | Multiplicateur bruit ambiant → seuil |

**Calibration automatique :** Au démarrage, mesure 30 chunks de bruit ambiant (médiane RMS). Le seuil effectif = `noise_floor × EXO_VAD_MULTIPLIER`, borné entre 50% et 150% du seuil fixe.

### 2. STT — Speech-to-Text (`src/core/listener.py`)

Faster-Whisper avec exécution dans un thread executor (non-bloquant).

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| `WHISPER_MODEL` | base | Modèle (tiny/base/small/medium/large) |
| `beam_size` | 1 | Recherche greedy (plus rapide) |
| `language` | fr | Langue forcée français |
| Compute | CPU, float32 | Compatible tous systèmes |

**Latence mesurée :** ~0.5-1.5s (modèle "base" sur CPU)

**Filtre hallucinations :** Les transcriptions parasites de Whisper sur le silence ("sous-titres", "amara.org", "merci d'avoir regardé"...) sont automatiquement rejetées.

### 3. Wake Word (`src/audio/wake_word.py`)

Détection du mot "Exo" dans la transcription Whisper.

**Variantes reconnues :** exo, écho, echo, expo, ego, exc, exot, x.o, x o, exau, exeau, exos, exho

**Extraction commande :** "Exo, quelle heure est-il ?" → "quelle heure est-il ?"

### 4. TTS — Text-to-Speech (`src/assistant/tts_client.py`)

Cascade de moteurs TTS par ordre de priorité :

| Priorité | Moteur | Type | Latence | Qualité |
|----------|--------|------|---------|---------|
| 1 | **Kokoro** | Local | ~0.8s | Haute (quasi-humaine) |
| 2 | Piper | Local | ~0.3s | Bonne |
| 3 | OpenAI TTS-1 | API | ~1-2s | Très haute |
| 4 | Fish-Speech | API | Variable | Bonne |
| 5 | Coqui VITS | Local | ~2-3s | Moyenne |

### 5. Playback (`src/core/listener.py`)

- Pygame mixer initialisé au sample rate du TTS actif (24kHz pour Kokoro)
- Micro coupé pendant la réponse (anti-écho)
- Buffer micro vidé après playback

## Latence End-to-End

| Étape | Durée typique |
|-------|---------------|
| Capture VAD | 0.5-1s (parole + 0.5s silence) |
| Whisper STT | 0.5-1.5s |
| Brain GPT-4o-mini | 0.5-1.5s |
| Kokoro TTS | ~0.8s |
| **Total** | **~2-4s** |

## Diagnostic

```bash
# Monitoring temps réel (niveaux micro, VAD, STT, wake word)
python examples/test_pipeline_monitor.py --rounds 5

# Test E2E complet avec réponse vocale
python examples/test_e2e_vocal.py
```

## Configuration

```env
# STT
WHISPER_MODEL=base             # tiny|base|small|medium|large

# VAD
EXO_VAD_MULTIPLIER=2.5        # Sensibilité (plus bas = plus sensible)

# TTS
TTS_ENGINE=kokoro              # kokoro|piper|openai|fish|coqui
KOKORO_VOICE=ff_siwis          # Voix française
KOKORO_LANG=f                  # f = français
```
