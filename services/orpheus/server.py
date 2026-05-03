"""Orpheus 3B FR — serveur FastAPI TTS sur CUDA.

Pipeline :
    text -> Llama-3 3B (Orpheus FR) -> tokens audio -> SNAC 24 kHz -> WAV.

Endpoints :
    POST /tts      JSON { text, voice?, speed? } -> { audio_b64, sample_rate, duration_s }
    GET  /health   -> { status, cuda, gpu, model_loaded }
    GET  /voices   -> { voices: [...] }

Variables d'environnement utilisables :
    ORPHEUS_MODEL_ID   id HF (defaut: canopylabs/3b-fr-ft-research_release)
    ORPHEUS_MODEL_DIR  dossier local prioritaire (defaut: D:\\EXO\\models\\orpheus_fr)
    ORPHEUS_DTYPE      bfloat16 | float16 | float32 (defaut: bfloat16 si supporte)
    ORPHEUS_DEFAULT_VOICE   voix par defaut (defaut: pierre)
"""
from __future__ import annotations

import base64
import io
import logging
import os
import time
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


# ---------------------------------------------------------------------------
# Constantes Orpheus (format de tokens audio - cf. canopylabs/orpheus-tts)
# ---------------------------------------------------------------------------
# Le modele genere des tokens speciaux qui encodent les 7 codebooks SNAC
# entrelaces. Offsets verifies sur le checkpoint Orpheus 3B.
START_OF_HUMAN = 128259
END_OF_HUMAN = 128009
START_OF_AI = 128260
START_OF_SPEECH = 128261
END_OF_SPEECH = 128262
END_OF_AI = 128258
AUDIO_TOKEN_OFFSET = 128266  # premier token audio (codebook 0, index 0)
CODEBOOK_SIZE = 4096
N_CODEBOOKS = 7  # SNAC 24 kHz utilise une hierarchie 7 niveaux entrelaces

VOICES_FR_DEFAULT = ["pierre", "amelie", "marie"]


# ---------------------------------------------------------------------------
# Etat global
# ---------------------------------------------------------------------------
class _State:
    model = None
    tokenizer = None
    snac = None
    device: torch.device = torch.device("cpu")
    dtype: torch.dtype = torch.float32
    sample_rate: int = 24000
    voices: List[str] = list(VOICES_FR_DEFAULT)
    default_voice: str = "pierre"


STATE = _State()


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------
def _resolve_model_path() -> str:
    local = os.environ.get("ORPHEUS_MODEL_DIR", r"D:\EXO\models\orpheus_fr")
    if os.path.isdir(local) and os.listdir(local):
        return local
    return os.environ.get("ORPHEUS_MODEL_ID", "canopylabs/3b-fr-ft-research_release")


def _resolve_dtype() -> torch.dtype:
    pref = os.environ.get("ORPHEUS_DTYPE", "bfloat16").lower()
    if pref == "float32":
        return torch.float32
    if pref == "float16":
        return torch.float16
    if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
        return torch.bfloat16
    return torch.float16


