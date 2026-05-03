# Rapport d'audit — Installation CosyVoice2 dans EXO

**Date :** 2026-05-09  
**Auteur :** GitHub Copilot (session de correction automatisée)  
**Portée :** TTS microservice, package cosyvoice, moteur d'inférence, configuration voix

---

## 1. Analyse de l'installation actuelle

### 1.1 Dossier modèles

| Chemin | Statut |
|--------|--------|
| `D:\EXO\models\cosyvoice\` | ✅ Présent |
| `D:\EXO\CosyVoice\` (ancien clone Python) | ❌ Absent |

**Fichiers modèles présents dans `D:\EXO\models\cosyvoice\` :**

| Fichier | Taille | Rôle |
|---------|--------|------|
| `llm.pt` | ~200 MB | LLM (Qwen2-based) pour token speech |
| `flow.pt` | ~450 MB | Flow matching (décodeur speech) |
| `flow.cache.pt` | ~450 MB | Cache pré-compilé du flow |
| `hift.pt` | ~83 MB | HiFi-GAN vocoder (PCM 24 kHz) |
| `campplus.onnx` | ~28 MB | Speaker encoder |
| `speech_tokenizer_v2.onnx` | ~50 MB | Tokenizer speech |
| `speech_tokenizer_v2.batch.onnx` | ~50 MB | Tokenizer speech (batch) |
| `flow.decoder.estimator.fp32.onnx` | ~29 MB | Estimateur flow ONNX |
| `cosyvoice2.yaml` | 7 KB | Configuration modèle |
| `config.json` | 2 B | Métadonnées modèle |
| `CosyVoice-BlankEN/` | ~100 MB | Tokenizer BPE (GPT-2) |
| `voices/fr_*.wav` | 5 fichiers | Prompts voix FR (Denise, Éloïse, Henri, Rémy, Vivienne) |
| `voices/voices_metadata.json` | 1.5 KB | Métadonnées voix |
| `prompt.wav` | 285 KB | Prompt voix legacy (fallback) |

### 1.2 État du venv Python `.venv_stt_tts`

| Package | Avant correction | Après correction |
|---------|-----------------|-----------------|
| `cosyvoice` | ❌ `ModuleNotFoundError` | ✅ v2.0.0 installé |
| `matcha-tts` | ❌ Absent | ✅ v0.1.0 installé |
| `torch` | ✅ 2.7.0+cu128 | ✅ inchangé |
| `transformers` | ✅ présent | ✅ inchangé |
| `modelscope` | ✅ 1.35.3 | ✅ inchangé |
| `wetext` | ✅ 0.0.4 | ✅ inchangé |
| `onnxruntime-directml` | ✅ présent | ✅ inchangé |

---

## 2. Erreurs détectées

### 2.1 Erreur critique — Package cosyvoice absent

```
ModuleNotFoundError: No module named 'cosyvoice'
```

**Cause :** Le package Python `cosyvoice` n'était pas installé dans `.venv_stt_tts`. Le code source est distribué depuis GitHub ([FunAudioLLM/CosyVoice](https://github.com/FunAudioLLM/CosyVoice)) sans être publié sur PyPI. Il requiert un `pip install -e` depuis un clone local.

### 2.2 Erreur critique — Fallback COSYVOICE_ROOT vers répertoire inexistant

**Fichier :** `python/tts/cosyvoice_engine.py` (lignes 113–129, avant correction)  
**Code erroné :**
```python
cosyvoice_root = os.environ.get("COSYVOICE_ROOT", r"D:\EXO\CosyVoice")
matcha_path = os.path.join(cosyvoice_root, "third_party", "Matcha-TTS")
for p in (cosyvoice_root, matcha_path):
    if os.path.isdir(p):
        site.addsitedir(p)
```
**Cause :** Le répertoire `D:\EXO\CosyVoice` a été supprimé lors d'une réorganisation antérieure. Le fallback silencieux ne déclenchait pas d'erreur visible mais ne résolvait pas l'import.

### 2.3 Erreur secondaire — Voice par défaut incorrecte

**Fichier :** `config/assistant.conf`  
`voice=fr_denise` → la voix de référence opérationnelle spécifiée est `fr_vivienne`.

---

## 3. Corrections appliquées

### 3.1 Installation du package cosyvoice

```powershell
# Cloner CosyVoice avec ses sous-modules
git clone --depth=1 --recurse-submodules https://github.com/FunAudioLLM/CosyVoice.git C:\temp\cosyvoice_install

