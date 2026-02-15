# ⚡ Démarrage Rapide (5 min)

## Pour les impatients 🚀

### Prérequis

- Python 3.11+
- Les clés API Azure OpenAI et Home Assistant

### Installation Ultra-Rapide

```bash
# 1. Clone/Download
cd d:/Exo

# 2. Virtual env
python -m venv venv
venv\Scripts\activate  # Windows
# ou: source venv/bin/activate  # Linux/Mac

# 3. Installer
pip install -r requirements.txt

# 4. Config
copy .env.example .env
# ⚠️ ÉDITER .env : ajouter AZURE_OPENAI_ENDPOINT, clé, HA_URL, token

# 5. Lancer
python main.py
```

### Voilà ! 🎉

L'assistant devrait démarrer et afficher:
```
🚀 Assistant Personnel Haut de Gamme v1.0
==================================================
✅ Tous les modules initialisés avec succès
▶️ Démarrage de la boucle principale...
🎙️ Démarrage du traitement audio...
```

### Tester

Sur un Raspberry Pi (ou client test):
```bash
python examples/pi_satellite.py
```

L'assistant écoutera le audio du micro et traitera les commandes !

---

## Détails de Configuration

Besoin de config plus poussée ? Voir [SETUP.md](SETUP.md)

Besoin d'architecture ? Voir [ARCHITECTURE.md](ARCHITECTURE.md)

Questions ? → [README.md](README.md)
