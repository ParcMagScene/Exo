# Docker Deployment Guide - Assistant Personnel

## 📋 Prérequis

### Sur Windows (WSL2)
```bash
# Installer Docker Desktop avec WSL2 backend
# https://docs.docker.com/desktop/install/windows-install/

# Vérifier l'installation
docker --version
docker-compose --version
```

### Sur Linux
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo usermod -aG docker $USER
newgrp docker
```

### Sur macOS
```bash
# Avec Homebrew
brew install --cask docker

# Ou télécharger Docker Desktop directement
# https://docs.docker.com/desktop/install/mac-install/
```

---

## 🚀 Démarrage Rapide

### 1. Préparer l'environnement

```bash
cd d:/Exo

# Copier le template de configuration
cp .env.example .env

# Éditer .env avec vos clés:
#   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
#   AZURE_OPENAI_KEY=your-api-key
#   HA_TOKEN=votre-token-homeassistant
```

**Variables essentielles dans `.env`:**
```env
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your-api-key

# Home Assistant (optionnel mais recommandé)
HA_TOKEN=your-homeassistant-token

# Timezone
TZ=Europe/Paris
```

### 2. Lancer les services

```bash
# Démarrer tous les services en arrière-plan
docker-compose up -d

# Visualiser les logs en temps réel
docker-compose logs -f assistant
```

### 3. Accéder aux services

| Service | Adresse | Port |
|---------|---------|------|
| **Wyoming Server** (audio) | localhost:10700 | 10700 |
| **Home Assistant** (domotique) | http://localhost:8123 | 8123 |
| **Fish-Speech TTS** (synthèse vocale) | http://localhost:8000 | 8000 |
| **Mopidy** (streaming musique) | http://localhost:6680 | 6680 |

---

## 📊 Gestion des Services

### Voir l'état
```bash
# Tous les services
docker-compose ps

# Logs filtrés
docker-compose logs -f --tail=50 assistant
docker-compose logs -f homeassistant
docker-compose logs -f fish-speech
```

### Arrêter/Redémarrer
```bash
# Arrêter tous les services (données persistées)
docker-compose down

# Redémarrer seulement un service
docker-compose restart assistant

# Arrêter complètement (supprimer aussi les volumes)
docker-compose down -v
```

### Rebuild l'image
```bash
# Reconstruire sans cache après modification du code
docker-compose build --no-cache

# Puis redémarrer
docker-compose up -d --force-recreate
```

---

## 🔧 Configuration Détaillée

### Wyoming Protocol (Audio)

Le serveur Wyoming écoute sur le port **10700**:

```python
# Configuration dans docker-compose.yml
ports:
  - "10700:10700"  # Wyoming

environment:
  - WYOMING_HOST=0.0.0.0
  - WYOMING_PORT=10700
```

**Connecter des Raspberry Pi:**
```bash
# Sur chaque Pi (voir PI_SETUP.md)
python examples/pi_satellite.py --host assistant --port 10700
```

### Home Assistant Integration

Home Assistant s'exécute dans le même docker-compose:

```bash
# Accéder à Home Assistant
http://localhost:8123

# Configurer l'intégration Wyoming:
# Settings → Devices & Services → Wyoming Protocol
# Ajouter serveur: assistant:10700
```

### Fish-Speech TTS

Pour utiliser la synthèse vocale:

```bash
# Health check
curl http://localhost:8000/

# Tester la synthèse vocale
curl -X POST http://localhost:8000/v1/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Bonjour, comment puis-je vous aider?",
    "language": "fr_FR"
  }'
```

---

## 📦 Architecture des Volumes

Les données persistantes sont stockées dans:

| Volume | Contenu | Persistance |
|--------|---------|-------------|
| `homeassistant_config` | Configuration Home Assistant | ✅ Oui |
| `fish-speech-models` | Modèles TTS pré-chargés | ✅ Oui |
| `chroma-db` | Base vectorielle RAG | ✅ Oui |
| `./data/chroma` | Cache ChromaDB local | ✅ Oui |
| `./assistant.log` | Logs application | ✅ Oui |

**Nettoyer les données:**
```bash
# Supprimer TOUS les volumes persistants
docker-compose down -v

# Ou supprimer un volume spécifique
docker volume rm exo_homeassistant_config
```

---

## 🐛 Dépannage

### Le service assistant ne démarre pas

```bash
# 1. Vérifier les logs
docker-compose logs assistant

# 2. Vérifier la configuration .env
cat .env | grep AZURE_OPENAI

# 3. Rebuild l'image (contenu modifié)
docker-compose build --no-cache assistant
docker-compose up -d
```

### Erreur "Cannot connect to Home Assistant"

```bash
# Home Assistant met 2-3 minutes à démarrer
docker-compose logs homeassistant | tail -20