# Créer les __init__.py manquants dans les sous-modules sans en-tête standard
# (llm, flow, hifigan, tokenizer, vllm, bin)
foreach ($mod in @("llm","flow","hifigan","tokenizer","vllm","bin")) {
    New-Item "C:\temp\cosyvoice_install\cosyvoice\$mod\__init__.py" -Force
}

# Installer Matcha-TTS (dépendance interne)
python -m pip install "C:\temp\cosyvoice_install\third_party\Matcha-TTS" --no-deps

# Installer cosyvoice
python -m pip install "C:\temp\cosyvoice_install" --no-deps
```

**Résultat :**
```
Successfully installed matcha-tts-0.1.0
Successfully installed cosyvoice-2.0.0
```

**Vérification de l'import :**
```python
from cosyvoice.cli.cosyvoice import CosyVoice2  # ✅ OK
from cosyvoice.llm.llm import Qwen2LM           # ✅ OK
from tts.cosyvoice_engine import CosyVoiceEngine # ✅ OK
```

### 3.2 Nettoyage du fallback COSYVOICE_ROOT

**Fichier :** `python/tts/cosyvoice_engine.py`

Avant :
```python
try:
    from cosyvoice.cli.cosyvoice import CosyVoice2 as _CosyVoice2
except Exception:
    import site
    cosyvoice_root = os.environ.get("COSYVOICE_ROOT", r"D:\EXO\CosyVoice")
    matcha_path = os.path.join(cosyvoice_root, "third_party", "Matcha-TTS")
    for p in (cosyvoice_root, matcha_path):
        if os.path.isdir(p):
            site.addsitedir(p)
    try:
        from cosyvoice.cli.cosyvoice import CosyVoice2 as _CosyVoice2
    except Exception as exc:
        raise RuntimeError("CosyVoice package unavailable. Install it ...") from exc
```

Après :
```python
try:
    from cosyvoice.cli.cosyvoice import CosyVoice2 as _CosyVoice2
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "CosyVoice package not found in the active Python environment. "
        "Install it with: python -m pip install <path-to-CosyVoice-clone> --no-deps"
    ) from exc
```

### 3.3 Correction de la voix par défaut

**Fichier :** `config/assistant.conf`

```ini
[TTS]
# Avant
voice=fr_denise

# Après
voice=fr_vivienne
```

---

## 4. Fichiers modifiés

| Fichier | Modification |
|---------|-------------|
| `python/tts/cosyvoice_engine.py` | Suppression du fallback `site.addsitedir` vers `D:\EXO\CosyVoice` |
| `config/assistant.conf` | `voice=fr_denise` → `voice=fr_vivienne` |
| `.venv_stt_tts` | Packages `cosyvoice==2.0.0` et `matcha-tts==0.1.0` installés |

---

## 5. Vérification TTS server

### 5.1 État du processus

Au moment de l'audit, le TTS server (port 8767, PID 33636) tourne depuis le **01/05/2026 07:25:45** — antérieur à la correction du package cosyvoice. Ce processus a démarré avec le fallback cassé et n'a pas pu charger le modèle CosyVoice2.

**Action requise :** redémarrer le service TTS pour charger les corrections :
```powershell
# Via VS Code Tasks : Ctrl+Shift+P → "Run Task" → "tts_server"
# Ou en ligne de commande :
Stop-Process -Id 33636
& "D:\EXO\project\.venv_stt_tts\Scripts\python.exe" `
    "D:\EXO\project\python\tts\tts_server.py" `
    --lang fr --streaming --chunk-size 16000 --max-chunk-length 2048 --latency-optimized
