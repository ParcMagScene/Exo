"""
cosyvoice_engine.py — CosyVoice 2 engine for EXO TTS server

Drop-in replacement for XTTSEngine. Uses CosyVoice2-0.5B with streaming
inference for low-latency token-level audio generation on CUDA.

Audio output: PCM16 24 kHz mono — identical to the previous XTTS v2 backend.
"""

from __future__ import annotations

import logging
import os
import re
import time
import json
import builtins
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from tts.cosyvoice_french_frontend import install_french_frontend

logger = logging.getLogger("exo.tts")

# Audio constants — must match C++ TTSManager expectations
COSYVOICE_SAMPLE_RATE = 24000  # CosyVoice2-0.5B native rate (from yaml)
OUTPUT_SAMPLE_RATE = 24000
CHUNK_FRAMES = 128  # ~5.3 ms @ 24 kHz mono16 — aggressive streaming


class CosyVoiceEngine:
    """CosyVoice 2 streaming TTS engine for EXO.

    API contract (identical to former XTTSEngine):
      - load()             → warm the model on CUDA
      - synthesize_stream() → yield PCM16 bytes chunks
      - synthesize()        → return full PCM16 bytes
      - warmup()           → silent GPU warm-up
      - set_voice() / set_language() / list_voices()
    """

    # Readiness phases (same as previous XTTSEngine for compatibility)
    PHASE_INIT = "ready_init"
    PHASE_LOADING = "ready_loading"
    PHASE_WARMUP = "ready_warmup"
    PHASE_ONLINE = "ready_online"

    def __init__(self, voice: str = "", lang: str = "fr") -> None:
        self.voice_name = voice
        self.language = lang
        self.model = None  # CosyVoice2 instance
        self._loaded = False
        self.device = "cpu"
        self._last_synth_time = 0.0
        # Readiness
        self.phase = self.PHASE_INIT
        self._phase_callback = None
        self._profile: dict = {}
        # Cache (injected from tts_server)
        self._cache = None
        # Voice prompt for zero-shot cloning
        self._prompt_wav: Optional[str] = None
        self._prompt_text: str = ""
        self.voices: dict[str, dict] = {}
        self._voice_aliases: dict[str, str] = {}
        self._voice_order: list[str] = []
        # Available speakers from spk2info
        self._available_spks: list[str] = []
        # Latency optimization flags (set by tts_server from CLI)
        self.latency_optimized: bool = False
        self.max_chunk_length: int = 4096

    # ------------------------------------------------------------------
    # Device detection
    # ------------------------------------------------------------------
    @staticmethod
    def _detect_device() -> str:
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            logger.info("CosyVoice CUDA device: %s (VRAM: %.1f GB)", name, vram)
            return "cuda"
        logger.warning("CUDA not available — falling back to CPU")
        return "cpu"

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------
    @staticmethod
    def _disable_builtin_text_frontends():
        original_import = builtins.__import__

        def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            root = name.split(".", 1)[0]
            if root in {"wetext", "ttsfrd"}:
                raise ImportError(f"{root} disabled in EXO FR frontend mode")
            return original_import(name, globals, locals, fromlist, level)

        class _ImportGuard:
            def __enter__(self_inner):
                builtins.__import__ = _guarded_import
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb):
                builtins.__import__ = original_import
                return False

        return _ImportGuard()

    def _probe_ort_provider(self, model_dir: str) -> None:
        """Log effective ORT providers on a real model file.

        This gives a deterministic runtime signal like:
        InferenceSession created with providers: [...]
        """
        try:
            import onnxruntime as ort
        except Exception as exc:
            logger.warning("ONNX Runtime import failed during provider probe: %s", exc)
            return

        candidates = [
            os.path.join(model_dir, "campplus.onnx"),
            os.path.join(model_dir, "model.onnx"),
        ]
        target = next((p for p in candidates if os.path.isfile(p)), "")
        if not target:
            logger.warning("ORT provider probe skipped: no ONNX file found in %s", model_dir)
            return

        try:
            providers = self._build_ort_providers(model_dir)
            sess = ort.InferenceSession(target, providers=providers)
            logger.info("InferenceSession created with providers: %s", sess.get_providers())
        except Exception as exc:
            logger.warning("ORT provider probe failed: %s", exc)

    @staticmethod
    def _build_ort_providers(model_dir: str):
        """Build ORT provider list with TensorRT first when available.

        Order: TensorrtExecutionProvider → CUDAExecutionProvider → CPUExecutionProvider.
        Engine cache enabled so first-launch JIT compile is amortized.
        """
        try:
            import onnxruntime as ort
            avail = set(ort.get_available_providers())
        except Exception:
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        providers = []
        if "TensorrtExecutionProvider" in avail:
            cache_dir = os.environ.get(
                "EXO_TRT_CACHE",
                os.path.join(model_dir, "trt_cache"),
            )
            try:
                os.makedirs(cache_dir, exist_ok=True)
            except Exception:
                pass
            providers.append(("TensorrtExecutionProvider", {
                "trt_engine_cache_enable": True,
                "trt_engine_cache_path": cache_dir,
                "trt_fp16_enable": True,
            }))
        providers.append("CUDAExecutionProvider")
        providers.append("CPUExecutionProvider")
        return providers

    @staticmethod
    def _check_trt_runtime_available() -> bool:
        """Probe whether TensorRT + cuDNN runtime DLLs are loadable on this host.

        Returns True only when the EP can actually be loaded by ONNX Runtime.
        """
        if os.name != "nt":
            return True
        import ctypes
        # TRT 10.x or 8.x main library
        trt_candidates = ["nvinfer_10.dll", "nvinfer.dll", "nvinfer_8.dll"]
        cudnn_candidates = ["cudnn64_9.dll", "cudnn64_8.dll"]
        trt_ok = False
        for name in trt_candidates:
            try:
                ctypes.WinDLL(name)
                trt_ok = True
                break
            except OSError:
                continue
        cudnn_ok = False
        for name in cudnn_candidates:
            try:
                ctypes.WinDLL(name)
                cudnn_ok = True
                break
            except OSError:
                continue
        return trt_ok and cudnn_ok

    @staticmethod
    def _enable_tensorrt_globally(model_dir: str) -> bool:
        """Monkeypatch onnxruntime.InferenceSession so all CosyVoice2 ONNX
        sessions created without explicit providers default to TRT->CUDA->CPU.

        Returns True when patch is installed.
        """
        try:
            import onnxruntime as ort
            avail = set(ort.get_available_providers())
        except Exception as exc:
            logger.warning("[FR] TensorRT activation skipped: %s", exc)
            return False
        if "TensorrtExecutionProvider" not in avail:
            logger.info("[FR] TensorRT indisponible (provider absent du build ORT) \u2014 fallback CUDA")
            return False
        if not CosyVoiceEngine._check_trt_runtime_available():
            logger.info("[FR] TensorRT indisponible (DLL manquantes) \u2014 fallback CUDA")
            return False
        if getattr(ort.InferenceSession, "_exo_trt_patched", False):
            return True
        defaults = CosyVoiceEngine._build_ort_providers(model_dir)
        _OrigInit = ort.InferenceSession.__init__

        def _provider_name(p):
            return p if isinstance(p, str) else p[0]

        def _ensure_trt(providers):
            """Prefix TensorrtExecutionProvider (with options) if missing."""
            if not providers:
                return defaults
            names = [_provider_name(p) for p in providers]
            if "TensorrtExecutionProvider" in names:
                return providers
            trt_entry = next(
                (p for p in defaults if _provider_name(p) == "TensorrtExecutionProvider"),
                None,
            )
            if trt_entry is None:
                return providers
            # Build new list: TRT first, then user-provided (without dup)
            merged = [trt_entry]
            for p in providers:
                if _provider_name(p) != "TensorrtExecutionProvider":
                    merged.append(p)
            return merged

        def _patched_init(self, *args, **kwargs):
            kwargs["providers"] = _ensure_trt(kwargs.get("providers"))
            return _OrigInit(self, *args, **kwargs)

        ort.InferenceSession.__init__ = _patched_init
        ort.InferenceSession._exo_trt_patched = True
        logger.info("[FR] TensorRT activ\u00e9 (si support\u00e9) \u2014 providers=%s",
                    [p if isinstance(p, str) else p[0] for p in defaults])
        return True

    def load(self) -> None:
        """Load CosyVoice2-0.5B model and warm up GPU."""
        t_total = time.monotonic()

        # ── Phase 1: INIT ──
        self._set_phase(self.PHASE_INIT)
        t0 = time.monotonic()
        self.device = self._detect_device()
        self._profile["python_init_ms"] = (time.monotonic() - t0) * 1000

        # ── Phase 2: LOADING ──
        self._set_phase(self.PHASE_LOADING)
        t0 = time.monotonic()

        # ── MODEL CHOICE ──
        # Auto-bascule vers CosyVoice2-0.25B si présent (latence ~50% plus basse).
        env_dir = os.environ.get("EXO_COSYVOICE_MODELS")
        if env_dir:
            model_dir = env_dir
        else:
            candidate_025b = r"D:\EXO\models\cosyvoice_0.25b"
            if os.path.isdir(candidate_025b):
                model_dir = candidate_025b
                logger.info("[FR] Mod\u00e8le CosyVoice2-0.25B activ\u00e9 (%s)", model_dir)
            else:
                model_dir = r"D:\EXO\models\cosyvoice_fr"
                logger.info("[FR] CosyVoice2-0.25B introuvable \u2014 fallback 0.5B (%s)", model_dir)
        logger.info("Loading CosyVoice2 from %s on %s \u2026", model_dir, self.device)

        # Activer TensorRT (si supporté) AVANT toute création d'InferenceSession
        # afin que le monkeypatch s'applique aux sessions internes de CosyVoice2.
        self._enable_tensorrt_globally(model_dir)

        try:
            from cosyvoice.cli.cosyvoice import CosyVoice2 as _CosyVoice2
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "CosyVoice package not found in the active Python environment. "
                "Install it with: python -m pip install <path-to-CosyVoice-clone> --no-deps"
            ) from exc

        # fp16=True : ~20-30% gain first-chunk sur RTX 3070 (CosyVoice2 gère le cast).
        _fp16 = os.environ.get("EXO_COSYVOICE_FP16", "1") not in ("0", "false", "False")
        if (self.language or "").lower().startswith("fr"):
            with self._disable_builtin_text_frontends():
                self.model = _CosyVoice2(model_dir=model_dir, load_jit=False, fp16=_fp16)
        else:
            self.model = _CosyVoice2(model_dir=model_dir, load_jit=False, fp16=_fp16)
        if _fp16:
            logger.info("[FR] FP16 activ\u00e9 pour CosyVoice2")
        else:
            logger.info("[FR] FP16 d\u00e9sactiv\u00e9 (EXO_COSYVOICE_FP16=0)")
        self._profile["model_load_ms"] = (time.monotonic() - t0) * 1000
        logger.info("CosyVoice2-0.5B loaded in %.0f ms", self._profile["model_load_ms"])

        if (self.language or "").lower().startswith("fr"):
            frontend_dir = Path(model_dir) / "frontend"
            frontend_t0 = time.monotonic()
            frontend_wrapper = install_french_frontend(
                self.model,
                assets_dir=frontend_dir,
                language="fr",
            )
            self._profile["frontend_fr_ms"] = (time.monotonic() - frontend_t0) * 1000
            logger.info("FR frontend integrity: %s", frontend_wrapper.integrity)

        # Explicit ONNX Runtime provider visibility for diagnostics.
        self._probe_ort_provider(model_dir)

        # Verify sample rate
        native_sr = getattr(self.model, "sample_rate", COSYVOICE_SAMPLE_RATE)
        if native_sr != OUTPUT_SAMPLE_RATE:
            logger.warning(
                "CosyVoice2 native sample rate %d ≠ expected %d — will resample",
                native_sr, OUTPUT_SAMPLE_RATE,
            )

        # Discover available speakers
        try:
            self._available_spks = self.model.list_available_spks()
            logger.info("Available speakers: %s", self._available_spks)
        except Exception:
            logger.warning("Failed to list available speakers on init", exc_info=True)
            self._available_spks = []

        # Voice prompt for cross-lingual / zero-shot inference
        self._resolve_voice_prompt()

        # Register prompt WAV as a reusable zero-shot speaker (avoids
        # re-processing the WAV embedding on every inference call).
        if self._prompt_wav and os.path.isfile(self._prompt_wav):
            spk_id = "exo_default"
            try:
                self.model.add_zero_shot_spk(
                    self._prompt_text, self._prompt_wav, spk_id,
                )
                logger.info("Registered zero-shot speaker '%s' from %s", spk_id, self._prompt_wav)
            except Exception as exc:
                logger.warning("Failed to register zero-shot speaker: %s", exc)

        # Register all voices from voices/ directory as zero-shot speakers.
        # Deduplicate by WAV path to avoid redundant registrations (registry + legacy metadata).
        seen_wavs: set[str] = set()
        for vname, vinfo in getattr(self, "_voice_prompts", {}).items():
            if vname == "exo_default":
                continue  # already registered above
            wav_path = vinfo["wav"]
            wav_key = str(Path(wav_path).resolve()).lower()
            if wav_key in seen_wavs:
                continue
            seen_wavs.add(wav_key)
            prompt_text = vinfo.get("prompt_text", "")
            try:
                self.model.add_zero_shot_spk(prompt_text, wav_path, vname)
                logger.info("Registered FR voice '%s' from %s", vname, wav_path)
            except Exception as exc:
                logger.warning("Failed to register voice '%s': %s", vname, exc)

        # Refresh available speakers list — merge SFT speakers AND zero-shot voices.
        # CosyVoice2's list_available_spks() may not include zero-shot speakers
        # added via add_zero_shot_spk(), so we union both sources.
        try:
            sft_spks = self.model.list_available_spks()
        except Exception:
            logger.warning("Failed to list SFT speakers", exc_info=True)
            sft_spks = []

        registered: set[str] = set(sft_spks)
        registered.update(self._voice_prompts.keys())  # all voices from voices/ dir
        if self._prompt_wav and os.path.isfile(self._prompt_wav):
            registered.add("exo_default")
        self._available_spks = sorted(registered)

        # Set default voice if current voice_name is not among available voices
        if self.voice_name not in self._available_spks and self._available_spks:
            self.voice_name = "exo_default" if "exo_default" in self._available_spks else self._available_spks[0]
        logger.info("Active voice: '%s' | Available: %s", self.voice_name, self._available_spks)

        # CUDA optimizations
        if torch.cuda.is_available():
            torch.backends.cudnn.benchmark = True
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            torch.set_float32_matmul_precision("high")

            # Pre-allocate CUDA context to avoid first-call overhead
            logger.info("CUDA pre-allocation …")
            t0 = time.monotonic()
            _a = torch.randn((4096, 4096), device="cuda")
            _b = torch.randn((4096, 4096), device="cuda")
            _ = _a @ _b
            del _a, _b
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            self._profile["cuda_prealloc_ms"] = (time.monotonic() - t0) * 1000
            logger.info("CUDA pre-allocation done in %.0f ms", self._profile["cuda_prealloc_ms"])

        # ── Phase 3: WARMUP ──
        self._set_phase(self.PHASE_WARMUP)
        self._warmup_gpu()
        self._warmup_streaming()
        self._warmup_audio()

        # Ensure all CUDA operations from warmup are complete
        if torch.cuda.is_available():
            torch.cuda.synchronize()

        self._loaded = True

        # ── Phase 4: ONLINE ──
        self._profile["total_ms"] = (time.monotonic() - t_total) * 1000
        self._set_phase(self.PHASE_ONLINE)

        logger.info(
            "CosyVoice2 ready — device=%s, voice=%s, lang=%s, speakers=%d",
            self.device, self.voice_name, self.language, len(self._available_spks),
        )
        if str(self.device).startswith("cuda"):
            logger.info("[TTS] CosyVoice2 backend: CUDA (RTX 3070)")
            logger.info("[GPU] TTS: CUDA → RTX 3070 (OK)")

        # Profiling report
        logger.info("═══ TTS STARTUP PROFILE ═══")
        for k, v in self._profile.items():
            logger.info("  %-25s %7.0f ms", k, v)
        logger.info("═══════════════════════════")

    # ------------------------------------------------------------------
    # Voice prompt resolution
    # ------------------------------------------------------------------
    def _resolve_voice_prompt(self) -> None:
        """Find the voice prompt WAV file for zero-shot / cross-lingual inference.

        Loads voices from:
          1. ``<model_dir>/voices/voices_metadata.json`` — multiple named voices
          2. ``<model_dir>/prompt.wav`` — legacy single prompt fallback
        """
        model_dir = os.environ.get(
            "EXO_COSYVOICE_MODELS",
            r"D:\EXO\models\cosyvoice_fr",
        )
        voices_dir = os.path.join(model_dir, "voices")

        # ── 1. Load all voices from voices/ directory ──
        self._voice_prompts: dict[str, dict] = {}  # name → {"wav": path, "prompt_text": str}
        self.voices = {}
        self._voice_aliases = {}
        self._voice_order = []

        # Preferred registry format for EXO FR voices.
        registry_path = os.path.join(model_dir, "voices.json")
        if os.path.isfile(registry_path):
            try:
                with open(registry_path, "r", encoding="utf-8") as f:
                    registry = json.load(f)
                if isinstance(registry, list):
                    for item in registry:
                        if not isinstance(item, dict):
                            continue
                        vid = str(item.get("id", "")).strip()
                        wav_file = str(item.get("file", "")).strip()
                        if not vid or not wav_file:
                            continue
                        wav_path = wav_file if os.path.isabs(wav_file) else os.path.join(voices_dir, wav_file)
                        if not os.path.isfile(wav_path):
                            logger.warning("voices.json entry ignored (missing wav): %s -> %s", vid, wav_path)
                            continue
                        entry = {
                            "wav": wav_path,
                            "prompt_text": item.get("prompt_text", ""),
                            "name": item.get("name", vid),
                            "model": item.get("model", "cosyvoice2"),
                            "speaker_embedding": "",
                        }
                        emb_rel = str(item.get("speaker_embedding", "")).strip()
                        if emb_rel:
                            emb_abs = emb_rel if os.path.isabs(emb_rel) else os.path.join(model_dir, emb_rel)
                            entry["speaker_embedding"] = emb_abs
                            if not os.path.isfile(emb_abs):
                                logger.warning("Missing speaker embedding for %s: %s", vid, emb_abs)
                        self._voice_prompts[vid] = entry
                        self.voices[vid] = dict(entry)
                        self._voice_order.append(vid)

                        # Optional compatibility alias (e.g. fr_denise -> fr_female_01)
                        legacy = str(item.get("legacy_id", "")).strip()
                        if legacy and legacy not in self._voice_aliases:
                            self._voice_aliases[legacy] = vid

                        # File stem alias for direct requests like "fr_henri".
                        stem = Path(wav_file).stem
                        if stem and stem not in self._voice_aliases:
                            self._voice_aliases[stem] = vid

                    logger.info("Loaded %d voice(s) from %s", len(self._voice_prompts), registry_path)
            except Exception as exc:
                logger.warning("Failed to load voices.json: %s", exc)

        # Legacy metadata fallback (kept for compatibility).
        meta_path = os.path.join(voices_dir, "voices_metadata.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                for name, info in meta.items():
                    wav_path = os.path.join(voices_dir, info["file"])
                    if os.path.isfile(wav_path) and name not in self._voice_prompts:
                        self._voice_prompts[name] = {
                            "wav": wav_path,
                            "prompt_text": info.get("prompt_text", ""),
                            "name": name,
                            "model": "cosyvoice2",
                            "speaker_embedding": "",
                        }
                        if name not in self._voice_order:
                            self._voice_order.append(name)
                        logger.info("Voice prompt loaded: %s → %s", name, wav_path)
                logger.info("Loaded %d total voice(s) from metadata/registry", len(self._voice_prompts))
            except Exception as exc:
                logger.warning("Failed to load voices metadata: %s", exc)

        # Also discover any *.wav in voices/ not listed in metadata
        if os.path.isdir(voices_dir):
            for fname in os.listdir(voices_dir):
                if fname.endswith(".wav"):
                    stem = os.path.splitext(fname)[0]
                    if stem not in self._voice_prompts:
                        self._voice_prompts[stem] = {
                            "wav": os.path.join(voices_dir, fname),
                            "prompt_text": "",
                            "name": stem,
                            "model": "cosyvoice2",
                            "speaker_embedding": "",
                        }
                        self._voice_order.append(stem)
                        logger.info("Voice prompt discovered: %s → %s", stem, fname)

        # ── 2. Legacy fallback: single prompt.wav in model root ──
        candidates = [
            os.path.join(model_dir, "prompt.wav"),
            os.path.join(model_dir, f"{self.voice_name}.wav"),
            os.path.join(model_dir, "voice_prompt.wav"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                self._prompt_wav = c
                logger.info("Default voice prompt found: %s", c)
                break

        if self._prompt_wav is None and self._voice_prompts:
            # Use the first available voice as default
            first_voice = next(iter(self._voice_prompts))
            self._prompt_wav = self._voice_prompts[first_voice]["wav"]
            self._prompt_text = self._voice_prompts[first_voice].get("prompt_text", "")
            logger.info("Using first voice '%s' as default prompt", first_voice)

        if self._prompt_wav is None:
            logger.info("No voice prompt WAV found — will use SFT mode if speakers available")

        # Default prompt text for zero-shot (must match prompt.wav content)
        if not self._prompt_text:
            self._prompt_text = "Bonjour, je suis votre assistant vocal EXO. Je suis là pour vous aider."

    # ------------------------------------------------------------------
    # Phase management
    # ------------------------------------------------------------------
    def _set_phase(self, phase: str) -> None:
        self.phase = phase
        logger.info("[Readiness] Phase → %s", phase)
        if self._phase_callback:
            try:
                self._phase_callback(phase)
            except Exception:
                logger.warning("Phase callback failed for %s", phase, exc_info=True)

    # ------------------------------------------------------------------
    # Warmup
    # ------------------------------------------------------------------
    def _warmup_gpu(self) -> None:
        """Warm up GPU with a short inference pass."""
        if str(self.device) == "cpu" or self.model is None:
            return
        t0 = time.monotonic()
        try:
            logger.info("GPU warm-up (CosyVoice2) …")
            for _ in self._inference_internal("Bonjour.", stream=False):
                pass
            torch.cuda.synchronize()
            self._profile["gpu_warmup_ms"] = (time.monotonic() - t0) * 1000
            logger.info("GPU warm-up done in %.0f ms", self._profile["gpu_warmup_ms"])
        except Exception as exc:
            logger.warning("GPU warm-up failed: %s", exc)
            self._profile["gpu_warmup_ms"] = (time.monotonic() - t0) * 1000

    def _warmup_streaming(self) -> None:
        """Warm up the streaming inference path."""
        if str(self.device) == "cpu" or self.model is None:
            return
        t0 = time.monotonic()
        try:
            logger.info("Streaming warm-up (CosyVoice2) …")
            for _ in self._inference_internal("Bonjour.", stream=True):
                break  # first chunk enough
            torch.cuda.synchronize()
            self._profile["streaming_warmup_ms"] = (time.monotonic() - t0) * 1000
            logger.info("Streaming warm-up done in %.0f ms", self._profile["streaming_warmup_ms"])
        except Exception as exc:
            logger.warning("Streaming warm-up failed: %s", exc)

    def _warmup_audio(self) -> None:
        """Generate silence PCM16 to prime the audio conversion pipeline."""
        t0 = time.monotonic()
        # 300 ms silence at 24 kHz
        n_samples = int(OUTPUT_SAMPLE_RATE * 0.3)
        silence = np.zeros(n_samples, dtype=np.float32)
        pcm = np.clip(silence * 32767, -32768, 32767).astype(np.int16)
        self._silence_pcm = pcm.tobytes()
        del pcm, silence
        self._profile["audio_warmup_ms"] = (time.monotonic() - t0) * 1000
        logger.info("Audio warmup done (%.0f ms, %d bytes silence)",
                     self._profile["audio_warmup_ms"], len(self._silence_pcm))

    def warmup(self) -> None:
        """Public warmup entry point."""
        self._warmup_gpu()
        self._warmup_streaming()
        self._warmup_audio()

    # ------------------------------------------------------------------
    # Text normalization and sentence splitting
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_text(text: str) -> str:
        """Light text normalization for TTS input."""
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        # Remove control characters (keep all printable unicode)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        return text.strip()

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split text into sentences for incremental streaming.

        First sentence is sent ASAP to reduce first-chunk latency.
        """
        parts = re.split(r"(?<=[.!?])\s+", text)
        result = [p.strip() for p in parts if p.strip()]
        return result if result else [text]

    @staticmethod
    def _split_long_text(text: str, max_len: int) -> list[str]:
        """Split text into blocks of max_len chars, breaking at sentence boundaries."""
        if len(text) <= max_len:
            return [text]
        parts = re.split(r"(?<=[.!?])\s+", text)
        blocks: list[str] = []
        current = ""
        for p in parts:
            if current and len(current) + len(p) + 1 > max_len:
                blocks.append(current.strip())
                current = p
            else:
                current = (current + " " + p).strip() if current else p
        if current.strip():
            blocks.append(current.strip())
        return blocks if blocks else [text]

    # ------------------------------------------------------------------
    # Voice / language management
    # ------------------------------------------------------------------
    def set_voice(self, voice: str) -> bool:
        """Switch voice. Returns True if voice exists."""
        voice = self._voice_aliases.get(voice, voice)
        if voice in self._available_spks:
            self.voice_name = voice
            # Update prompt_wav if this voice has a dedicated prompt
            vp = getattr(self, "_voice_prompts", {})
            if voice in vp:
                self._prompt_wav = vp[voice]["wav"]
            logger.info("Voice set to: %s (registered speaker)", voice)
            return True
        # Voice declared in voices/ dir but not in model's SFT speaker list
        # (add_zero_shot_spk may not have updated list_available_spks)
        vp = getattr(self, "_voice_prompts", {})
        if voice in vp:
            self.voice_name = voice
            self._prompt_wav = vp[voice]["wav"]
            logger.info("Voice set to: %s (voice_prompts entry, raw wav path)", voice)
            return True
        # Check for a matching prompt wav in voices/ directory
        model_dir = os.environ.get(
            "EXO_COSYVOICE_MODELS",
            r"D:\EXO\models\cosyvoice_fr",
        )
        for check_dir in [os.path.join(model_dir, "voices"), model_dir]:
            wav_path = os.path.join(check_dir, f"{voice}.wav")
            if os.path.isfile(wav_path):
                self.voice_name = voice
                self._prompt_wav = wav_path
                logger.info("Voice set to: %s (zero-shot prompt from %s)", voice, check_dir)
                return True
        # Case-insensitive fallback
        for spk in self._available_spks:
            if spk.lower() == voice.lower():
                return self.set_voice(spk)
        logger.warning("Speaker '%s' not found, keeping '%s'", voice, self.voice_name)
        return False

    def set_language(self, lang: str) -> None:
        self.language = lang
        logger.info("Language set to: %s", lang)

    def list_voices(self) -> list[str]:
        """Return ALL declared voices: registered SFT speakers + zero-shot from voices/ dir.

        CosyVoice2's ``list_available_spks()`` only returns SFT speakers baked into
        the model checkpoint; zero-shot speakers added via ``add_zero_shot_spk()``
        are stored in a separate internal dict and may NOT appear in that list.
        We therefore merge both sources so the GUI always shows all 5 French voices.
        """
        ordered: list[str] = []
        for v in getattr(self, "_voice_order", []):
            if v not in ordered:
                ordered.append(v)

        # Keep compatibility with runtime speakers if not declared in registry.
        for v in self._available_spks:
            if v not in ordered and (v.startswith("fr_") or v == "exo_default"):
                ordered.append(v)

        if self._prompt_wav and os.path.isfile(self._prompt_wav) and "exo_default" not in ordered:
            ordered.append("exo_default")

        return ordered

    # ------------------------------------------------------------------
    # Internal inference dispatcher
    # ------------------------------------------------------------------
    def _inference_internal(self, text: str, stream: bool = True, speed: float = 1.0):
        """Dispatch to the appropriate CosyVoice2 inference method.

        Priority:
          1. Registered zero-shot speaker (cached embeddings in model) — fastest
          2. Voice declared in voices/ dir but not in model's SFT list — raw wav path
          3. Default prompt.wav fallback
        Uses inference_zero_shot (with prompt_text) so the model knows the voice
        language, producing authentic French phonetics instead of English-accented output.
        Yields dicts with 'tts_speech' tensor key (shape [1, N]).
        """
        vp = getattr(self, "_voice_prompts", {})
        spk_store = getattr(getattr(self.model, "frontend", None), "spk2info", {})
        with torch.inference_mode():
            if self.voice_name and self.voice_name in spk_store:
                # Registered zero-shot speaker with cached embeddings.
                # Use inference_zero_shot + prompt_text so the language model
                # knows the reference voice is French (prevents English accent).
                vp_entry = vp.get(self.voice_name, {})
                pt = vp_entry.get("prompt_text", "") or self._prompt_text
                pw = vp_entry.get("wav", "") or self._prompt_wav or ""
                if pt:
                    yield from self.model.inference_zero_shot(
                        tts_text=text,
                        prompt_text=pt,
                        prompt_wav=pw,
                        zero_shot_spk_id=self.voice_name,
                        stream=stream,
                        speed=speed,
                    )
                else:
                    yield from self.model.inference_cross_lingual(
                        tts_text=text,
                        prompt_wav=pw,
                        zero_shot_spk_id=self.voice_name,
                        stream=stream,
                        speed=speed,
                    )
            elif self.voice_name in vp:
                # Voice declared in voices/ but NOT in model's internal speaker dict.
                wav_path = vp[self.voice_name]["wav"]
                pt = vp[self.voice_name].get("prompt_text", "")
                if pt:
                    yield from self.model.inference_zero_shot(
                        tts_text=text,
                        prompt_text=pt,
                        prompt_wav=wav_path,
                        stream=stream,
                        speed=speed,
                    )
                else:
                    yield from self.model.inference_cross_lingual(
                        tts_text=text,
                        prompt_wav=wav_path,
                        stream=stream,
                        speed=speed,
                    )
            elif self._prompt_wav and os.path.isfile(self._prompt_wav):
                if self._prompt_text:
                    yield from self.model.inference_zero_shot(
                        tts_text=text,
                        prompt_text=self._prompt_text,
                        prompt_wav=self._prompt_wav,
                        stream=stream,
                        speed=speed,
                    )
                else:
                    yield from self.model.inference_cross_lingual(
                        tts_text=text,
                        prompt_wav=self._prompt_wav,
                        stream=stream,
                        speed=speed,
                    )
            else:
                raise RuntimeError(
                    "No voice prompt WAV and no speakers available. "
                    "Place a prompt.wav in the model directory."
                )

    # ------------------------------------------------------------------
    # Dedicated streaming inference (zero-shot speaker)
    # ------------------------------------------------------------------
    def infer_stream(self, text: str, speaker_id: str = "exo_default", speed: float = 1.0):
        """Streaming inference via inference_zero_shot for zero-shot speakers.

        Yields dicts with 'tts_speech' tensor key (shape [1, N]).
        Uses inference_zero_shot with prompt_text when available so the model
        correctly identifies the reference voice language (French).
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")
        vp = getattr(self, "_voice_prompts", {})
        spk_store = getattr(getattr(self.model, "frontend", None), "spk2info", {})
        with torch.inference_mode():
            if speaker_id in spk_store:
                vp_entry = vp.get(speaker_id, {})
                pt = vp_entry.get("prompt_text", "") or self._prompt_text
                pw = vp_entry.get("wav", "") or self._prompt_wav or ""
                if pt:
                    yield from self.model.inference_zero_shot(
                        tts_text=text,
                        prompt_text=pt,
                        prompt_wav=pw,
                        zero_shot_spk_id=speaker_id,
                        stream=True,
                        speed=speed,
                    )
                else:
                    yield from self.model.inference_cross_lingual(
                        tts_text=text,
                        prompt_wav=pw,
                        zero_shot_spk_id=speaker_id,
                        stream=True,
                        speed=speed,
                    )
            elif speaker_id in vp:
                pt = vp[speaker_id].get("prompt_text", "")
                pw = vp[speaker_id]["wav"]
                if pt:
                    yield from self.model.inference_zero_shot(
                        tts_text=text,
                        prompt_text=pt,
                        prompt_wav=pw,
                        stream=True,
                        speed=speed,
                    )
                else:
                    yield from self.model.inference_cross_lingual(
                        tts_text=text,
                        prompt_wav=pw,
                        stream=True,
                        speed=speed,
                    )
            elif self._prompt_wav and os.path.isfile(self._prompt_wav):
                if self._prompt_text:
                    yield from self.model.inference_zero_shot(
                        tts_text=text,
                        prompt_text=self._prompt_text,
                        prompt_wav=self._prompt_wav,
                        stream=True,
                        speed=speed,
                    )
                else:
                    yield from self.model.inference_cross_lingual(
                        tts_text=text,
                        prompt_wav=self._prompt_wav,
                        stream=True,
                        speed=speed,
                    )
            else:
                raise RuntimeError(
                    "No speaker or prompt WAV available for streaming inference"
                )

    # ------------------------------------------------------------------
    # Tensor → PCM16 bytes conversion
    # ------------------------------------------------------------------
    @staticmethod
    def _tensor_to_pcm16(speech_tensor: torch.Tensor, target_sr: int = OUTPUT_SAMPLE_RATE) -> bytes:
        """Convert a CosyVoice speech tensor to PCM16 bytes at target sample rate."""
        wav = speech_tensor.squeeze()
        if wav.dim() == 0 or wav.numel() == 0:
            return b""
        # GPU-side: normalize + scale + clamp → int16, then transfer
        peak = wav.abs().max()
        if peak > 1.0:
            wav = wav / peak
        pcm = torch.clamp(wav * 32767, -32768, 32767).to(torch.int16).cpu().numpy()
        return pcm.tobytes()

    @staticmethod
    def _resample(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
        """Linear interpolation resampling."""
        if src_rate == dst_rate:
            return samples
        ratio = dst_rate / src_rate
        n_out = int(len(samples) * ratio)
        indices = np.arange(n_out) / ratio
        indices = np.clip(indices, 0, len(samples) - 1)
        idx_floor = indices.astype(np.int64)
        idx_ceil = np.minimum(idx_floor + 1, len(samples) - 1)
        frac = (indices - idx_floor).astype(np.float32)
        return samples[idx_floor] * (1 - frac) + samples[idx_ceil] * frac

    # ------------------------------------------------------------------
    # Public synthesis API
    # ------------------------------------------------------------------
    def synthesize_stream(
        self,
        text: str,
        voice: Optional[str] = None,
        lang: Optional[str] = None,
        rate: float = 1.0,
    ):
        """Streaming synthesis: yield PCM16 byte chunks as CosyVoice2 generates them.

        Each yielded chunk is raw PCM16 bytes at OUTPUT_SAMPLE_RATE.
        Splits text into sentences — first sentence streamed ASAP
        to minimize first-chunk latency.
        """
        if not self._loaded or self.model is None:
            raise RuntimeError("Model not loaded")
        if not text or not text.strip():
            return

        # Apply per-request voice/language overrides when provided.
        # This keeps GUI selection effective even when clients only send
        # synthesize requests (without a separate set_voice message).
        if voice:
            self.set_voice(voice)
        if lang:
            self.set_language(lang)

        # Normalize and split into sentences for faster first-chunk
        text = self._normalize_text(text)
        if not text:
            return

        # ── Latency-optimized mode ──
        # Keep first sentence isolated to minimize first-chunk latency,
        # then merge remaining text into larger blocks to reduce tail overhead.
        if self.latency_optimized:
            raw_sentences = self._split_sentences(text)
            if len(raw_sentences) <= 1:
                sentences = self._split_long_text(text, self.max_chunk_length)
            else:
                first = raw_sentences[0]
                rest = " ".join(raw_sentences[1:]).strip()
                tail_blocks = self._split_long_text(rest, self.max_chunk_length) if rest else []
                sentences = [first] + tail_blocks
            logger.info(
                "[Latency] latency_optimized=ON → %d block(s) for %d chars",
                len(sentences), len(text),
            )
        else:
            sentences = self._split_sentences(text)

        t0 = time.monotonic()
        chunk_idx = 0
        native_sr = getattr(self.model, "sample_rate", COSYVOICE_SAMPLE_RATE)
        if not getattr(self, "_streaming_log_emitted", False):
            logger.info("[FR] Streaming CosyVoice2 activé (inference_stream)")
            self._streaming_log_emitted = True

        try:
            with torch.inference_mode():
                for sent_idx, sentence in enumerate(sentences):
                    for output in self._inference_internal(sentence, stream=True, speed=rate):
                        speech = output.get("tts_speech")
                        if speech is None:
                            continue

                        wav = speech.squeeze()
                        if wav.numel() == 0:
                            continue

                        # Optimized tensor → PCM16 conversion
                        if native_sr != OUTPUT_SAMPLE_RATE:
                            # Resample path: requires numpy intermediate
                            wav_np = wav.float().cpu().numpy()
                            wav_np = self._resample(wav_np, native_sr, OUTPUT_SAMPLE_RATE)
                            peak = np.max(np.abs(wav_np))
                            if peak > 1.0:
                                wav_np = wav_np / peak
                            pcm_int16 = np.clip(wav_np * 32767, -32768, 32767).astype(np.int16)
                        else:
                            # Fast path: scale + clamp on GPU, transfer as int16
                            # (halves PCIe bandwidth vs float32)
                            peak = wav.abs().max()
                            if peak > 1.0:
                                wav = wav / peak
                            pcm_int16 = torch.clamp(
                                wav * 32767, -32768, 32767
                            ).to(torch.int16).cpu().numpy()

                        pcm_bytes = pcm_int16.tobytes()

                        if chunk_idx == 0:
                            first_chunk_ms = (time.monotonic() - t0) * 1000
                            logger.info(
                                "[Latency] TTS first-chunk: %.0f ms (%d bytes) "
                                "sent=%d/%d text=%s",
                                first_chunk_ms, len(pcm_bytes),
                                sent_idx + 1, len(sentences), sentences[0][:50],
                            )
                            if first_chunk_ms > 600:
                                logger.warning(
                                    "[Latency] TTS first-chunk slow (%.0f ms > 600 ms)",
                                    first_chunk_ms,
                                )

                        chunk_idx += 1
                        yield pcm_bytes

        except Exception as exc:
            logger.error("CosyVoice2 streaming error: %s", exc)
            if chunk_idx == 0:
                # Fallback to non-streaming
                full_pcm = self.synthesize(text, voice, lang, rate)
                if full_pcm:
                    yield full_pcm
                return

        dt = time.monotonic() - t0
        self._last_synth_time = time.monotonic()
        logger.info(
            "[STREAM] done: %d chunks, %d sentences in %.2fs text=%s",
            chunk_idx, len(sentences), dt, text[:50],
        )

    def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        lang: Optional[str] = None,
        rate: float = 1.0,
        pitch: float = 1.0,
    ) -> bytes:
        """Full (non-streaming) synthesis returning complete PCM16 bytes."""
        if not self._loaded or self.model is None:
            raise RuntimeError("Model not loaded")
        if not text or not text.strip():
            return b""

        t0 = time.monotonic()
        native_sr = getattr(self.model, "sample_rate", COSYVOICE_SAMPLE_RATE)
        all_pcm = bytearray()

        with torch.inference_mode():
            for output in self._inference_internal(text, stream=False, speed=rate):
                speech = output.get("tts_speech")
                if speech is None:
                    continue
                wav = speech.squeeze()
                if wav.numel() == 0:
                    continue
                if native_sr != OUTPUT_SAMPLE_RATE:
                    wav_np = wav.float().cpu().numpy()
                    wav_np = self._resample(wav_np, native_sr, OUTPUT_SAMPLE_RATE)
                    peak = np.max(np.abs(wav_np))
                    if peak > 1.0:
                        wav_np = wav_np / peak
                    pcm_int16 = np.clip(wav_np * 32767, -32768, 32767).astype(np.int16)
                else:
                    # GPU-side: scale + clamp → int16, halves transfer bandwidth
                    peak = wav.abs().max()
                    if peak > 1.0:
                        wav = wav / peak
                    pcm_int16 = torch.clamp(
                        wav * 32767, -32768, 32767
                    ).to(torch.int16).cpu().numpy()
                all_pcm.extend(pcm_int16.tobytes())

        dt = time.monotonic() - t0
        duration = len(all_pcm) / (OUTPUT_SAMPLE_RATE * 2)
        logger.info(
            "CosyVoice2 synthesized %.1fs audio in %.2fs (RTF=%.2f) text=%s",
            duration, dt, dt / max(duration, 0.01), text[:60],
        )
        self._last_synth_time = time.monotonic()
        return bytes(all_pcm)
