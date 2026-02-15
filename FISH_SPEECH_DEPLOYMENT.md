# 🐟 Fish-Speech Deployment Guide

## Vue d'ensemble

Fish-Speech est le moteur TTS (Text-to-Speech) principal du projet. Il génère de l'audio naturel et expressif en français.

- **Primary TTS**: Fish-Speech (réseau, haute qualité)
- **Fallback TTS**: XTTS v2 (local, GPU-ready, rechute gracieuse)

---

## 🚀 Déploiement Rapide (Docker Recommandé)

### Option 1: Docker Compose (Complet)

Tout-en-un avec Home Assistant, Fish-Speech, assistant main :

```bash
# À la racine du projet
docker-compose up -d

# Logs
docker-compose logs -f fish-speech

# Vérifier santé
docker-compose ps
```

### Option 2: Docker Image Seule

Lancer uniquement le service Fish-Speech :

```bash
# Télécharger l'image
docker pull fish-audio/fish-speech:latest

# Lancer le container
docker run -d \
  --name fish-speech \
  -p 8000:8000 \
  -v fish-speech-models:/app/models \
  fish-audio/fish-speech:latest

# Vérifier
curl http://localhost:8000/health
```

### Option 3: Installation Directe (Sans Docker)

Pour développement local :

```bash
# Installation
pip install fish-speech

# Lancer le serveur
fish-speech-server --host 0.0.0.0 --port 8000

# Logs détaillés
fish-speech-server --host 0.0.0.0 --port 8000 --debug
```

---

## 🔧 Configuration

### Variables d'Environnement

Ajouter à `.env` :

```env
# ========== Fish-Speech ==========
FISH_SPEECH_URL=http://localhost:8000

# ========== TTS Fallback & Retry ==========
TTS_FALLBACK=true          # Enable XTTS v2 fallback
XTTS_DEVICE=auto           # auto/cuda/cpu
TTS_TIMEOUT=30             # Timeout in seconds
TTS_RETRIES=2              # Number of retry attempts
```

### Docker Compose - Configuration

Fichier [docker-compose.yml](docker-compose.yml), section `fish-speech`:

```yaml
fish-speech:
  image: fish-audio/fish-speech:latest
  container_name: fish-speech
  
  environment:
    LANG: fr_FR.UTF-8
    SERVICE_PORT: 8000
  
  volumes:
    - fish-speech-models:/app/models  # Persistent model cache
  
  ports:
    - "8000:8000"  # REST API
  
  deploy:
    resources:
      limits:
        cpus: '4'
        memory: 4G
  
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 60s
  
  restart: unless-stopped
```

---

## ✅ Vérifier l'Installation

### 1. Health Check

```bash
# Via curl
curl http://localhost:8000/health
# Doit retourner: 200 OK

# Via Python
python -c "
import requests
r = requests.get('http://localhost:8000/health')
print('✓ Fish-Speech running' if r.status_code == 200 else '✗ Not available')
"
```

### 2. Test Simple

```bash
# Générer audio de test
curl -X POST http://localhost:8000/v1/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Bonjour, ceci est un test.",
    "language": "fr",
    "speaker": 0
  }' \
  --output test.wav

# Vérifier fichier
ls -lh test.wav
# Doit être > 0 KB
```

### 3. Test via Pipeline

```bash
# Tester l'intégration E2E complète
python examples/test_e2e_pipeline.py

# Output attendu:
# ✅ STT: XXX ms
# ✅ LLM: XXX ms
# ✅ TTS: XXX ms
# ────
# ⌛ TOTAL E2E: ZZZ ms
```

---

## 🐛 Dépannage

### Problème: Connection refused (127.0.0.1:8000)

**Solution:**

1. Vérifier que Fish-Speech est lancé:
   ```bash
   docker ps | grep fish-speech
   # Ou: ps aux | grep fish-speech (sans Docker)
   ```

2. Si Docker, vérifier les logs:
   ```bash
   docker logs fish-speech
   ```

3. Lancer manuellement:
   ```bash
   # Docker
   docker run -d -p 8000:8000 fish-audio/fish-speech:latest
   
   # Sans Docker
   fish-speech-server --host 0.0.0.0 --port 8000
   ```

### Problème: Timeout ou TTS trop lent

**Solution:**

1. Vérifier ressources:
   ```bash
   # Docker
   docker stats fish-speech
   
   # Sans Docker
   nvidia-smi  # Si GPU disponible
   ```

2. Si GPU absent, TTS sera lent:
   - Utiliser fallback XTTS v2
   - Ou upgrader machine

### Problème: XTTS v2 Fallback échoue (TTS indisponible)

**Solution:**

1. Installer TTS (Coqui):
   ```bash
   pip install TTS soundfile
   ```

2. Précharger modèle:
   ```bash
   python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-speaker/xtts_v2', gpu=True)"
   ```

3. Vérifier .env:
   ```env
   TTS_FALLBACK=true
   XTTS_DEVICE=auto
   ```

### Problème: Qualité audio faible

**Solution:**

1. Paramètres Fish-Speech:
   ```json
   {
     "text": "Votre texte",
     "language": "fr",
     "speaker": 0,
     "speed": 1.0,
     "quality": "high"
   }
   ```

2. Vérifier modèle chargé (dernière version):
   ```bash
   docker pull fish-audio/fish-speech:latest
   docker-compose up --force-recreate fish-speech
   ```

---

## 📊 Benchmarking

### Mesurer Latence TTS

```bash
# Script benchmark
python examples/test_latency.py
# Affiche latences STT, TTS, E2E

# Output:
# TTS Latence: 250-350ms (typique)
# Objectif: <500ms E2E
```

### Profiler Performance

```bash
# Mode détaillé avec logs
export LOG_LEVEL=DEBUG
python examples/test_e2e_pipeline.py

# Voir breakdown:
# STT: 200ms
# LLM: 250ms
# TTS: 100ms (fast) ou 300ms (si fallback)
# Total: ~550ms
```

---

## 🔐 Sécurité (Production)

### Authentication

Si Fish-Speech exposé publiquement, ajouter authentification:

```yaml
# docker-compose.yml - avec reverse proxy
nginx:
  image: nginx:latest
  ports:
    - "443:443"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf
    - ./cert.pem:/etc/nginx/cert.pem
  depends_on:
    - fish-speech
```

### Rate Limiting

```bash
# docker-compose.yml - limiter appels
fish-speech:
  environment:
    - RATE_LIMIT=100/minute
```

---

## 📚 Références

- [Fish-Speech GitHub](https://github.com/fishaudio/fish-speech)
- [Fish-Speech Docker Hub](https://hub.docker.com/r/fish-audio/fish-speech)
- [XTTS v2 (Fallback)](https://github.com/coqui-ai/TTS)
- [Problèmes Connus](https://github.com/fishaudio/fish-speech/issues)

---

## 🎯 État du Déploiement

Checklist:

- [ ] Docker image Fish-Speech téléchargée
- [ ] Container lancé et healthy
- [ ] Health endpoint répond (200 OK)
- [ ] TTS génère audio valide
- [ ] Pipeline E2E teste succès (~500ms)
- [ ] Fallback XTTS v2 configurable
- [ ] Logs affichés correctement
- [ ] Retry logic active (2 tentatives)

