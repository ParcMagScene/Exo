# 🍓 Déploiement Raspberry Pi - Wyoming Protocol

## Vue d'ensemble

Déployer l'assistant sur plusieurs Raspberry Pi satellites qui envoient l'audio au serveur central via le **Wyoming Protocol** (WebSocket + PCM16).

**Status:** ✅ **CLIENT IMPLÉMENTÉ**

## Architecture Multi-Room

```
┌─────────────────────────────────┐
│  SERVEUR CENTRAL (PC Intel i9)  │
│  - WyomingServer (port 10700)   │
│  - BrainEngine (GPT-4o)         │
│  - HomeAssistant Bridge         │
│  - GUI Pygame                   │
└────────────┬────────────────────┘
             │ Wyoming WebSocket
    ┌────────┼────────┬────────────┐
    │        │        │            │
    ▼        ▼        ▼            ▼
┌──────┐ ┌──────┐ ┌──────┐  ┌──────────┐
│ Pi 1 │ │ Pi 2 │ │ Pi 3 │  │ Pi Zero  │
│Salon │ │Chmb  │ │Cuis  │  │2W Entrée │
└──────┘ └──────┘ └──────┘  └──────────┘
```

## Étape 1: Préparation Pi (Une fois)

### Installation OS
```bash
# Sur SD Card (32GB minimum recommandé)
# Utiliser Raspberry Pi Imager
# - OS: Raspberry Pi OS (64-bit)
# - Host: `pi-salon`, `pi-chambre`, etc.
# - Enable SSH
# - Set WiFi credentials
```

### SSH depuis PC
```bash
# Remplacer pi-salon par votre hostname
ssh pi@pi-salon.local

# Password: raspberry (par défaut)
# À changer: passwd
```

### Fixer IPv4 (recommandé)
```bash
# Sur le Pi:
sudo nmtui
# ou éditer /etc/dhcpcd.conf

# Configuration statique (exemple):
interface wlan0
static ip_address=192.168.1.51/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8
```

## Étape 2: Installation Dépendances Pi

### Installer Python + PIP
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-dev

# Vérifier version
python3 --version  # Doit être 3.9+
```

### Installer PyAudio (système)
```bash
# Dépendances système
sudo apt install -y portaudio19-dev libasound2-dev

# Installer PyAudio
pip3 install --upgrade pip
pip3 install pyaudio
```

### Installer dépendances Python
```bash
pip3 install websockets numpy

# Optionnel (STT local sur Pi):
pip3 install faster-whisper
```

### Vérifier microphone
```bash
# Lister périphériques
arecord -l

# Test enregistrement (3 secondes)
arecord -c 1 -f S16_LE -r 16000 -d 3 test.wav
aplay test.wav  # Écouter
```

## Étape 3: Copier Code Assistant sur Pi

### Via SCP depuis PC
```bash
# D:\Exo> sur Windows PowerShell:
scp -r src/ pi@pi-salon.local:~/assistant/
scp examples/pi_satellite.py pi@pi-salon.local:~/assistant/
```

### Ou Git Clone
```bash
# Sur le Pi:
cd ~
git clone <votre-repo-url>
cd assistant
```

## Étape 4: Lancer Client Wyoming

### Test Connexion
```bash
# Sur Pi, tester connexion au serveur:
# (Remplacer 192.168.1.50 par IP serveur central)

python3 examples/pi_satellite.py \
  --server 192.168.1.50 \
  --port 10700 \
  --device-id pi-salon \
  --device-name "Salon Pi"
```

**Expected output:**
```
🚀 WYOMING PI CLIENT - Salon Pi
✅ Audio capture prêt (16000Hz, 1 canal)
🔌 Connexion à ws://192.168.1.50:10700...
✅ Connecté au serveur Wyoming
🚀 Session démarrée: pi-salon-1707...
🎤 Enregistrement en cours (30s)...
```

### Autostart au Démarrage (systémd)

Créer `/home/pi/assistant/run.sh`:
```bash
#!/bin/bash
cd /home/pi/assistant
python3 examples/pi_satellite.py \
  --server 192.168.1.50 \
  --port 10700 \
  --device-id pi-salon \
  --device-name "Salon Pi" \
  --duration 3600  # 1 heure
```

Permissions:
```bash
chmod +x /home/pi/assistant/run.sh
```

Créer systemd service `/etc/systemd/system/assistant-pi.service`:
```ini
[Unit]
Description=Assistant Wyoming Pi Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/assistant
ExecStart=/home/pi/assistant/run.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable assistant-pi
sudo systemctl start assistant-pi
sudo systemctl status assistant-pi

# Logs:
sudo journalctl -u assistant-pi -f
```

## Étape 5: Configuration Multi-Pi

Pour chaque Pi, adapter:
- `--device-id`: ID unique (pi-salon, pi-chambre, pi-cuisine)
- `--device-name`: Nom affichable
- `--server`: IP serveur central (discovery possible via mDNS)

**Exemple - 3 Pi:**
```bash
# Pi 1 (Salon)
python3 examples/pi_satellite.py --device-id pi-salon --server 192.168.1.50

