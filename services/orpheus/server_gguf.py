"""Orpheus 3B FR (GGUF Q8_0) — serveur FastAPI TTS via llama.cpp + SNAC.

Pipeline :
    text -> llama-cpp-python (GGUF) -> tokens "<custom_token_N>" -> SNAC 24 kHz -> WAV.

Endpoints :
    POST /tts      JSON { text, voice?, speed? } -> { audio_b64, sample_rate, duration_s, rtf, voice }
    GET  /health   -> { status, cuda, gpu, model_loaded, sample_rate, default_voice }
    GET  /voices   -> { voices: [...] }

Variables d'environnement utilisables :
    ORPHEUS_GGUF_PATH       chemin du .gguf (defaut: D:\\EXO\\models\\orpheus_fr_gguf\\Orpheus-3b-French-FT-Q8_0.gguf)
    ORPHEUS_N_CTX           taille de contexte (defaut: 4096)
    ORPHEUS_N_GPU_LAYERS    nb couches GPU (-1 = toutes, defaut: -1)
    ORPHEUS_DEFAULT_VOICE   voix par defaut (defaut: pierre)

Format prompt (Lex-au / canopylabs) :
    "<|audio|>{voice}: {text}<|eot_id|>"
Le modele genere des tokens stringifies "<custom_token_N>" qui encodent
7 codebooks SNAC entrelaces.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import time
from pathlib import Path
from typing import List, Optional

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Orpheus] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("orpheus")

CUSTOM_TOKEN_PREFIX = "<custom_token_"
SAMPLE_RATE = 24000
N_CODEBOOKS = 7

VOICES_FR_DEFAULT = ["pierre", "amelie", "marie"]

# Tokens d'arret (definis par Orpheus / canopylabs)
STOP_TOKEN_STRINGS = ["<|eot_id|>", "<|audio_end|>"]


# ---------------------------------------------------------------------------
# Etat global
# ---------------------------------------------------------------------------
class _State:
    llm = None              # llama_cpp.Llama
    snac = None             # snac.SNAC
    snac_device = "cpu"
    voices: List[str] = list(VOICES_FR_DEFAULT)
    default_voice: str = "pierre"
    active_model_path: Optional[str] = None  # J5 : chemin du .gguf actif


STATE = _State()


# ---------------------------------------------------------------------------
# J5 (2026-05-14) : selection dynamique du meilleur modele Orpheus apres bench
# ---------------------------------------------------------------------------
# Le bench `services/orpheus/bench_quants.py` produit un JSON
# `bench_quants_results.json` contenant pour chaque quantification testee :
#   { "model": "Q8_0" | "Q6_K" | "Q5_K_M" | ..., "rtf": float,
#     "first_chunk": float (ms), "vram": float (GB), "quality_ok": bool }
# select_best_model() lit ce JSON et renvoie le chemin .gguf du meilleur
# candidat selon les criteres (RTF<1.20, first_chunk<450ms, qualite OK,
# VRAM<=6.5GB). Sans bench valide -> renvoie None (caller fallback Q8_0).
# Aucun telechargement automatique n'est effectue : seuls les .gguf deja
# presents sur disque sont utilises.
DEFAULT_MODELS_DIR = Path(r"D:\EXO\models\orpheus_fr_gguf")
DEFAULT_GGUF = DEFAULT_MODELS_DIR / "Orpheus-3b-French-FT-Q8_0.gguf"
BENCH_RESULTS_JSON = Path(__file__).with_name("bench_quants_results.json")

# Criteres J5
SEL_MAX_RTF = 1.20
SEL_MAX_FIRST_MS = 450.0
SEL_MAX_VRAM_GB = 6.5


def _quant_to_path(quant: str, models_dir: Path = DEFAULT_MODELS_DIR) -> Path:
    return models_dir / f"Orpheus-3b-French-FT-{quant}.gguf"


def _valid_entry(d: object) -> bool:
    if not isinstance(d, dict):
        return False
    required = ("model", "rtf", "first_chunk", "vram", "quality_ok")
    if not all(k in d for k in required):
        return False
    try:
        float(d["rtf"]); float(d["first_chunk"]); float(d["vram"])
    except (TypeError, ValueError):
        return False
    return isinstance(d["model"], str) and isinstance(d["quality_ok"], bool)


def select_best_model(
    json_path: Path = BENCH_RESULTS_JSON,
    models_dir: Path = DEFAULT_MODELS_DIR,
) -> Optional[str]:
    """Retourne le chemin .gguf du meilleur modele selon les resultats du bench
    `bench_quants.py`. Renvoie None si aucun candidat valide (caller doit
    appliquer son propre fallback)."""
    if not json_path.is_file():
        log.info("[select] aucun bench JSON (%s) -> selection auto desactivee", json_path.name)
        return None
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("[select] JSON bench illisible (%s): %s", json_path.name, exc)
        return None

    entries = data.get("results") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        log.warning("[select] format JSON inattendu, attendu liste ou {results:[...]}")
        return None

    candidates = []
    for raw in entries:
        if not _valid_entry(raw):
            continue
        gguf = _quant_to_path(raw["model"], models_dir)
        if not gguf.is_file():
            continue  # modele absent du disque -> ignore
        candidates.append({
            "model": raw["model"],
            "rtf": float(raw["rtf"]),
            "first_chunk": float(raw["first_chunk"]),
            "vram": float(raw["vram"]),
            "quality_ok": bool(raw["quality_ok"]),
            "path": str(gguf),
        })

    if not candidates:
        log.info("[select] aucun candidat valide dans le bench")
        return None

    eligible = [
        c for c in candidates
        if c["rtf"] < SEL_MAX_RTF
        and c["first_chunk"] < SEL_MAX_FIRST_MS
        and c["quality_ok"]
        and c["vram"] <= SEL_MAX_VRAM_GB
    ]
    if not eligible:
        log.info(
            "[select] aucun modele ne satisfait tous les criteres "
            "(RTF<%.2f, first<%.0fms, quality_ok, VRAM<=%.1fGB)",
            SEL_MAX_RTF, SEL_MAX_FIRST_MS, SEL_MAX_VRAM_GB,
        )
        return None

    # Tri : RTF asc, puis first_chunk asc (plus rapide en cas d'egalite)
    eligible.sort(key=lambda c: (c["rtf"], c["first_chunk"]))
    best = eligible[0]
    log.info(
        "[select] meilleur candidat: %s (RTF=%.2f, first=%.0fms, VRAM=%.2fGB)",
        best["model"], best["rtf"], best["first_chunk"], best["vram"],
    )
    return best["path"]


def load_model(model_path: str) -> object:
    """Charge un GGUF via llama-cpp-python avec les params J1 et retourne
    l'instance Llama. Leve une exception en cas d'echec (le caller doit
    gerer le fallback)."""
    from llama_cpp import Llama
    n_ctx = int(os.environ.get("ORPHEUS_N_CTX", "4096"))
    n_gpu_layers = int(os.environ.get("ORPHEUS_N_GPU_LAYERS", "-1"))
    n_batch = int(os.environ.get("ORPHEUS_N_BATCH", "1024"))
    n_ubatch = int(os.environ.get("ORPHEUS_N_UBATCH", "512"))
    flash_attn = os.environ.get("ORPHEUS_FLASH_ATTN", "1").lower() not in ("0", "false", "no")
    offload_kqv = os.environ.get("ORPHEUS_OFFLOAD_KQV", "1").lower() not in ("0", "false", "no")
    t0 = time.time()
    llm = Llama(
        model_path=model_path,
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        n_batch=n_batch,
        n_ubatch=n_ubatch,
        flash_attn=flash_attn,
        offload_kqv=offload_kqv,
        verbose=False,
        logits_all=False,
    )
    log.info(
        "LLM charge en %.1fs (n_ctx=%d, gpu_layers=%d, n_batch=%d, n_ubatch=%d, "
        "flash_attn=%s, offload_kqv=%s)",
        time.time() - t0, n_ctx, n_gpu_layers, n_batch, n_ubatch, flash_attn, offload_kqv,
    )
    return llm


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------
def load_models() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA indisponible. Orpheus exige une GPU NVIDIA.")

    # J5 (2026-05-14) : selection dynamique du modele.
    # Priorite :
    #   1) ORPHEUS_GGUF_PATH explicite (override manuel) -> respecte
    #   2) bench_quants_results.json -> select_best_model()
    #   3) fallback Q8_0
    env_override = os.environ.get("ORPHEUS_GGUF_PATH", "").strip()
    source = "default"
    if env_override:
        gguf_path = env_override
        source = "env"
    else:
        selected = select_best_model()
        if selected:
            gguf_path = selected
            source = "bench"
        else:
            gguf_path = str(DEFAULT_GGUF)

    if not os.path.isfile(gguf_path):
        raise FileNotFoundError(f"GGUF introuvable : {gguf_path}")

    STATE.default_voice = os.environ.get("ORPHEUS_DEFAULT_VOICE", "pierre").strip().lower()

    log.info("CUDA: True | GPU: %s", torch.cuda.get_device_name(0))
    log.info("Chargement GGUF (%s) : %s", source, gguf_path)

    # J5 failsafe : si le modele selectionne via bench refuse de charger,
    # on retombe automatiquement sur Q8_0 sans interrompre le serveur.
    try:
        STATE.llm = load_model(gguf_path)
        STATE.active_model_path = gguf_path
    except Exception as exc:
        if source == "bench" and os.path.isfile(DEFAULT_GGUF):
            log.error("[Orpheus] echec chargement %s -> fallback Q8_0: %s", gguf_path, exc)
            STATE.llm = load_model(str(DEFAULT_GGUF))
            STATE.active_model_path = str(DEFAULT_GGUF)
            gguf_path = str(DEFAULT_GGUF)
        else:
            raise

    # Log d'activation au format demande J5
    quant = Path(gguf_path).stem.split("-")[-1]  # "Orpheus-3b-French-FT-Q6_K" -> "Q6_K"
    if source == "bench":
        # On peut reutiliser les metriques du bench pour le log d'activation
        try:
            data = json.loads(BENCH_RESULTS_JSON.read_text(encoding="utf-8"))
            entries = data.get("results") if isinstance(data, dict) else data
            for raw in entries or []:
                if _valid_entry(raw) and raw["model"] == quant:
                    log.info(
                        "[Orpheus] Activated model: %s (RTF=%.2f, first_chunk=%.0fms)",
                        quant, float(raw["rtf"]), float(raw["first_chunk"]),
                    )
                    break
        except Exception:
            log.info("[Orpheus] Activated model: %s", quant)
    else:
        log.info("[Orpheus] Activated model: %s (source=%s)", quant, source)


    from snac import SNAC

    t0 = time.time()
    STATE.snac_device = "cuda"
    STATE.snac = SNAC.from_pretrained("hubertsiuzdak/snac_24khz").eval().to(STATE.snac_device)
    log.info("SNAC charge en %.1fs sur %s", time.time() - t0, STATE.snac_device)

    # J3-bis (audit perf 2026-05-14) : pre-warm SNAC pour amortir l'init des
    # kernels CUDA (cuDNN convolutions, etc.). Sans cela, le 1er decode SNAC
    # de la 1re synthese paie ~50-120 ms d'init froide visible dans first_chunk.
    # On execute un decode "jouet" sur des codes valides (zeros) :
    # 3 codebooks SNAC, dimensions [1, n_frames * mult] avec mult=1,2,4.
    try:
        t_warm = time.time()
        with torch.inference_mode():
            warm_codes = [
                torch.zeros((1, 1), dtype=torch.int32, device=STATE.snac_device),
                torch.zeros((1, 2), dtype=torch.int32, device=STATE.snac_device),
                torch.zeros((1, 4), dtype=torch.int32, device=STATE.snac_device),
            ]
            _ = STATE.snac.decode(warm_codes)
            torch.cuda.synchronize()
        log.info("SNAC pre-warm OK (%.0f ms)", (time.time() - t_warm) * 1000)
    except Exception as e:
        log.warning("SNAC pre-warm KO (non-fatal) : %s", e)

    env_voices = os.environ.get("ORPHEUS_VOICES", "").strip()
    if env_voices:
        STATE.voices = [v.strip() for v in env_voices.split(",") if v.strip()]
    if STATE.default_voice not in STATE.voices:
        STATE.voices.insert(0, STATE.default_voice)

    log.info("Voix : %s (defaut=%s)", STATE.voices, STATE.default_voice)
    log.info("Orpheus pret. sample_rate=%d", SAMPLE_RATE)


# ---------------------------------------------------------------------------
# Decodage tokens audio
# ---------------------------------------------------------------------------
def _turn_token_into_id(token_string: str, index: int) -> Optional[int]:
    """Convertit '<custom_token_N>' en id audio decode (cf. Lex-au/Orpheus-FastAPI)."""
    if CUSTOM_TOKEN_PREFIX not in token_string:
        return None
    s = token_string.strip()
    last_start = s.rfind(CUSTOM_TOKEN_PREFIX)
    if last_start == -1:
        return None
    last = s[last_start:]
    if not (last.startswith(CUSTOM_TOKEN_PREFIX) and last.endswith(">")):
        return None
    try:
        n = int(last[len(CUSTOM_TOKEN_PREFIX):-1])
    except ValueError:
        return None
    return n - 10 - ((index % N_CODEBOOKS) * 4096)


def _decode_window(window_ids: List[int]) -> Optional[np.ndarray]:
    """Decode une fenetre de N*7 ids -> tenseur audio complet (slice centrale gardee par l'appelant)."""
    if len(window_ids) < N_CODEBOOKS:
        return None
    n_frames = len(window_ids) // N_CODEBOOKS
    frame = window_ids[: n_frames * N_CODEBOOKS]

    dev = STATE.snac_device
    # v6.0 perf audit (piste #3) : vectorisation de la dissemination des codes
    # SNAC. Avant : boucle Python + 7*n_frames assignements scalaires sur GPU
    # (autant de lancements de kernel + sync). Apres : 1 upload CPU->GPU + 3
    # gather indexes -> ~4 ops fusees, latence dominante des kernels eliminee.
    # Pour n_frames=4 (regime steady-state) : 28 ops -> 3 ops.
    ft = torch.as_tensor(frame, dtype=torch.int32, device=dev).view(n_frames, N_CODEBOOKS)
    codes_0 = ft[:, 0].contiguous()
    codes_1 = ft[:, [1, 4]].reshape(-1).contiguous()
    codes_2 = ft[:, [2, 3, 5, 6]].reshape(-1).contiguous()

    # Validation borne : un seul reduce min/max au lieu de 6 any() chaines.
    ft_min = int(ft.min().item())
    ft_max = int(ft.max().item())
    if ft_min < 0 or ft_max > 4096:
        return None

    codes = [codes_0.unsqueeze(0), codes_1.unsqueeze(0), codes_2.unsqueeze(0)]
    with torch.inference_mode():
        audio_hat = STATE.snac.decode(codes)
    return audio_hat  # tenseur [1, 1, T]


def _convert_frames_to_audio(frame_ids: List[int]) -> np.ndarray:
    """Decode tous les ids audio en utilisant la meme strategie de fenetre glissante
    que Orpheus-FastAPI (Lex-au) :
      - Fenetre de 28 tokens (4 frames), pas de 7 tokens (1 frame).
      - On garde la slice [2048:4096] de chaque decode (la "fenetre centrale", 2048 samples).
    Cela evite les artefacts de bord et reproduit le pipeline streaming en mode batch.
    """
    if not frame_ids:
        return np.zeros(0, dtype=np.float32)

    window_size = 28  # 4 frames
    step = 7          # 1 frame
    chunks: List[np.ndarray] = []

    # Premiere chunk : si on a au moins 7 tokens, decode-les pour amorcer
    if len(frame_ids) >= 7:
        first = _decode_window(frame_ids[:7])
        if first is not None:
            slice_len = first.shape[-1]
            # garde le 2eme tiers (fenetre centrale)
            seg = first[:, :, slice_len // 4 : slice_len // 2]
            chunks.append(seg.squeeze().detach().cpu().float().numpy())

    # Fenetres glissantes de 28 tokens, on garde [2048:4096]
    count = 7
    while count + step <= len(frame_ids):
        count += step
        if count < window_size:
            continue
        window = frame_ids[count - window_size : count]
        ah = _decode_window(window)
        if ah is None:
            continue
        # garde la fenetre centrale 2048 samples (slice [2048:4096])
        seg = ah[:, :, 2048:4096]
        chunks.append(seg.squeeze().detach().cpu().float().numpy())

    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def synthesize(text: str, voice: str, speed: float) -> np.ndarray:
    voice = (voice or STATE.default_voice).strip().lower()
    text_norm = text.strip().replace("\n", " ")
    prompt = f"<|audio|>{voice}: {text_norm}<|eot_id|>"

    # ~83 tokens audio par seconde de parole, plafond 30s (~2600 tokens)
    max_tokens = min(2600, max(400, int(len(text_norm) * 28)))

    log.info("synthese voice=%s len=%d max_tokens=%d", voice, len(text_norm), max_tokens)
    t0 = time.time()

    out = STATE.llm.create_completion(
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=0.6,
        top_p=0.9,
        repeat_penalty=1.1,
        stream=True,
        stop=STOP_TOKEN_STRINGS,
    )

    # Collecte des tokens audio
    audio_ids: List[int] = []
    index = 0
    raw_token_count = 0
    for chunk in out:
        choices = chunk.get("choices") or []
        if not choices:
            continue
        token_text = choices[0].get("text", "")
        if not token_text:
            continue
        # Un token llama.cpp peut contenir plusieurs '<custom_token_N>' colles
        # ou du texte entre eux. On split sur '>' et on remet le suffixe.
        for piece in token_text.split(">"):
            if not piece:
                continue
            piece_full = piece + ">"
            raw_token_count += 1
            tid = _turn_token_into_id(piece_full, index)
            if tid is not None and tid > 0:
                audio_ids.append(tid)
                index += 1

    gen_dt = time.time() - t0
    log.info("LLM termine : %d audio_ids / %d tokens bruts en %.2fs", len(audio_ids), raw_token_count, gen_dt)

    if not audio_ids:
        log.warning("Aucun token audio recu")
        return np.zeros(int(SAMPLE_RATE * 0.1), dtype=np.float32)

    wav = _convert_frames_to_audio(audio_ids)

    # Normalisation douce
    if wav.size:
        peak = float(np.max(np.abs(wav)))
        if peak > 1.0:
            wav = wav / peak

    # Resample temporel rudimentaire pour speed != 1.0
    if abs(speed - 1.0) > 1e-3 and wav.size > 0:
        n_out = max(1, int(len(wav) / speed))
        idx = (np.linspace(0, len(wav) - 1, n_out)).astype(np.int64)
        wav = wav[idx]
    return wav


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(title="Orpheus 3B FR TTS (GGUF)", version="2.0.0")


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    voice: Optional[str] = None
    speed: float = Field(1.0, ge=0.5, le=1.5)


class TTSResponse(BaseModel):
    audio_b64: str
    sample_rate: int
    duration_s: float
    rtf: float
    voice: str


@app.on_event("startup")
def _startup() -> None:
    load_models()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "cuda": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "model_loaded": STATE.llm is not None and STATE.snac is not None,
        "sample_rate": SAMPLE_RATE,
        "default_voice": STATE.default_voice,
    }


@app.get("/voices")
def voices() -> dict:
    return {"voices": STATE.voices, "default": STATE.default_voice}


@app.post("/tts", response_model=TTSResponse)
def tts(req: TTSRequest) -> TTSResponse:
    if STATE.llm is None or STATE.snac is None:
        raise HTTPException(status_code=503, detail="Modele non charge")
    t0 = time.time()
    try:
        wav = synthesize(req.text, req.voice or STATE.default_voice, req.speed)
    except Exception as e:
        log.exception("Erreur synthese")
        raise HTTPException(status_code=500, detail=f"Synth error: {e}")
    duration = float(wav.size) / SAMPLE_RATE if wav.size else 0.0
    elapsed = time.time() - t0
    rtf = (elapsed / duration) if duration > 0 else 0.0

    buf = io.BytesIO()
    sf.write(buf, wav, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    audio_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    log.info("/tts dur=%.2fs elapsed=%.2fs rtf=%.2f", duration, elapsed, rtf)

    return TTSResponse(
        audio_b64=audio_b64,
        sample_rate=SAMPLE_RATE,
        duration_s=duration,
        rtf=rtf,
        voice=(req.voice or STATE.default_voice).strip().lower(),
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("ORPHEUS_PORT", "8899"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
