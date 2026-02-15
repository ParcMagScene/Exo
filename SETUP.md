# 📚 Guide d'Installation Complète

## 🖥️ Système Requis

### Serveur Central (PC)
- **OS** : Windows 10/11 ou Linux (Ubuntu 20.04+)
- **CPU** : Intel i9-11900KF (ou équivalent)
- **RAM** : 48 Go recommandé
- **GPU** : AMD Radeon RX 6750 XT (optionnel mais recommandé)
- **Python** : 3.11+

### Satellites (Raspberry Pi)
- **Pi Zero 2 W** : STT
- **Pi 5** : STT + GUI optionnelle
- **Système** : Raspberry Pi OS (Bookworm)

### Domotique
- **Home Assistant** : v2024.1+ (contener Docker ou installation native)
- **Devices** : Philips Hue, IKEA, Samsung, EZWIZ, Petkit

## 1️⃣ Installation Serveur Central (PC)

### Étape 1 : Cloner le projet

```bash
git clone <repo-url> assistant
cd assistant
```

### Étape 2 : Environnement Python

#### Windows
```bash
# Créer virtualenv
python -m venv venv
venv\Scripts\activate

# Vérifier Python
python --version  # Doit afficher 3.11+
```

#### Linux/Mac
```bash
python3 -m venv venv
source venv/bin/activate
python3 --version
```

### Étape 3 : Installer les dépendances

```bash
# Upgrade pip/setuptools
pip install --upgrade pip setuptools wheel

# Installer dépendances
pip install -r requirements.txt
```

> **⚠️ Note GPU** : Pour CUDA (NVIDIA), ajouter :
> ```bash
> pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
> ```

### Étape 4 : Configuration (.env)

```bash
# Copier le fichier exemple
cp .env.example .env  # Linux/Mac
copy .env.example .env  # Windows

# Éditer avec votre éditeur
```

**Remplir au minimum** :
```env
# Azure OpenAI (obligatoire)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=sk-...
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Home Assistant
HA_URL=http://192.168.1.100:8123  # Adapter à votre réseau
HA_TOKEN=eyJ0eXAi...              # Long-lived token HA
```

### Étape 5 : Setup Home Assistant

#### Option A : Docker (Recommandé)
```bash
docker run -d \
  --name homeassistant \
  -p 8123:8123 \
  -v /path/to/config:/config \
  ghcr.io/home-assistant/home-assistant:latest
```

Puis acceder à http://localhost:8123 et suivre l'assistant.

#### Option B : Installation Native
```bash
pip install homeassistant
hass --config /path/to/config --open-ui
```

### Étape 6 : Configurer Home Assistant

1. Aller à http://localhost:8123
2. Setup initial (user, localisation, etc.)
3. Ajouter intégrations :
   - Philips Hue : Settings > Devices > Add integration > Hue
   - IKEA : Add integration > IKEA Dirigera
   - Samsung : Add integration > Samsung TV
   - EZWIZ : Add integration > EZviz
   - Petkit : Add integration > Petkit

4. Créer token long-lived :
   - Settings > Users > Profile > Tokens
   - Copier dans .env : `HA_TOKEN=...`

### Étape 7 : Obtenir clés API Azure

1. Créer compte Azure : https://portal.azure.com
2. Créer ressource "Azure OpenAI"
3. Déployer modèle GPT-4o
4. Copier endpoint + key dans .env

## 2️⃣ Installation Raspberry Pi

### Pi Zero 2 W / Pi 5

#### Étape 1 : Préparation OS
```bash
# Mettre à jour
sudo apt update && sudo apt upgrade -y

# Installer dépendances système
sudo apt install -y python3.11 python3-pip python3-venv \
    libopenblas0 libatlas-base-dev libjasper-dev \
    libtiff5 libjasper1 libharfbuzz0b libwebp6 \
    libopenjp2-7 libpython3-dev
```

#### Étape 2 : Client Wyoming

```bash
# Créer répertoire
mkdir -p ~/assistant && cd ~/assistant

# Virtual env
python3 -m venv venv
source venv/bin/activate

# Installation Whisper + Wyoming
pip install faster-whisper --no-cache-dir
pip install websockets pyaudio numpy

# Télécharger le client exemple
wget https://repo/examples/pi_satellite.py
```

#### Étape 3 : Lancer le client

```bash
# Adapter l'IP du serveur central
export ASSISTANT_SERVER="ws://192.168.1.100:10700"
export PI_ROOM="pi_zero"  # ou "pi_5"

# Lancer
python3 pi_satellite.py
```

