# TTS Voices Fix — CosyVoice2 multi-voice GUI

**Composants affectés :** `cosyvoice_engine.py` · `VoicePipeline.cpp`  
**Priorité :** P1 (bloquant — la GUI n'affichait qu'une seule voix)  
**Statut :** ✅ Corrigé + recompilé

---

## Symptôme

Le ComboBox "Voix TTS" de la page Paramètres n'affichait que `["fr_denise"]` (valeur de
repli statique), quel que soit le nombre de fichiers `.wav` présents dans
`D:\EXO\models\cosyvoice\voices\`.

---

## Cause racine 1 — Python : `list_voices()` ne retournait que les speakers SFT

**Fichier :** `python/tts/cosyvoice_engine.py`

### Explication

`list_voices()` retournait `sorted(self._available_spks)`. Ce champ était initialisé
uniquement depuis `model.list_available_spks()`, qui ne liste que les speakers **SFT**
(pré-entraînés dans le checkpoint du modèle). Or, CosyVoice2-0.5B ne contient aucun
speaker SFT natif : le résultat était donc `[]`.

Les voix zéro-shot enregistrées via `add_zero_shot_spk()` (fr_vivienne, fr_remy,
fr_denise, fr_henri, fr_eloise) sont stockées dans un dict interne de CosyVoice2
(`_zero_shot_spk`) qui **ne remonte pas** dans `list_available_spks()`.

### Chaîne de conséquences

```
list_voices() = []
  → tts_server.py: {"type": "voices", "available": []}
  → TTSManager.cpp: m_ttsVoices = QStringList()
  → VoicePipeline::ttsVoices() = QStringList()
  → QML model.length == 0
  → fallback: model = ["fr_denise"]   ← GUI bloquée ici
```

### Corrections appliquées

#### A. `list_voices()` — fusion de toutes les sources

```python
# AVANT
def list_voices(self) -> list[str]:
    return sorted(self._available_spks)

# APRÈS
def list_voices(self) -> list[str]:
    all_voices: set[str] = set(self._available_spks)
    vp = getattr(self, "_voice_prompts", {})
    all_voices.update(vp.keys())                        # ← 5 voix FR ajoutées
    if self._prompt_wav and os.path.isfile(self._prompt_wav):
        all_voices.add("exo_default")
    return sorted(all_voices)
```

#### B. Reconstruction de `_available_spks` après chargement

Dans `load()`, après toutes les registrations `add_zero_shot_spk()` :

```python
# AVANT
self._available_spks = self.model.list_available_spks()

# APRÈS
sft_spks = []
try:
    sft_spks = self.model.list_available_spks()
except Exception:
    logger.warning("Failed to list SFT speakers", exc_info=True)

registered = set(sft_spks) | set(self._voice_prompts.keys())
if self._prompt_wav and os.path.isfile(self._prompt_wav):
    registered.add("exo_default")
self._available_spks = sorted(registered)
```

#### C. `_inference_internal()` — branche pour voix hors SFT list

Avant ce correctif, si une voix était dans `_voice_prompts` mais **absente** de
`_available_spks`, l'inférence tombait sur le fallback `self._prompt_wav` au lieu
d'utiliser le `.wav` propre à la voix. Branche ajoutée :

```python
elif self.voice_name in vp:
    # Voice in _voice_prompts but NOT in model's internal SFT dict
    yield from self.model.inference_cross_lingual(
        tts_text=text,
        prompt_wav=vp[self.voice_name]["wav"],
        stream=stream,
        speed=speed,
    )
```

#### D. `infer_stream()` — même correctif de branche

Identique à `_inference_internal()` : branche `elif speaker_id in vp` ajoutée avant
le fallback `_prompt_wav`.

#### E. `set_voice()` — accepter les voix de `_voice_prompts` sans SFT check

```python
# Branche ajoutée après le check _available_spks
if voice in vp:
    self.voice_name = voice
    self._prompt_wav = vp[voice]["wav"]
    return True
```

---

## Cause racine 2 — C++ : `VoicePipeline::setTTSVoice()` écrasait des voix valides

**Fichier :** `app/audio/VoicePipeline.cpp`

```cpp
// AVANT — forçait exo_default et fr_vivienne vers fr_denise
if (selected.isEmpty()
    || selected == QStringLiteral("exo_default")
    || selected == QStringLiteral("fr_vivienne")) {
    selected = QStringLiteral("fr_denise");
}

// APRÈS — remplacement uniquement si sélection vide
if (selected.isEmpty()) {
    selected = QStringLiteral("fr_denise");
}
```

**Impact :** même avec la liste de voix corrigée, l'utilisateur ne pouvait pas
sélectionner `exo_default` ni `fr_vivienne` car ces valeurs étaient silencieusement
converties en `fr_denise` avant transmission au moteur Python.

---

## Ce qui N'était PAS un bug

| Composant | Statut |
|-----------|--------|
| `voices_metadata.json` | ✅ Encodage UTF-8 correct (7B 0D 0A…) — affichage terminal Windows biaisé |
| `tts_server.py` | ✅ Handler `list_voices` correct (retourne `engine.list_voices()`) |
| `TTSManager.cpp::fetchAvailableVoices()` | ✅ WebSocket correct, 5 min de timeout |
| `SettingsPage.qml` voiceCombo | ✅ Binding réactif `ttsVoicesChanged`, logique correcte |

---

## Résultat attendu après correctifs

```
# tts_server.py démarré, engine.list_voices() :
["exo_default", "fr_denise", "fr_eloise", "fr_henri", "fr_remy", "fr_vivienne"]
# → TTSManager reçoit QStringList(6 voix)
# → ComboBox affiche les 6 voix (plus le fallback ["fr_denise"])
```

---

## Vérification manuelle

1. Redémarrer le serveur TTS : `python/tts/tts_server.py --lang fr --streaming`
2. Se connecter avec un client WebSocket sur `ws://localhost:8767`
3. Envoyer `{"action": "list_voices"}` → vérifier `"available"` contient ≥ 5 entrées
4. Lancer EXO → Paramètres → "Voix TTS" → le ComboBox doit lister toutes les voix
5. Sélectionner `fr_vivienne` → vérifier que la synthèse utilise bien la voix Vivienne

---

## Build

```
cmake --build "D:\EXO\project\build" --config Release --target RaspberryAssistant -- /m:8
# → RaspberryAssistant.exe 64 bit, release executable [QML]  ✅  (0 erreur)
```

*Rapport généré le 2025-07-23 — Session EXO diagnostic audio P2*
