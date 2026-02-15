# 🔐 Variables d'Environnement - Référence Complète

## Format .env

Créer un fichier `.env` à la racine avec les variables suivantes.

---

## 🔴 VARIABLES OBLIGATOIRES

### Azure OpenAI (GPT-4o)

```env
# Endpoint du service Azure OpenAI
# Format: https://<NOM-RESOURCE>.openai.azure.com/
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# Clé API Azure
# Récupérer depuis Azure Portal > Manage Keys
AZURE_OPENAI_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Nom du déploiement (doit être créé dans Azure)
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Version API Azure
# (Généralement ne pas changer)
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### Home Assistant

```env
# URL de Home Assistant
# Format: http://<IP>:8123 ou http://homeassistant.local:8123
HA_URL=http://homeassistant.local:8123

# Token long-lived (créer dans HA > Settings > Users > Profile)
# Ne jamais exposer cette clé !
HA_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

---

## 🟡 VARIABLES OPTIONNELLES RECOMMANDÉES

### Hardware

```env
# Détection automatique du device
# Options: auto, cuda, cpu, hip (AMD GPU)
DEVICE=auto

# Nombre de workers pour Faster-Whisper (multi-threading)
# Adapter au CPU: 8 pour i9, 4 pour i5, 2 pour Pi
WHISPER_WORKERS=8

# Taille du modèle Whisper
# Options: tiny, base, small, medium, large
# "base" = bon compromis vitesse/précision FR (~0.5-1s)
# "small" = meilleure précision mais ~2-3x plus lent
WHISPER_MODEL=base

# ========== VAD (Voice Activity Detection) ==========
# Multiplicateur du bruit ambiant pour le seuil adaptatif
# Le seuil effectif = bruit_ambiant × multiplicateur
# Plus bas = plus sensible (capte mieux les voix douces)
# Plus haut = plus strict (filtre mieux le bruit)
EXO_VAD_MULTIPLIER=2.5
```

### TTS (Text-to-Speech) - Kokoro + Piper + Fish-Speech + XTTS v2

```env
# ========== Moteur TTS préféré ==========
# Ordre de priorité: kokoro > piper > openai > fish > coqui
# Options: kokoro, piper, openai, fish, coqui
TTS_ENGINE=kokoro

# ========== Kokoro TTS (Primary - Haute qualité locale) ==========
# Voix Kokoro française (voir https://huggingface.co/hexgrad/Kokoro-82M)
# Voix FR: ff_siwis (femme), ff_alma (femme alt), fm_music (homme)
KOKORO_VOICE=ff_siwis

# Langue Kokoro: f=français, e=english, j=japanese, z=chinese
KOKORO_LANG=f

# Activer/désactiver Kokoro
KOKORO_ENABLED=true

# ========== Piper TTS (Fallback rapide local) ==========
# Chemin vers le modèle Piper .onnx
PIPER_MODEL=models/piper/fr_FR-siwis-medium.onnx
PIPER_ENABLED=true

# ========== Fish-Speech (Optionnel, via Docker) ==========
# Endpoint du serveur Fish-Speech (HTTP REST API)
# Si vous utilisez Docker: http://localhost:8000
FISH_SPEECH_URL=http://localhost:8000

# ========== TTS Fallback ==========
# Activer XTTS v2 comme fallback si tous les autres échouent
# Options: true, false (défaut: true)
TTS_FALLBACK=true

# Device pour XTTS v2 (si fallback activé)
# Options: auto, cuda, cpu (défaut: auto = auto-detect)
XTTS_DEVICE=auto

# ========== Timeout & Retry ==========
# Timeout pour Fish-Speech en secondes (défaut: 30)
TTS_TIMEOUT=30

# Nombre de tentatives avant fallback (défaut: 2)
TTS_RETRIES=2
```

### Musique (Mopidy/TIDAL)

```env
# URL du serveur Mopidy
MOPIDY_URL=http://localhost:6680

# Qualité TIDAL
# Options: LOSSLESS, HI_RES, MASTER, NORMAL
TIDAL_QUALITY=LOSSLESS
```

### GUI Pygame

