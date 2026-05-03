"""
cosyvoice_streaming_engine.py — engine TTS streaming **stateless** pour EXO.

Objectifs de ce module:
  1. Chargement unique du modèle CosyVoice2 au démarrage.
  2. Configuration explicite des providers ONNX Runtime — uniquement
     **CUDAExecutionProvider > CPUExecutionProvider**. TensorRT EP est
     volontairement désactivé (option 1) pour éviter les recompilations
     dynamiques liées aux shapes qui bloquent le first_chunk.
  3. API stateless: chaque appel `generate_stream(text)` est indépendant,
     ne lit/écrit AUCUN cache audio, ne réutilise AUCUN buffer global.
  4. Optimisation first_chunk: micro-segmentation de la 1ère phrase
     (split sur première virgule/conjonction si trop long), prewarm du
     frontend FR au démarrage pour sortir gruut du chemin critique.
  5. Instrumentation: temps modèle, first_chunk_ms, total_ms, RTF.

Le wrapper s'appuie sur l'API haut-niveau de CosyVoice2 (PyTorch). Aucun
état persistant n'est conservé entre deux requêtes.
"""

from __future__ import annotations

import builtins
import json
import logging
import os
import re
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional

import numpy as np
import torch

from audio_streamer import (
    OUTPUT_SAMPLE_RATE,
    DEFAULT_WS_CHUNK_BYTES,
    chunk_pcm,
    float_wave_to_pcm16,
    pcm_duration_seconds,
)

try:
    # Frontend FR (gruut) — remplace le wetext EN/ZH stock pour le francais.
    from tts.cosyvoice_french_frontend import install_french_frontend
except Exception:  # pragma: no cover
    install_french_frontend = None  # type: ignore[assignment]


# Auto-selection de la meilleure voix FR a partir du rapport
# scripts/profile_voices.py (D:/EXO/logs/tts_voice_report.json).
_VOICE_REPORT_PATH = Path(r"D:/EXO/logs/tts_voice_report.json")
_VOICE_REPORT_CACHE: "tuple[float, list[str]] | None" = None


def _best_voice_from_report() -> Optional[str]:
    """Retourne le 1er voice_id du rapport si dispo et frais (<24h)."""
    global _VOICE_REPORT_CACHE
    try:
        st = _VOICE_REPORT_PATH.stat()
    except OSError:
        return None
    if _VOICE_REPORT_CACHE is None or _VOICE_REPORT_CACHE[0] != st.st_mtime:
        try:
            data = json.loads(_VOICE_REPORT_PATH.read_text(encoding="utf-8"))
            ranking = list(data.get("ranking") or [])
        except (OSError, ValueError):
            ranking = []
        _VOICE_REPORT_CACHE = (st.st_mtime, ranking)
    ranking = _VOICE_REPORT_CACHE[1]
    return ranking[0] if ranking else None


@contextmanager
def _disable_builtin_text_frontends():
    """Bloque l'import de wetext/ttsfrd pendant la creation de CosyVoice2,
    pour eviter le telechargement du normalizer EN et le routage francais
    via le pipeline anglais."""
    original_import = builtins.__import__

    def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        root = name.split(".", 1)[0]
        if root in {"wetext", "ttsfrd"}:
            raise ImportError(f"{root} disabled in EXO FR frontend mode")
        return original_import(name, globals, locals, fromlist, level)

    builtins.__import__ = _guarded_import
    try:
        yield
    finally:
        builtins.__import__ = original_import

logger = logging.getLogger("exo.tts.streaming")

# ---------------------------------------------------------------------------
# Configuration providers ONNX Runtime — Option 1 : TRT EP désactivé
# ---------------------------------------------------------------------------
#
# Décision d'archi (option 1) : on n'utilise QUE CUDA + CPU. TensorRT EP est
# volontairement exclu pour éviter les recompilations dynamiques de moteurs
# TRT à chaque nouveau shape d'entrée (qui bloquaient la 1re vraie requête
# pendant >60 s alors que le prewarm court avait fonctionné).
# Cette politique reste compatible avec une réactivation future (option 2/3)
# en repassant ENABLE_TENSORRT à True ou en exposant un flag d'env.