# Pi 2 (Chambre)
python3 examples/pi_satellite.py --device-id pi-chambre --server 192.168.1.50

# Pi 3 (Cuisine)
python3 examples/pi_satellite.py --device-id pi-cuisine --server 192.168.1.50
```

## Étape 6: Vérifier sur Serveur Central

### Lancer Wyoming Server
```bash
python3 main.py
# Ou directement:
python3 -c "
from src.protocols.wyoming import WyomingServer
import asyncio
server = WyomingServer()
asyncio.run(server.start())
"
```

### Vérifier connexions Pi
```bash
netstat -an | grep 10700
# Output:
# LISTENING 0.0.0.0:10700
```

### Logs serveur
```bash
# Dans output du serveur:
# ✅ Client connecté: pi-salon (192.168.1.51:xxxxx)
# 📤 Audio frame reçu: pi-salon, 1024 bytes
```

## Optimisation Performance

### Pi Zero 2W (limité)
```bash
# Moins de workers, modèle STT petit
export DEVICE=cpu
export WHISPER_WORKERS=1
export WHISPER_MODEL=tiny  # tiny.en pour performance

# Reduced resolution
python3 examples/pi_satellite.py --chunk-size 512
```

### Pi 5 (plus puissant)
```bash
export DEVICE=auto
export WHISPER_WORKERS=4
export WHISPER_MODEL=base  # Plus d'acurité

python3 examples/pi_satellite.py --chunk-size 2048
```

## Dépannage

### "Connection refused"
```bash
# Vérifier serveur Wyoming lancé:
ps aux | grep main.py
netstat -an | grep 10700

# Vérifier firewall:
sudo ufw allow 10700
```

### "Microphone not found"
```bash
# Vérifier micro:
arecord -l
# Si vide, activer dans raspi-config:
sudo raspi-config
# Select: 3 Interface Options → P5 Audio

# Re-boot:
sudo reboot
```

### "WebSocket timeout"
```bash
# Vérifier IP serveur:
ping 192.168.1.50

# Vérifier routage:
traceroute 192.168.1.50

# Essayer avec hostname si possible:
python3 examples/pi_satellite.py --server assistant.local
```

### Latence audio élevée
```bash
# Réduire chunk size:
python3 examples/pi_satellite.py --chunk-size 512

# Vérifier WiFi signal:
iwconfig wlan0
# Signal level=-40 dBm: Bon
# Signal level=-70 dBm: Passable
# Signal level=-90 dBm: Mauvais → Utiliser filaire si possible
```

## Monitoring

### Ressources Pi
```bash
# Température:
vcgencmd measure_temp

# Utilisation RAM:
free -h

# CPU:
top

# Network:
iftop
```

### Distance Serveur ↔ Pi
```bash
# Mesurer ping:
ping -c 10 192.168.1.50
# Chercher RTT proche de 1-5ms sur WiFi

# Iperf test:
# Serveur: iperf3 -s
# Pi:      iperf3 -c 192.168.1.50
```

## Architecture Wyoming Protocol

**Format Message:**
```
┌─────────────┬──────┬─────────────────┐
│ JSON Header │ NULL │ PCM16 Audio     │
│ (variable)  │ 0x00 │ Data (variable) │
└─────────────┴──────┴─────────────────┘

Exemple:
{"type":"audio_frame","session_id":"pi-salon-170...","timestamp":1707...}\0[binary PCM16]
```

**Handshake:**
```
Pi → Server: {"type":"audio_start","device_id":"pi-salon",...}
Server → Pi: {"type":"ready"}
Pi → Server: [audio frames] (multiples)
Pi → Server: {"type":"audio_stop","frames_sent":1000}
```

## Multi-Client Gestion

Le serveur Wyoming (`src/protocols/wyoming.py`) gère:
- ✅ Clients multiples simultanés
- ✅ Identification par device_id + session_id
- ✅ Priority queue (qui parle dans quelle pièce)
- ✅ Context routing (réponse → bonne pièce)

## Prochaines Étapes

1. **Installer OS Pi Zero 2W + Pi 5**
2. **Tester SSH connexion**
3. **Installer PyAudio + dépendances**
4. **Lancer test client**: `python3 examples/pi_satellite.py --server <PC-IP>`
5. **Vérifier périphériques audio**: `arecord -l`
6. **Configurer autostart systemd**
7. **Déployer sur tous les Pi**
8. **Tester conversations multi-room**

## Architecture Recommandée

```
┌─ PC Central (i9-11900KF)
│  ├─ main.py (orchestrateur)
│  ├─ WyomingServer (:10700)
│  ├─ BrainEngine (GPT-4o + RAG)
│  └─ GUI Pygame
│
├─ Pi 5 (Salon) - Audio 48kHz
│  ├─ Microphone Haut de Gamme
│  └─ Speakers/Amplificateur
│
├─ Pi Zero 2W (Chambre) - Compact
│  └─ Microphone intégré
│
└─ Pi Zero 2W (Cuisine) - Minimal
   └─ USB Microphone
```

---

**✅ Prêt pour déploiement multi-room!**