```env
# Résolution de la fenêtre GUI
GUI_WIDTH=800
GUI_HEIGHT=600

# Cible FPS (144 recommandé pour fluide)
GUI_FPS=144

# Activer/désactiver le rendu GPU
ENABLE_PYGAME=true
```

### Wyoming Protocol (multi-room)

```env
# Adresse du serveur Wisconsin
# 0.0.0.0 = écoute sur toutes les interfaces
WYOMING_HOST=0.0.0.0

# Port Wyoming
# Défaut: 10700
WYOMING_PORT=10700
```

### Logging

```env
# Niveau de log
# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO
```

---

## 🟢 VARIABLES DE DÉVELOPPEMENT

```env
# Mode debug (plus de logs détaillés)
DEBUG=false

# Mock Home Assistant (pour test sans HA réel)
MOCK_HA=false
```

---

## 📝 Exemple de .env Complet

```env
# ==================== AZURE OPENAI ====================
AZURE_OPENAI_ENDPOINT=https://my-openai.openai.azure.com/
AZURE_OPENAI_KEY=abc123xyz789...
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_MODEL=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# ==================== HOME ASSISTANT ====================
HA_URL=http://192.168.1.100:8123
HA_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiI4ZDk4NzBh...

# ==================== HARDWARE ====================
DEVICE=auto
WHISPER_WORKERS=8
WHISPER_MODEL=base

# ==================== VAD (Voice Activity Detection) ====================
EXO_VAD_MULTIPLIER=2.5

# ==================== TTS ====================
FISH_SPEECH_ENDPOINT=http://localhost:8000

# ==================== MUSIQUE ====================
MOPIDY_URL=http://localhost:6680
TIDAL_QUALITY=LOSSLESS

# ==================== GUI ====================
GUI_WIDTH=800
GUI_HEIGHT=600
GUI_FPS=144
ENABLE_PYGAME=true

# ==================== WYOMING ====================
WYOMING_HOST=0.0.0.0
WYOMING_PORT=10700

# ==================== LOGGING ====================
LOG_LEVEL=INFO

# ==================== DEV ====================
DEBUG=false
MOCK_HA=false
```

---

## 🔓 Récupérer les Clés

### Azure OpenAI

1. Aller à https://portal.azure.com
2. Créer ou utiliser une ressource "Azure OpenAI Service"
3. Aller à "Keys and Endpoints"
4. Copier :
   - `AZURE_OPENAI_ENDPOINT` (ex: https://my-openai.openai.azure.com/)
   - `AZURE_OPENAI_KEY` (Key 1 ou 2)

### Home Assistant Token

1. Se connecter à Home Assistant (http://homeassistant:8123)
2. Cliquer sur le profil (coin bas-gauche)
3. Défiler vers le bas → "Long-lived access tokens"
4. Créer un nouveau token
5. Copier la valeur entière dans `HA_TOKEN`

---

## ⚠️ Sécurité

- **Ne jamais** committer `.env` dans Git
- **Ne jamais** exposer `AZURE_OPENAI_KEY` ou `HA_TOKEN` publiquement
- Utiliser des secrets managers en production (Azure Key Vault, HashiCorp Vault)
- Limiter les permissions du token HA au strict nécessaire

---

## 🧪 Vérifier Configuration

```bash
# Test Azure OpenAI
python << 'EOF'
import os
from dotenv import load_dotenv

load_dotenv()
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
key = os.getenv("AZURE_OPENAI_KEY")

if endpoint and key:
    print("✅ Azure OpenAI configuré")
else:
    print("❌ Manquant: AZURE_OPENAI_ENDPOINT ou AZURE_OPENAI_KEY")
EOF

# Test Home Assistant
curl -H "Authorization: Bearer $(grep HA_TOKEN .env | cut -d'=' -f2)" \
     http://homeassistant.local:8123/api/states | head -20
# Doit retourner du JSON, pas 401
```

---

## 📚 Références

- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Home Assistant Long-Lived Tokens](https://www.home-assistant.io/docs/authentication/#your-account-profile)
- [Fish-Speech API](https://github.com/fishaudio/fish-speech)
- [Faster-Whisper](https://github.com/guillaumekln/faster-whisper)