def load_models() -> None:
    """Charge Orpheus (LM) + SNAC (codec) sur GPU."""
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA indisponible. Orpheus exige une GPU NVIDIA + torch CUDA. "
            "Installer torch via : pip install torch --index-url "
            "https://download.pytorch.org/whl/cu124"
        )

    STATE.device = torch.device("cuda")
    STATE.dtype = _resolve_dtype()
    STATE.default_voice = os.environ.get("ORPHEUS_DEFAULT_VOICE", "pierre").strip().lower()

    log.info("CUDA available: True")
    log.info("GPU: %s", torch.cuda.get_device_name(0))
    log.info("dtype: %s", STATE.dtype)

    from transformers import AutoModelForCausalLM, AutoTokenizer
    from snac import SNAC

    model_path = _resolve_model_path()
    log.info("Chargement Orpheus depuis: %s", model_path)

    t0 = time.time()
    STATE.tokenizer = AutoTokenizer.from_pretrained(model_path)
    STATE.model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=STATE.dtype,
        low_cpu_mem_usage=True,
    ).to(STATE.device)
    STATE.model.eval()
    log.info("LM charge en %.1fs", time.time() - t0)

    t0 = time.time()
    log.info("Chargement SNAC 24 kHz...")
    STATE.snac = SNAC.from_pretrained("hubertsiuzdak/snac_24khz").eval().to(STATE.device)
    log.info("SNAC charge en %.1fs", time.time() - t0)

    # Voix : on prend les valeurs de la variable d'env si fournies,
    # sinon defaut FR connu.
    env_voices = os.environ.get("ORPHEUS_VOICES", "").strip()
    if env_voices:
        STATE.voices = [v.strip() for v in env_voices.split(",") if v.strip()]
    if STATE.default_voice not in STATE.voices:
        STATE.voices.insert(0, STATE.default_voice)

    log.info("Voix disponibles: %s (defaut=%s)", STATE.voices, STATE.default_voice)
    log.info("Orpheus pret. sample_rate=%d", STATE.sample_rate)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def _build_prompt(text: str, voice: str) -> torch.Tensor:
    """Construit la sequence de tokens d'entree au format Orpheus.

    Format observe (canopylabs/orpheus-tts) :
        [SOH] <voice>: <text> [EOH][SOAI][SOSP]
    Le modele continue avec les tokens audio jusqu'au [EOSP].
    """
    text_norm = text.strip().replace("\n", " ")
    if voice:
        prompt_text = f"{voice}: {text_norm}"
    else:
        prompt_text = text_norm

    tok = STATE.tokenizer(prompt_text, return_tensors="pt", add_special_tokens=False)
    text_ids = tok.input_ids[0].tolist()

    seq = (
        [START_OF_HUMAN]
        + text_ids
        + [END_OF_HUMAN, START_OF_AI, START_OF_SPEECH]
    )
    return torch.tensor([seq], dtype=torch.long, device=STATE.device)


def _decode_audio_tokens(generated_ids: torch.Tensor) -> np.ndarray:
    """Extrait les tokens audio puis les decode via SNAC."""
    ids = generated_ids[0].tolist()

    # Cherche la zone entre START_OF_SPEECH et END_OF_SPEECH (ou fin)
    try:
        start = ids.index(START_OF_SPEECH) + 1
    except ValueError:
        start = 0
    end = len(ids)
    for tok in (END_OF_SPEECH, END_OF_AI, STATE.tokenizer.eos_token_id):
        if tok is None:
            continue
        try:
            idx = ids.index(tok, start)
            end = min(end, idx)
        except ValueError:
            pass

    audio_ids = ids[start:end]

    # Filtre : ne garde que les tokens dans la plage audio
    audio_ids = [
        t for t in audio_ids
        if AUDIO_TOKEN_OFFSET <= t < AUDIO_TOKEN_OFFSET + N_CODEBOOKS * CODEBOOK_SIZE
    ]
    # Doit etre multiple de 7 (un frame complet)
    n_frames = len(audio_ids) // N_CODEBOOKS
    if n_frames == 0:
        log.warning("Aucun frame audio decodable (texte vide ou generation tronquee)")
        return np.zeros(int(STATE.sample_rate * 0.1), dtype=np.float32)
    audio_ids = audio_ids[: n_frames * N_CODEBOOKS]

    # SNAC attend 3 codebooks (hierarchie) extraits des 7 tokens entrelaces
    # selon l'ordre Orpheus : [c0, c1, c2, c3, c4, c5, c6] par frame.
    # Mapping standard Orpheus -> SNAC :
    #   layer_0 (coarse) <- c0
    #   layer_1 (mid)    <- [c1, c4]
    #   layer_2 (fine)   <- [c2, c3, c5, c6]
    c = np.array(audio_ids, dtype=np.int64).reshape(n_frames, N_CODEBOOKS)
    c -= AUDIO_TOKEN_OFFSET
    # Retire l'offset de codebook (chaque codebook occupe sa propre tranche)
    for k in range(N_CODEBOOKS):
        c[:, k] -= k * CODEBOOK_SIZE
    c = np.clip(c, 0, CODEBOOK_SIZE - 1)

    layer_0 = torch.tensor(c[:, 0], dtype=torch.long, device=STATE.device).unsqueeze(0)
    layer_1 = torch.tensor(c[:, [1, 4]].reshape(-1), dtype=torch.long, device=STATE.device).unsqueeze(0)
    layer_2 = torch.tensor(c[:, [2, 3, 5, 6]].reshape(-1), dtype=torch.long, device=STATE.device).unsqueeze(0)

    with torch.inference_mode():
        wav = STATE.snac.decode([layer_0, layer_1, layer_2])
    wav = wav.squeeze().detach().cpu().float().numpy()
    # Normalisation douce
    peak = float(np.max(np.abs(wav))) if wav.size else 1.0
    if peak > 1.0:
        wav = wav / peak
    return wav.astype(np.float32)