Pour démarrage auto (systemd) :

```bash
# Créer service
sudo tee /etc/systemd/system/assistant-pi.service << EOF
[Unit]
Description=Assistant Wyoming Client
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/pi/assistant
ExecStart=/home/pi/assistant/venv/bin/python3 pi_satellite.py
Environment="ASSISTANT_SERVER=ws://192.168.1.100:10700"
Environment="PI_ROOM=pi_zero"
User=pi
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Activer
sudo systemctl enable assistant-pi.service
sudo systemctl start assistant-pi.service

# Vérifier logs
sudo journalctl -u assistant-pi.service -f
```

## 3️⃣ Lancer l'Assistant

### Serveur Central

```bash
# Activer venv (si pas encore fait)
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate      # Windows

# Lancer l'application
python main.py
```

Attendez les logs :
```
🚀 Assistant Personnel Haut de Gamme v1.0
==================================================
✅ Tous les modules initialisés avec succès
▶️ Démarrage de la boucle principale...
🎙️ Démarrage du traitement audio...
```

## 4️⃣ Tests & Vérification

### Test 1 : Connectivité Wyoming

```bash
# Pi Zero (ou test local)
python examples/pi_satellite.py

# Serveur - vérifier logs : "Client Wyoming connecté"
```

### Test 2 : Performance

```bash
# Sur le serveur
python examples/test_performance.py

# Résultat attendu : E2E total < 500ms
```

### Test 3 : Home Assistant

```bash
# Tester l'API HA
curl -H "Authorization: Bearer $HA_TOKEN" \
     http://localhost:8123/api/states

# Doit retourner la liste des entités
```

### Test 4 : LLM

Dire (via micro Pi) : "Allume la lumière du salon"
→ Doit voir dans les logs : fonction `control_light()` appelée

## 🔧 Troubleshooting

### "AZURE_OPENAI_ENDPOINT requis"
```bash
# Vérifier .env existe
ls -la .env

# Vérifier contenu (ne pas montrer la clé!)
cat .env | grep AZURE
```

### "Connexion HA échouée"
```bash
# Vérifier HA accessible
curl -I http://192.168.1.100:8123

# Vérifier token
curl -H "Authorization: Bearer $HA_TOKEN" \
     http://192.168.1.100:8123/api/

# Doit retourner un JSON, pas 401 Unauthorized
```

### "Whisper pas disponible"
```bash
# Réinstaller
pip install --upgrade faster-whisper

# Télécharger modèle
python -c "import faster_whisper; faster_whisper.WhisperModel('base')"
```

### "GPU non détecté"
```bash
# Vérifier CUDA disponible
python -c "import torch; print(torch.cuda.is_available())"

# Si False, utiliser CPU
export DEVICE=cpu
```

### "Pygame crash"
```bash
# Réinstaller SDL
sudo apt install libsdl2-dev libsdl2-image-dev  # Linux

# Ou sur Windows : pip install pygame-pygame
pip install --upgrade pygame
```

## 📊 Vérifier Installation

```bash
# Script de vérification
python << 'EOF'
import os
import sys

checks = {
    "Python 3.11+": sys.version_info >= (3, 11),
    "Azure SDK": __import__("importlib.util").util.find_spec("azure.ai.openai") is not None,
    "ChromaDB": __import__("importlib.util").util.find_spec("chromadb") is not None,
    "Faster-Whisper": __import__("importlib.util").util.find_spec("faster_whisper") is not None,
    "Pygame": __import__("importlib.util").util.find_spec("pygame") is not None,
    ".env file": os.path.exists(".env"),
}

print("✅ Installation Check\n")
for check, result in checks.items():
    symbol = "✅" if result else "❌"
    print(f"{symbol} {check}")

if all(checks.values()):
    print("\n✨ Installation réussie!")
else:
    print("\n⚠️  Dépendances manquantes - relancer pip install -r requirements.txt")
EOF
```

## 🚀 Prochaines Étapes

1. **Ajouter des animaux** à la mémoire :
   ```bash
   curl -X POST http://localhost:8000/api/memory \
        -H "Content-Type: application/json" \
        -d '{"category": "animal", "content": "Felix est un chat noir"}'
   ```

2. **Tester commandes vocales** :
   - "Allume le salon"
   - "Quelle est la température?"
   - "Mets TIDAL, du Indie"

3. **Optimiser latence** selon mesures de `test_performance.py`

## 📞 Support

Consulter les logs :
```bash
tail -f assistant.log
```

Vérifier ARCHITECTURE.md pour flux détaillé.