# Attendre et vérifier la santé
docker-compose ps
# Status doit afficher "healthy"
```

### Fish-Speech timeout

```bash
# Fish-Speech a besoin de 60+ secondes pour charger les modèles
docker-compose logs fish-speech | tail -30

# Augmenter les ressources dans docker-compose.yml
# deploy:
#   resources:
#     limits:
#       cpus: '8'
#       memory: 8G
```

### Port déjà utilisé

```bash
# Si port 8123 est occupé (Home Assistant)
# Modifier docker-compose.yml:
ports:
  - "8124:8123"  # Forwards 8124 → 8123 dans container

# Puis accéder via http://localhost:8124
```

---

## 🧪 Testing

### Test du serveur Wyoming

```bash
# Sur votre PC, installer le client Wyoming
# pip install wyoming

# Tester la connexion
python -c "
from wyoming.client import WyomingClient
import asyncio

async def test():
    async with WyomingClient('localhost', 10700) as client:
        await client.ping()
        print('✅ Wyoming server responsive')

asyncio.run(test())
"
```

### Test de la conversation

```bash
# Depuis le PC (pas dans Docker)
python examples/demo_conversation.py

# Ou depuis le container
docker-compose exec assistant python examples/demo_conversation.py
```

### Test audio multi-room

```bash
# Depuis chaque Raspberry Pi (après installation)
python examples/pi_satellite.py --host assistant --port 10700

# Logs sur PC
docker-compose logs -f assistant | grep "Pi\|audio"
```

---

## 🌐 Réseau Docker

Les services communiquent via le réseau `assistant-net`:

```
┌─────────────────────────────────────┐
│   Docker Network: assistant-net     │
│                                     │
│  172.20.0.2: assistant (core)      │
│  172.20.0.3: homeassistant         │
│  172.20.0.4: fish-speech           │
│  172.20.0.5: mopidy                │
└─────────────────────────────────────┘
```

Chaque service peut accéder aux autres par nom d'hôte:
```python
# Depuis assistant, accéder à Home Assistant:
url = "http://homeassistant:8123"

# Depuis Pi satellite, accéder à assistant:
host = "assistant"  # DNS résolu automatiquement
port = 10700
```

---

## 📈 Monitoring

### Vérifier la santé des services

```bash
# Script de health check
docker-compose ps

# Output attendu:
# NAME               STATUS
# assistant-core     Up (healthy)
# homeassistant      Up (healthy)
# fish-speech        Up (healthy)
# mopidy             Up
```

### Metriques de performance

```bash
# Utilisation CPU/RAM
docker stats

# Détail par service
docker stats --no-stream

# Espace disque utilisé
docker system df
```

---

## 🔐 Production Checklist

Avant déploiement en production:

- [ ] ✅ Tous les services healthy (docker-compose ps)
- [ ] 🔑 Clés Azure OpenAI configurées et testées
- [ ] 🏠 Home Assistant intégré et fonctionnel
- [ ] 🎤 Pi satellites connectés au Wyoming server (voir PI_SETUP.md)
- [ ] 🔊 Fish-Speech TTS répondant sur :8000
- [ ] 📝 Logs configurés et rotate (voir requirements)
- [ ] 🚨 Health checks actifs sur tous les services
- [ ] 🔄 Redémarrage automatique (restart: unless-stopped)
- [ ] 💾 Volumes de persistance sur disque stable
- [ ] 🌐 Pare-feu configuré si accès distant

---

## 📚 Ressources

- **Wyoming Protocol**: [Documentation officielle](https://www.wyoming-protocol.com/)
- **Home Assistant**: [Docs](https://www.home-assistant.io/)
- **Fish-Speech**: [GitHub](https://github.com/fishaudio/fish-speech)
- **Docker Compose**: [Documentation](https://docs.docker.com/compose/)

---

## 🚀 Prochaines Étapes

Après configuration Docker réussie:

1. **Déploiement sur Raspberry Pi** (voir [PI_SETUP.md](PI_SETUP.md))
   ```bash
   # Les Pi vont se connecter au Wyoming server
   # par le réseau local
   ```

2. **Intégration domotique** via Home Assistant
   - Contrôle des lumières
   - Automation avec scenes
   - Notifications

3. **Optimisations** en production
   - Scaling horizontal (plusieurs assistants)
   - Load balancing pour Wyoming
   - Caching distribué (Redis)

4. **Monitoring & observabilité**
   - Prometheus pour métriques
   - ELK Stack pour logs centralisés
   - Grafana pour dashboards

---

**Questions?** Consultez les autres documentations:
- [README.md](README.md) - Vue d'ensemble
- [PI_SETUP.md](PI_SETUP.md) - Déploiement Raspberry Pi
- [ARCHITECTURE.md](ARCHITECTURE.md) - Architecture système
