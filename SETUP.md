# 📦 Installation & Déploiement

Guide complet pour installer EXO sur PC, Raspberry Pi et Docker.

---

## Table des matières

- [Prérequis](#-prérequis)
- [Installation PC](#1%EF%B8%8F⃣-installation-pc)
- [Raspberry Pi (satellites)](#2%EF%B8%8F⃣-raspberry-pi-satellites)
- [Docker](#3%EF%B8%8F⃣-docker)
- [Troubleshooting](#-troubleshooting)

---

## 🖥️ Prérequis

| Composant | Serveur PC | Satellite Pi |
|-----------|-----------|-------------|
| OS | Windows 10/11 ou Linux | Raspberry Pi OS (64-bit) |
| Python | 3.11+ | 3.9+ |
| RAM | 16 Go+ (48 Go recommandé) | 512 Mo+ |
| GPU | Optionnel (AMD/NVIDIA) | Non requis |
| Réseau | LAN | WiFi ou Ethernet |

---

## 1️⃣ Installation PC

### Cloner et configurer

```bash
git clone <repo-url> Exo
cd Exo

# Virtual env
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

# Dépendances
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

> **GPU NVIDIA** : `pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118`

### Configuration .env

```bash
copy .env.example .env          # Windows
# cp .env.example .env          # Linux
```

**Minimum requis** :

```env
OPENAI_API_KEY=sk-...
```

**Avec domotique** :

```env
OPENAI_API_KEY=sk-...
HA_URL=http://192.168.1.100:8123
HA_TOKEN=eyJ0eXAi...
```

Voir le [README.md](README.md#-variables-denvironnement) pour la liste complète.

### Configurer Home Assistant

1. Accéder à http://localhost:8123 — setup initial
2. Ajouter intégrations : Philips Hue, IKEA, Samsung, EZWIZ, Petkit
3. Créer token : Settings → Users → Profile → Long-lived access tokens
4. Copier dans `.env` : `HA_TOKEN=...`

### Obtenir clé OpenAI

1. https://platform.openai.com/api-keys
2. Créer une clé API
3. Copier dans `.env` : `OPENAI_API_KEY=sk-...`

Pour Azure OpenAI : https://portal.azure.com → Azure OpenAI Service → Keys and Endpoints

### Lancer

```bash
python main.py
```

```
🚀 Assistant Personnel Haut de Gamme v1.0
✅ Tous les modules initialisés avec succès
▶️ Démarrage de la boucle principale...
🎙️ Démarrage du traitement audio...
```

### Vérifier l'installation

```bash
python verify_installation.py
```

---

## 2️⃣ Raspberry Pi (satellites)

Déployer des microphones satellites qui envoient l'audio au serveur central via **Wyoming Protocol** (WebSocket + PCM16).

### Architecture multi-room

```
┌─ Serveur Central (PC)
│  ├─ WyomingServer (:10700)
│  └─ BrainEngine + TTS
│
├─ Pi 5 (Salon) ──────── ws://PC:10700
├─ Pi Zero 2W (Chambre) ── ws://PC:10700
└─ Pi Zero 2W (Cuisine) ── ws://PC:10700
```

### Préparer le Pi

```bash
# Mettre à jour
sudo apt update && sudo apt upgrade -y

# Dépendances système
sudo apt install -y python3 python3-pip python3-dev \
    portaudio19-dev libasound2-dev

# Dépendances Python
pip3 install --upgrade pip
pip3 install pyaudio websockets numpy

# Optionnel (STT local) :
pip3 install faster-whisper
```

### Vérifier le microphone

```bash
arecord -l                          # Lister les périphériques
arecord -c 1 -f S16_LE -r 16000 -d 3 test.wav  # Test 3s
aplay test.wav                      # Écouter
```

### Copier le code

```bash
# Depuis le PC :
scp examples/pi_satellite.py pi@pi-salon.local:~/assistant/

# Ou git clone sur le Pi :
git clone <repo-url> ~/assistant
```

### Lancer le client

```bash
python3 ~/assistant/pi_satellite.py \
  --server 192.168.1.50 \
  --port 10700 \
  --device-id pi-salon \
  --device-name "Salon Pi"
```

### Autostart (systemd)

```bash
sudo tee /etc/systemd/system/assistant-pi.service << EOF
[Unit]
Description=Assistant Wyoming Pi Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/assistant
ExecStart=/usr/bin/python3 /home/pi/assistant/pi_satellite.py \
  --server 192.168.1.50 --port 10700 \
  --device-id pi-salon --device-name "Salon Pi"
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable assistant-pi
sudo systemctl start assistant-pi

# Vérifier :
sudo journalctl -u assistant-pi -f
```

### IP statique (recommandé)

```bash
sudo nmtui
# ou éditer /etc/dhcpcd.conf :
# interface wlan0
# static ip_address=192.168.1.51/24
# static routers=192.168.1.1
```

### Optimisation par modèle

| Pi | WHISPER_MODEL | Chunk size | Workers |
|----|---------------|------------|---------|
| Zero 2W | tiny | 512 | 1 |
| Pi 5 | base | 2048 | 4 |

---

## 3️⃣ Docker

### Prérequis Docker

```bash
# Windows : Docker Desktop avec WSL2
# Linux :
sudo apt-get install -y docker.io docker-compose
sudo usermod -aG docker $USER

# Vérifier :
docker --version
docker-compose --version
```

### Lancer

```bash
cd d:/Exo
cp .env.example .env              # Configurer les clés
docker-compose up -d
```

### Services exposés

| Service | Port | Description |
|---------|------|-------------|
| Wyoming Server | 10700 | Audio multi-room |
| Home Assistant | 8123 | Domotique |
| Mopidy | 6680 | Streaming musique |

### Gestion

```bash
docker-compose ps                   # État des services
docker-compose logs -f assistant    # Logs temps réel
docker-compose restart assistant    # Redémarrer un service
docker-compose down                 # Arrêter tout
docker-compose down -v              # Arrêter + supprimer volumes
docker-compose build --no-cache     # Rebuild après modif code
```

### Volumes persistants

| Volume | Contenu |
|--------|---------|
| `homeassistant_config` | Config Home Assistant |
| `chroma-db` | Base vectorielle RAG |
| `./data/chroma` | Cache ChromaDB local |
| `./assistant.log` | Logs application |

### Réseau Docker

Les services communiquent via le réseau `assistant-net` par nom d'hôte :

```python
# Depuis assistant → Home Assistant :
url = "http://homeassistant:8123"

# Depuis Pi satellite → assistant :
host = "assistant"
port = 10700
```

### Connecter les Pi au Docker

```bash
# Sur chaque Pi :
python3 pi_satellite.py --server <IP-SERVEUR-DOCKER> --port 10700

# Dans HA : Settings → Devices → Wyoming Protocol → assistant:10700
```

### Monitoring

```bash
docker stats                        # CPU/RAM par service
docker system df                    # Espace disque
```

---

## 🔧 Troubleshooting

### Pas de clé API

```bash
# Vérifier .env
cat .env | grep OPENAI_API_KEY
# Doit contenir sk-...
```

### Home Assistant inaccessible

```bash
curl -I http://192.168.1.100:8123
curl -H "Authorization: Bearer $HA_TOKEN" http://192.168.1.100:8123/api/
# Doit retourner du JSON, pas 401
```

### Whisper ne charge pas

```bash
pip install --upgrade faster-whisper
python -c "from faster_whisper import WhisperModel; WhisperModel('base')"
```

### Microphone non détecté (Pi)

```bash
arecord -l
# Si vide : sudo raspi-config → Interface Options → Audio
sudo reboot
```

### Connexion Wyoming refusée

```bash
# Vérifier que le serveur tourne :
netstat -an | grep 10700
# Vérifier firewall :
sudo ufw allow 10700
# Tester ping :
ping 192.168.1.50
```

### Pygame crash

```bash
# Linux :
sudo apt install libsdl2-dev libsdl2-image-dev
# Windows/tous :
pip install --upgrade pygame
```

### GPU non détecté

```bash
python -c "import torch; print(torch.cuda.is_available())"
# Si False → utiliser DEVICE=cpu dans .env
```

### Docker : HA ne démarre pas

```bash
# HA met 2-3 min à démarrer
docker-compose logs homeassistant | tail -20
docker-compose ps   # Attendre status "healthy"
```