# Flag explicite pour réactivation future. Ne PAS mettre True sans repenser
# le prewarm (cf. options 2 et 3 du plan TTS).
ENABLE_TENSORRT: bool = False

# Liste des providers utilisés par EXO TTS (ordre = priorité).
ORT_PROVIDERS_PRIORITY: List[str] = [
    # "TensorrtExecutionProvider",  # désactivé volontairement (option 1)
    "CUDAExecutionProvider",
    "CPUExecutionProvider",
]


def get_providers(model_dir: str) -> List[tuple]:
    """Construit la liste de providers ORT pour TOUTES les sessions du pipeline.

    Politique (option 1):
      - TensorrtExecutionProvider est **volontairement désactivé**.
      - On utilise uniquement CUDAExecutionProvider puis CPUExecutionProvider
        (fallback CPU uniquement si CUDA indisponible).
      - Aucun fallback implicite vers TRT n'est jamais ajouté.
    """
    try:
        import onnxruntime as ort
    except ImportError:
        logger.warning("[TTS] onnxruntime indisponible — pas de provider ORT configuré")
        return []

    available = set(ort.get_available_providers())
    logger.info("[TTS] ORT providers disponibles: %s", sorted(available))

    # Log explicite si TRT est présent sur la machine mais désactivé.
    if "TensorrtExecutionProvider" in available and not ENABLE_TENSORRT:
        logger.info("[TTS] TensorRT détecté mais volontairement désactivé.")

    providers: List[tuple] = []

    # NOTE: TensorRT volontairement omis — voir ENABLE_TENSORRT ci-dessus.
    if "CUDAExecutionProvider" in available:
        providers.append((
            "CUDAExecutionProvider",
            {
                "arena_extend_strategy": "kNextPowerOfTwo",
                "cudnn_conv_algo_search": "EXHAUSTIVE",
                "do_copy_in_default_stream": True,
            },
        ))
    providers.append(("CPUExecutionProvider", {}))

    active = [p[0] for p in providers]
    logger.info("[TTS] Providers actifs : %s", active)
    # Garde-fou explicite : ne JAMAIS exposer TRT par accident.
    assert "TensorrtExecutionProvider" not in active, (
        "TensorRT EP doit rester désactivé en option 1"
    )
    # Le paramètre model_dir est conservé dans la signature pour rester
    # compatible avec une réactivation future (option 2/3) qui pourrait
    # avoir besoin du dossier modèle pour le cache TRT.
    _ = model_dir
    return providers


# Alias rétro-compatible (ancien nom interne).
_build_providers = get_providers


def configure_global_ort_providers(model_dir: str) -> None:
    """Force les providers ORT pour les `InferenceSession` créées sans `providers=...`.

    CosyVoice2 instancie ses propres sessions ONNX en interne; cette fonction
    monkey-patche `ort.InferenceSession` au démarrage du serveur pour leur
    injecter notre liste de providers prioritaires (TRT > CUDA > CPU).
    """
    try:
        import onnxruntime as ort
    except ImportError:
        return

    desired = get_providers(model_dir)
    if not desired:
        return

    if getattr(ort, "_exo_patched", False):
        return

    original_init = ort.InferenceSession.__init__

    def _patched_init(self, *args, **kwargs):  # type: ignore[no-redef]
        # Force notre liste — même si l'appelant a fourni `providers=` qui
        # contiendrait TensorRT, on l'écrase pour respecter la politique
        # "option 1 : pas de TRT".
        forced = [p for p in desired]
        # Filtrage défensif: on retire toute occurrence de TRT au cas où.
        forced = [
            p for p in forced
            if (p[0] if isinstance(p, tuple) else p) != "TensorrtExecutionProvider"
        ]
        kwargs["providers"] = forced
        kwargs.setdefault("provider_options", None)
        return original_init(self, *args, **kwargs)

    ort.InferenceSession.__init__ = _patched_init  # type: ignore[assignment]
    ort._exo_patched = True
    logger.info(
        "[TTS] ORT InferenceSession patched — providers forcés: %s",
        [p[0] if isinstance(p, tuple) else p for p in desired],
    )