@torch.inference_mode()
def synthesize(text: str, voice: str, speed: float) -> np.ndarray:
    voice = (voice or STATE.default_voice).strip().lower()
    input_ids = _build_prompt(text, voice)

    # Estimation generee : ~83 tokens audio par seconde de parole.
    # Plafond securitaire : 30 s d'audio max -> 30 * 7 * 12 ~ 2520 tokens.
    max_new = min(2600, max(400, int(len(text) * 28)))

    out = STATE.model.generate(
        input_ids=input_ids,
        max_new_tokens=max_new,
        do_sample=True,
        temperature=0.6,
        top_p=0.9,
        repetition_penalty=1.1,
        eos_token_id=END_OF_SPEECH,
        pad_token_id=STATE.tokenizer.pad_token_id or STATE.tokenizer.eos_token_id,
    )

    wav = _decode_audio_tokens(out)

    # Resample temporel rudimentaire pour speed != 1.0
    if abs(speed - 1.0) > 1e-3 and wav.size > 0:
        n_out = max(1, int(len(wav) / speed))
        idx = (np.linspace(0, len(wav) - 1, n_out)).astype(np.int64)
        wav = wav[idx]
    return wav


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(title="Orpheus 3B FR TTS", version="1.0.0")


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    voice: Optional[str] = None
    speed: float = Field(1.0, ge=0.5, le=1.5)


class TTSResponse(BaseModel):
    audio_b64: str
    sample_rate: int
    duration_s: float
    voice: str
    rtf: float


@app.on_event("startup")
def _startup() -> None:
    load_models()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if STATE.model is not None else "loading",
        "cuda": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "model_loaded": STATE.model is not None,
        "sample_rate": STATE.sample_rate,
        "default_voice": STATE.default_voice,
    }


@app.get("/voices")
def voices() -> dict:
    return {"voices": STATE.voices, "default": STATE.default_voice}


@app.post("/tts", response_model=TTSResponse)
def tts(req: TTSRequest) -> TTSResponse:
    if STATE.model is None:
        raise HTTPException(503, "Modele non charge")

    voice = (req.voice or STATE.default_voice).strip().lower()
    log.info("synth voice=%s len_text=%d speed=%.2f", voice, len(req.text), req.speed)

    t0 = time.time()
    try:
        wav = synthesize(req.text, voice, req.speed)
    except Exception as e:  # pragma: no cover
        log.exception("synth error")
        raise HTTPException(500, f"Erreur de synthese: {e}")
    synth_s = time.time() - t0

    duration = len(wav) / STATE.sample_rate if wav.size else 0.0
    rtf = (synth_s / duration) if duration > 0 else 0.0

    buf = io.BytesIO()
    sf.write(buf, wav, STATE.sample_rate, subtype="PCM_16", format="WAV")
    audio_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    log.info("done duration=%.2fs synth=%.2fs rtf=%.2f", duration, synth_s, rtf)

    return TTSResponse(
        audio_b64=audio_b64,
        sample_rate=STATE.sample_rate,
        duration_s=duration,
        voice=voice,
        rtf=rtf,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host=os.environ.get("ORPHEUS_HOST", "0.0.0.0"),
        port=int(os.environ.get("ORPHEUS_PORT", "8899")),
        log_level="info",
    )
