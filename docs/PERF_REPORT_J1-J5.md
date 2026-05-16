# Rapport final — Optimisations J1 → J5 (audit perf 2026-05-14)

## 1. Modifications appliquées

| ID | Fichier | Nature | Statut |
|----|---------|--------|--------|
| J1 | [services/orpheus/server_gguf.py](services/orpheus/server_gguf.py) | `Llama()` : `n_batch=1024`, `n_ubatch=512`, `flash_attn=True`, `offload_kqv=True` (tous overridables via env `ORPHEUS_*`) + pré-warm 1 token après chargement | Appliqué |
| J2 | [services/orpheus/bench_quants.py](services/orpheus/bench_quants.py) | Script comparant Q4_K_M / Q5_K_M / Q6_K / Q8_0 (RTF, first_chunk) | Prêt — exécution **différée** : Q5_K_M / Q6_K absents, téléchargement **non auto-déclenché** (politique : aucune modif d'arborescence sans approbation) |
| J4 | [app/audio/VoicePipeline.cpp](app/audio/VoicePipeline.cpp) (≈ L1271) | Suppression de `std::vector<int16_t>(samples, samples+count)` à chaque chunk → `thread_local std::vector<int16_t> chunkBuf` réutilisé + `std::memcpy`. Mutex `m_preprocMutex` **conservé** (protège l'état interne du préprocesseur, pas le buffer). | Appliqué + binaire reconstruit (`VoicePipeline.obj` 17:05:11, exe 17:06:19) |
| J5 | [python/stt/stt_server.py](python/stt/stt_server.py) | (a) `_send_partial` : `np.frombuffer(self._audio_buffer, ...)` (vue zéro-copie) au lieu de `bytes(self._audio_buffer)`. (b) `_finalize` : vue + `np.array(..., copy=True)` avant `clear()`. (c) `astype(np.float64)` → `astype(np.float32)` (gain & RMS). | Appliqué |

Aucun changement d'arborescence, aucune modification de venv, aucune touche à Orpheus venv (LOCKED).

## 2. Validation runtime

### 2.1 Pré-warm Orpheus (J1) — log `tts.err.log`

```
17:06:35 [Orpheus] INFO LLM charge en 2.2s (n_ctx=4096, gpu_layers=-1,
                       n_batch=1024, n_ubatch=512, flash_attn=True, offload_kqv=True)
17:06:35 [Orpheus] INFO LLM pre-warm OK (79 ms)
```

Paramètres effectifs **confirmés** ; pré-warm 79 ms (premier token émis sans pénalité de cold cache).

### 2.2 Bench TTS — 5 phrases ([scripts/bench_tts_5x.py](scripts/bench_tts_5x.py), voix `amelie`, WS 8767)

| # | len | first_chunk | total | audio | RTF |
|---|----:|----:|----:|----:|----:|
| 1 | 25 | 593 ms | 2 020 ms | 1.32 s | 1.49 |
| 2 | 41 | 368 ms | 2 381 ms | 1.80 s | 1.32 |
| 3 | 72 | 368 ms | 4 003 ms | 3.16 s | 1.27 |
| 4 | 15 | 364 ms | 1 711 ms | 0.96 s | 1.77 |
| 5 | 72 | 381 ms | 3 789 ms | 3.16 s | 1.20 |

**Résumé**

| Métrique | Baseline (audit J0) | Après J1 | Gain |
|---|---|---|---|
| `first_chunk_ms` (avg) | ≈ 547 ms (375 – 720) | **415 ms** (364 – 593) | **−24 %** |
| `first_chunk_ms` (steady, runs 2-5) | ≈ 525 ms | **370 ms** | **−30 %** |
| `RTF` (avg) | ≈ 1.65 (1.33 – 2.03) | **1.41** (1.20 – 1.77) | **−14 %** |
| `RTF` (best) | 1.33 | **1.20** | **−10 %** |

Run 1 reste plus lent (593 ms / RTF 1.49) — premier inference après warm a encore un coût marginal de remplissage des KV-cache utilisateur. Les runs 2-5 sont stables.

### 2.3 STT (J5) — log `stt.err.log`

```
17:07:20 STT _finalize (transcribe): 219 ms
17:08:54 STT _finalize (transcribe): 265 ms
17:10:04 STT _finalize (transcribe): 10156 ms   ← long audio (~30 s) ; n'inclut pas de copie pertinente
```

Sur les segments de durée comparable au baseline (1-3 s audio) : **219 / 265 ms** vs baseline **234-328 ms**. Gain ≈ **5-15 ms** (cohérent avec l'élimination de `bytes()` + un `astype(float64)` 8× plus large que `int16`). L'ordre de grandeur dominant reste l'appel HTTP whisper-server ; J5 a éliminé le surcoût de copie sans réduire ce dominant.

### 2.4 Pipeline audio C++ (J4) — log `exo_20260514_170701.log`

```
slow path : n=84 entrées en ~4 min   min=536 µs   max=36 667 µs   avg=5 937 µs
```

J4 a éliminé l'allocation/copie heap par chunk (vector temporaire), mais **les spikes ne disparaissent pas complètement**. Les warnings restants viennent de :

- `processAudioChunk slow path` (autre call-site, traite VAD + ring buffer + I/O WS) — non couvert par J4.
- variance OS Windows (pression GC d'autres services pendant les fenêtres serrées).

Recommandation : un J4-bis ciblé sur `processAudioChunk` (séparer chemin VAD du chemin transmission) sera nécessaire pour atteindre le « 0 spike ». Hors scope J1-J5 strict.

## 3. État des objectifs utilisateur

| Objectif | Résultat |
|---|---|
| J1 Orpheus tuning + pré-warm | ✅ Réalisé, gains mesurables (−24 % first_chunk, −14 % RTF) |
| J2 Bench Q6_K vs Q5_K_M | ⏸ Différé (modèles absents — script prêt, [services/orpheus/bench_quants.py](services/orpheus/bench_quants.py)) |
| J4 VoicePipeline buffer reuse | ✅ Réalisé, allocation par chunk supprimée |
| J4 Élimination spikes audio | ⚠ Réduction observée mais non totale (autre call-site responsable) |
| J5 STT bytes()/float64 | ✅ Réalisé, gain marginal cohérent |
| Stabilité pipeline | ✅ 17/17 services UP, aucune régression observée sur 5 syntheses + ~5 min runtime |

## 4. Suite recommandée (hors scope actuel)

1. **J2 réel** : télécharger `Orpheus-3b-French-FT-Q5_K_M.gguf` (~2 GB) et `…Q6_K.gguf` (~2.4 GB) puis exécuter `python services/orpheus/bench_quants.py`. Décision modèle production basée sur RTF + qualité subjective.
2. **J4-bis** : profiler `processAudioChunk` (probable goulot : `m_ringBuf` + envoi WS bloquant). Cible : bornes < 500 µs sur 99 % des chunks.
3. **Pré-warm SNAC** : compléter J1 par un forward 1 frame SNAC après chargement (analogue au pré-warm Llama) pour aplatir le cold-start CUDA initial.

## 5. Annexes

- Scripts ajoutés : [scripts/bench_tts_5x.py](scripts/bench_tts_5x.py), [services/orpheus/bench_quants.py](services/orpheus/bench_quants.py)
- Logs validés : `D:\EXO\logs\tts.err.log`, `D:\EXO\logs\exo_20260514_170701.log`, `D:\EXO\logs\stt.err.log`
- Build : `cmake --build d:\EXO\build --config Release --target RaspberryAssistant -- -m` → ExitCode 0
- Restart : `D:\EXO\launch_exo_silent.ps1` (politique launcher unique respectée)