# ---------------------------------------------------------------------------
# Segmentation texte (latence-optimisée)
# ---------------------------------------------------------------------------

_SENT_SPLIT_RE = re.compile(r"(?<=[\.!\?])\s+")
_SOFT_SPLIT_RE = re.compile(r"\s*[,;:]\s+|\s+(?:et|mais|donc|car|or|ni|puis|alors)\s+", re.IGNORECASE)


def split_sentences(text: str) -> List[str]:
    parts = [s.strip() for s in _SENT_SPLIT_RE.split(text) if s.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def split_first_sentence_for_latency(first: str, soft_max_chars: int = 60) -> List[str]:
    """Pour réduire le first_chunk: si la 1ère phrase est longue, on coupe
    sur la 1ère virgule/conjonction pour streamer le 1er morceau plus vite.
    Le reste est ré-émis tel quel pour conserver la prosodie.
    """
    if len(first) <= soft_max_chars:
        return [first]
    m = _SOFT_SPLIT_RE.search(first, pos=20)
    if not m:
        return [first]
    head = first[: m.start()].strip().rstrip(",;:")
    tail = first[m.end():].strip()
    if not head or not tail:
        return [first]
    # Ponctuation finale légère pour éviter une intonation suspendue.
    if not head.endswith((",", ".", "?", "!")):
        head = head + ","
    return [head, tail]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

@dataclass
class StreamMetrics:
    text_len: int
    first_chunk_ms: float
    total_ms: float
    audio_seconds: float
    chunks: int

    @property
    def rtf(self) -> float:
        return (self.total_ms / 1000.0) / self.audio_seconds if self.audio_seconds > 0 else float("inf")


class CosyVoiceStreamingEngine:
    """Wrapper streaming **stateless** autour de CosyVoice2.

    Threading model:
      - `load()` est appelé une fois au démarrage (bloquant).
      - `generate_stream(text)` est ré-entrant (un lock de modèle protège
        l'appel CosyVoice qui n'est pas thread-safe), MAIS aucun état
        audio n'est conservé entre deux appels.
    """

    def __init__(
        self,
        model_dir: str,
        speaker_id: str = "exo_default",
        prompt_wav: Optional[str] = None,
        prompt_text: Optional[str] = None,
        ws_chunk_bytes: int = DEFAULT_WS_CHUNK_BYTES,
    ) -> None:
        self.model_dir = model_dir
        self.speaker_id = speaker_id
        self.prompt_wav = prompt_wav
        self.prompt_text = prompt_text
        self.ws_chunk_bytes = ws_chunk_bytes

        self.model = None
        self._native_sr: int = OUTPUT_SAMPLE_RATE
        self._loaded = False
        self._model_lock = threading.Lock()

        # Catalogue des voix zero-shot (alimente par voices.json au load).
        # voice_id -> {"prompt_wav": str, "prompt_text": str, "registered": bool}
        self._voices: "dict[str, dict]" = {}
        self._voice_order: "list[str]" = []

    # -- chargement -------------------------------------------------------

    def load(self) -> None:
        """Charge CosyVoice2 une seule fois et configure ORT (TRT/CUDA/CPU)."""
        if self._loaded:
            return
        t0 = time.monotonic()

        configure_global_ort_providers(self.model_dir)

        # Ajout du repo CosyVoice si présent (chemin EXO standard).
        cosy_root = os.environ.get("COSYVOICE_REPO")
        if cosy_root and os.path.isdir(cosy_root) and cosy_root not in sys.path:
            sys.path.insert(0, cosy_root)
            third = os.path.join(cosy_root, "third_party", "Matcha-TTS")
            if os.path.isdir(third) and third not in sys.path:
                sys.path.insert(0, third)

        from cosyvoice.cli.cosyvoice import CosyVoice2  # type: ignore

        # Option 1 : aucun chargement TRT. CosyVoice2 ne tentera pas de
        # convertir son flow decoder en .plan TensorRT. On reste 100 %
        # PyTorch + ONNX (CUDA EP). Ne PAS r\u00e9activer sans repenser
        # le prewarm (cf. options 2 et 3).
        use_trt = False  # forc\u00e9 \u00e0 False (option 1 \u2014 TensorRT d\u00e9sactiv\u00e9)
        logger.info("[TTS] CosyVoice2 load_trt=%s (TensorRT d\u00e9sactiv\u00e9)", use_trt)

        # Si le modele expose un dossier `frontend/` (CosyVoice FR EXO), on
        # bloque l'import de wetext/ttsfrd pendant la construction du modele.
        frontend_dir = Path(self.model_dir) / "frontend"
        use_fr_frontend = (
            install_french_frontend is not None and frontend_dir.is_dir()
        )
        if use_fr_frontend:
            with _disable_builtin_text_frontends():
                self.model = CosyVoice2(
                    self.model_dir,
                    load_jit=False,
                    load_trt=use_trt,
                    fp16=True,
                )
        else:
            self.model = CosyVoice2(
                self.model_dir,
                load_jit=False,
                load_trt=use_trt,
                fp16=True,
            )
        self._native_sr = int(getattr(self.model, "sample_rate", OUTPUT_SAMPLE_RATE))

        # Installation du frontend FR (gruut) en remplacement de wetext.
        if use_fr_frontend:
            try:
                wrapper = install_french_frontend(
                    self.model,
                    assets_dir=frontend_dir,
                    language="fr",
                )
                logger.info(
                    "[TTS] Frontend FR (gruut) installe (assets=%s)", frontend_dir
                )
                logger.info("[TTS] FR frontend integrity: %s", getattr(wrapper, "integrity", {}))
            except Exception:  # pragma: no cover
                logger.exception("[TTS] Echec installation frontend FR (gruut)")
        else:
            logger.warning(
                "[TTS] Frontend FR NON installe (frontend dir absent ou module "
                "indisponible) -- accent/prosodie risque d'etre degrade. "
                "Verifier EXO_COSYVOICE_MODELS=%s",
                self.model_dir,
            )

        # Enregistrement zero-shot speaker (idempotent).
        if self.prompt_wav and os.path.isfile(self.prompt_wav):
            try:
                self.model.add_zero_shot_spk(
                    self.prompt_text or "Bonjour.",
                    self.prompt_wav,
                    self.speaker_id,
                )
                logger.info("Zero-shot speaker '%s' enregistré", self.speaker_id)
                self._voices[self.speaker_id] = {
                    "prompt_wav": self.prompt_wav,
                    "prompt_text": self.prompt_text or "Bonjour.",
                    "registered": True,
                }
                self._voice_order.append(self.speaker_id)
            except Exception:  # pragma: no cover
                logger.exception("Echec add_zero_shot_spk")

        # Enregistrement de toutes les voix declarees dans voices.json.
        self._register_voices_from_json()

        # Prewarm: 1 inférence courte pour purger le frontend FR (gruut)
        # du chemin critique de la 1ère vraie requête.
        try:
            with torch.inference_mode():
                for _ in self._raw_infer("Bonjour."):
                    pass
            logger.info("Prewarm streaming OK")
        except Exception:  # pragma: no cover
            logger.exception("Prewarm a échoué (non bloquant)")

        self._loaded = True
        logger.info(
            "CosyVoice2 chargé en %.2fs (native_sr=%d Hz, dir=%s)",
            time.monotonic() - t0, self._native_sr, self.model_dir,
        )

    # -- inférence brute --------------------------------------------------

    def _register_voices_from_json(self) -> None:
        """Enregistre comme zero-shot speakers toutes les voix de voices.json."""
        voices_json = Path(self.model_dir) / "voices.json"
        if not voices_json.is_file():
            logger.info("voices.json absent (%s) - 1 seule voix disponible", voices_json)
            return
        try:
            entries = json.loads(voices_json.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.exception("voices.json illisible: %s", voices_json)
            return
        if not isinstance(entries, list):
            logger.warning("voices.json: format inattendu (liste attendue)")
            return

        for v in entries:
            if not isinstance(v, dict):
                continue
            vid = str(v.get("id") or "").strip()
            if not vid:
                continue
            wav_rel = v.get("file") or ""
            wav_path = os.path.join(self.model_dir, "voices", wav_rel)
            ptext = (v.get("prompt_text") or "").strip()
            if not (wav_rel and os.path.isfile(wav_path) and ptext):
                logger.warning(
                    "voices.json[%s]: wav ou prompt_text manquant - ignoree", vid
                )
                continue
            registered = False
            try:
                self.model.add_zero_shot_spk(ptext, wav_path, vid)
                registered = True
                logger.info("Zero-shot voice '%s' enregistree (%s)", vid, wav_rel)
            except Exception:  # pragma: no cover
                logger.exception("Echec add_zero_shot_spk(%s)", vid)
            self._voices[vid] = {
                "prompt_wav": wav_path,
                "prompt_text": ptext,
                "registered": registered,
            }
            if vid not in self._voice_order:
                self._voice_order.append(vid)
            # Aliases legacy_id / name -> meme entree (resolution uniquement).
            for alias_key in ("legacy_id", "name"):
                alias = str(v.get(alias_key) or "").strip()
                if alias and alias not in self._voices:
                    self._voices[alias] = self._voices[vid]

    def list_voices(self) -> list[str]:
        """Retourne les voix exposees a la GUI (ordre stable)."""
        return list(self._voice_order)

    def _resolve_voice(self, voice: Optional[str]) -> "tuple[str, str, str]":
        """Resout (speaker_id, prompt_wav, prompt_text) pour la voix demandee.

        Fallback sur la voix par defaut (self.speaker_id) si la voix demandee
        est inconnue ou non enregistree. Si aucune voix n'est demandee et que
        speaker_id pointe sur un fallback minimal, on tente d'utiliser la
        meilleure voix FR rapportee par scripts/profile_voices.py.
        """
        if voice:
            v = voice.strip()
            entry = self._voices.get(v)
            if entry and entry.get("registered"):
                for canon in self._voice_order:
                    if self._voices.get(canon) is entry:
                        return canon, entry["prompt_wav"], entry["prompt_text"]
            elif v:
                logger.warning("Voix '%s' inconnue - fallback sur '%s'", v, self.speaker_id)
        else:
            # Auto-selection si rapport disponible et speaker_id par defaut.
            best = _best_voice_from_report()
            if best and best in self._voices and self._voices[best].get("registered"):
                logger.info("[FR] Selected voice (auto): %s", best)
                entry = self._voices[best]
                for canon in self._voice_order:
                    if self._voices.get(canon) is entry:
                        return canon, entry["prompt_wav"], entry["prompt_text"]
        # Fallback defaut.
        entry = self._voices.get(self.speaker_id)
        if entry:
            return self.speaker_id, entry["prompt_wav"], entry["prompt_text"]
        return self.speaker_id, self.prompt_wav or "", self.prompt_text or ""

    def _raw_infer(self, text: str, speed: float = 1.0, voice: Optional[str] = None):
        """Itère sur les sorties CosyVoice (dict avec 'tts_speech')."""
        assert self.model is not None
        spk_id, p_wav, p_text = self._resolve_voice(voice)
        if p_text and p_wav and os.path.isfile(p_wav):
            yield from self.model.inference_zero_shot(
                tts_text=text,
                prompt_text=p_text,
                prompt_wav=p_wav,
                zero_shot_spk_id=spk_id,
                stream=True,
                speed=speed,
            )
        else:
            yield from self.model.inference_cross_lingual(
                tts_text=text,
                prompt_wav=p_wav or "",
                zero_shot_spk_id=spk_id,
                stream=True,
                speed=speed,
            )

    # -- API publique stateless ------------------------------------------

    def generate_stream(
        self,
        text: str,
        speed: float = 1.0,
        ws_chunk_bytes: Optional[int] = None,
        voice: Optional[str] = None,
    ) -> Iterator[bytes]:
        """Génère et yield des chunks PCM16 prêts à envoyer sur WebSocket.

        STATELESS: aucun cache, aucune mémoire de l'appel précédent.
        Chaque appel reproduit intégralement la synthèse pour `text`.

        - Yield le 1er chunk dès que le 1er bloc audio sort du modèle
          (pas d'accumulation).
        - Logs structurés first_chunk_ms / total_ms / RTF.
        """
        if not self._loaded:
            raise RuntimeError("CosyVoiceStreamingEngine non chargé — appelle load() d'abord.")

        text = (text or "").strip()
        if not text:
            return

        chunk_size = ws_chunk_bytes or self.ws_chunk_bytes

        # 1) Segmentation: première phrase isolée, possiblement coupée
        #    à la 1ère virgule pour réduire le first_chunk.
        sentences = split_sentences(text)
        if not sentences:
            return
        head_blocks = split_first_sentence_for_latency(sentences[0])
        tail = sentences[1:]
        blocks = head_blocks + tail
        logger.info(
            "[gen] text_len=%d sentences=%d -> blocks=%d (first=%r)",
            len(text), len(sentences), len(blocks), blocks[0][:50],
        )

        t0 = time.monotonic()
        first_chunk_ms: Optional[float] = None
        total_pcm_bytes = 0
        chunks_sent = 0

        # 2) Lock modèle (CosyVoice n'est pas thread-safe), MAIS aucune
        #    variable d'instance n'est mutée par la synthèse.
        with self._model_lock, torch.inference_mode():
            for block in blocks:
                if not block.strip():
                    continue
                pending = bytearray()
                for output in self._raw_infer(block, speed=speed, voice=voice):
                    speech = output.get("tts_speech")
                    if speech is None:
                        continue
                    wav = speech.squeeze()
                    if wav.numel() == 0:
                        continue

                    # Conversion + resample éventuel.
                    wav_np = wav.float().cpu().numpy()
                    if self._native_sr != OUTPUT_SAMPLE_RATE:
                        wav_np = _resample_linear(
                            wav_np, self._native_sr, OUTPUT_SAMPLE_RATE,
                        )
                    pcm = float_wave_to_pcm16(wav_np)
                    if not pcm:
                        continue

                    pending.extend(pcm)
                    # Flush dès qu'on a au moins un chunk plein → first_chunk
                    # minimum, fluidité du stream maximum.
                    while len(pending) >= chunk_size:
                        out = bytes(pending[:chunk_size])
                        del pending[:chunk_size]
                        if first_chunk_ms is None:
                            first_chunk_ms = (time.monotonic() - t0) * 1000.0
                            logger.info(
                                "[gen] first_chunk_ms=%.0f (block 1/%d)",
                                first_chunk_ms, len(blocks),
                            )
                        total_pcm_bytes += len(out)
                        chunks_sent += 1
                        yield out

                # Fin du bloc → on flush le résidu pour ne pas retenir
                # de samples jusqu'au bloc suivant.
                if pending:
                    out = bytes(pending)
                    if first_chunk_ms is None:
                        first_chunk_ms = (time.monotonic() - t0) * 1000.0
                        logger.info(
                            "[gen] first_chunk_ms=%.0f (residual flush)",
                            first_chunk_ms,
                        )
                    total_pcm_bytes += len(out)
                    chunks_sent += 1
                    yield out

        total_ms = (time.monotonic() - t0) * 1000.0
        audio_s = pcm_duration_seconds(total_pcm_bytes)
        rtf = (total_ms / 1000.0) / audio_s if audio_s > 0 else float("inf")
        logger.info(
            "[gen] DONE first=%.0fms total=%.0fms chunks=%d audio=%.2fs RTF=%.2f text=%r",
            first_chunk_ms or -1, total_ms, chunks_sent, audio_s, rtf, text[:60],
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resample_linear(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    """Resample linéaire simple. Pour qualité supérieure, brancher torchaudio."""
    if sr_in == sr_out or x.size == 0:
        return x.astype(np.float32, copy=False)
    n_out = int(round(x.size * sr_out / sr_in))
    if n_out <= 1:
        return x.astype(np.float32, copy=False)
    xp = np.linspace(0.0, 1.0, num=x.size, dtype=np.float64)
    fp = x.astype(np.float64, copy=False)
    xn = np.linspace(0.0, 1.0, num=n_out, dtype=np.float64)
    return np.interp(xn, xp, fp).astype(np.float32)