```

### 5.2 Séquence de démarrage attendue (après redémarrage)

```
[TTS] Service tts_server initializing on port 8767
[TTS] Loading CosyVoice2-0.5B from D:\EXO\models\cosyvoice on cuda:0 …
[TTS] CosyVoice2-0.5B loaded in ~XXXX ms
[TTS] Voice prompt discovered: fr_vivienne → fr_vivienne.wav
[TTS] Voice prompt discovered: fr_denise → fr_denise.wav
[TTS] [Readiness] Phase → ready
```

---

## 6. Vérification pipeline vocal

### 6.1 Architecture du pipeline

```
tts_server.py (WS :8767)
  └── CosyVoiceEngine
        ├── CosyVoice2 (cli/cosyvoice.py)
        │     ├── LLM : llm.pt (Qwen2-0.5B)
        │     ├── Flow : flow.pt + flow.cache.pt
        │     ├── HiFi-GAN : hift.pt (24 kHz)
        │     └── Speaker encoder : campplus.onnx
        └── Voice prompts : voices/fr_vivienne.wav (défaut)
```

### 6.2 Mode d'inférence

Le moteur utilise le mode **zero-shot voice cloning** : le fichier WAV de la voix sélectionnée sert de prompt speaker. Toutes les voix FR disponibles sont pré-enregistrées au démarrage via `model.add_zero_shot_spk()`.

### 6.3 Paramètres de sortie

| Paramètre | Valeur |
|-----------|--------|
| Sample rate | 24 000 Hz |
| Format | PCM16 (signed 16-bit) |
| Streaming | Oui — chunks de 16 000 échantillons (~667 ms) |
| Max chunk length | 2 048 caractères |
| Latency-optimized | Oui |

---

## 7. Qualité des voix installées

Cinq voix françaises sont disponibles dans `D:\EXO\models\cosyvoice\voices\` :

| ID | Fichier | Taille WAV | Description (metadata) |
|----|---------|-----------|------------------------|
| `fr_vivienne` | `fr_vivienne.wav` | 323 KB | Voix féminine — défaut actuel |
| `fr_denise` | `fr_denise.wav` | 437 KB | Voix féminine — ancienne défaut |
| `fr_eloise` | `fr_eloise.wav` | 455 KB | Voix féminine |
| `fr_henri` | `fr_henri.wav` | 467 KB | Voix masculine |
| `fr_remy` | `fr_remy.wav` | 345 KB | Voix masculine |

La sélection de voix est dynamique : `set_voice("fr_henri")` bascule vers le speaker embedding correspondant sans rechargement du modèle.

---

## 8. Risques résiduels

| Risque | Sévérité | Mitigation |
|--------|----------|------------|
| Clone cosyvoice dans `C:\temp\` | Moyen — dossier temp susceptible d'être vidé | Déplacer vers `D:\EXO\project\cosyvoice_src\` et réinstaller, ou committer les wheels dans un dossier dédié |
| `matcha-tts` setup.py généré manuellement | Faible | Le `pyproject.toml` d'origine est bien présent — l'installation a utilisé les deux |
| FutureWarning `TRANSFORMERS_CACHE` | Faible — ne bloque pas | Ajouter `HF_HOME=D:\EXO\cache\huggingface` dans l'env du task `tts_server` |
| Sous-modules cosyvoice sans `__init__.py` | Faible | Les `__init__.py` ont été créés manuellement et sont inclus dans la wheel installée |
| TTS server non redémarré | Critique (actif) | Redémarrer manuellement le service `tts_server` |

---

## 9. Prochaines étapes

1. **Immédiat** — Redémarrer le service TTS (voir §5.1). Valider dans les logs la présence de `Phase → ready` et `fr_vivienne loaded`.

2. **Court terme** — Déplacer le clone CosyVoice vers un emplacement permanent :
   ```powershell
   Move-Item C:\temp\cosyvoice_install D:\EXO\project\cosyvoice_src
   & "D:\EXO\project\.venv_stt_tts\Scripts\python.exe" -m pip install "D:\EXO\project\cosyvoice_src" --no-deps
   ```

3. **Court terme** — Ajouter `HF_HOME` dans la task VS Code `tts_server` :
   ```json
   "env": {
       "PYTHONPATH": "${workspaceFolder}/python",
       "HF_HOME": "D:\\EXO\\cache\\huggingface",
       "EXO_COSYVOICE_MODELS": "D:\\EXO\\models\\cosyvoice"
   }
   ```

4. **Optionnel** — Tester un rendu TTS complet avec `test_tts_client.py` après redémarrage.

5. **Optionnel** — Si la latence premier chunk dépasse 1 s sur RTX 3070 : basculer sur le modèle CosyVoice2-0.25B en changeant `EXO_COSYVOICE_MODELS`.
