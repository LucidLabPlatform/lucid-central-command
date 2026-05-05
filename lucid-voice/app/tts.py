"""Text-to-speech endpoint using piper-tts."""

import asyncio
import io
import logging
import os
import urllib.request
import wave
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter()
log = logging.getLogger(__name__)

PIPER_MODEL_DIR = os.environ.get("PIPER_MODEL_DIR", "/models/piper")
PIPER_MODEL = os.environ.get("PIPER_MODEL", "en_US-amy-medium")
PIPER_VOICES_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

# Speech rate. 1.0 = native voice tempo. >1.0 slows down, <1.0 speeds up.
# Each request can override via the ``length_scale`` field on the body.
try:
    PIPER_LENGTH_SCALE = float(os.environ.get("PIPER_LENGTH_SCALE", "1.0"))
except ValueError:
    PIPER_LENGTH_SCALE = 1.0


def _ensure_voice(model_name: str, model_dir: Path) -> tuple[Path, Path] | None:
    """Make sure the piper voice exists locally. Download from HF if missing.

    Voice names follow ``{lang}_{country}-{voice}-{quality}`` (e.g.
    ``en_US-amy-medium``). The HuggingFace layout is
    ``{lang}/{lang_country}/{voice}/{quality}/{full-name}.onnx``.
    """
    onnx = model_dir / f"{model_name}.onnx"
    cfg = model_dir / f"{model_name}.onnx.json"
    if onnx.exists() and cfg.exists():
        return onnx, cfg

    try:
        lang_country, voice, quality = model_name.split("-")
        lang = lang_country.split("_")[0]
    except ValueError:
        log.error("Bad piper model name %r — expected lang_REGION-voice-quality", model_name)
        return None

    base = f"{PIPER_VOICES_BASE}/{lang}/{lang_country}/{voice}/{quality}"
    model_dir.mkdir(parents=True, exist_ok=True)
    log.info("Piper voice %s not found locally — downloading from %s", model_name, base)
    try:
        urllib.request.urlretrieve(f"{base}/{model_name}.onnx", onnx)
        urllib.request.urlretrieve(f"{base}/{model_name}.onnx.json", cfg)
    except Exception as e:
        log.error("Failed to download piper voice %s: %s", model_name, e)
        # Clean up partial files so we don't load a corrupt voice
        for p in (onnx, cfg):
            if p.exists() and p.stat().st_size < 1024:
                p.unlink(missing_ok=True)
        return None
    log.info("Downloaded piper voice %s (%.1f MB)",
             model_name, onnx.stat().st_size / 1_000_000)
    return onnx, cfg


def load_tts_engine():
    """Load a piper voice model, downloading it first if needed."""
    paths = _ensure_voice(PIPER_MODEL, Path(PIPER_MODEL_DIR))
    if paths is None:
        log.warning("Piper voice %s unavailable — TTS disabled", PIPER_MODEL)
        return None

    onnx, cfg = paths
    from piper import PiperVoice
    log.info("Loading piper voice %s", PIPER_MODEL)
    return PiperVoice.load(str(onnx), config_path=str(cfg))


class TTSRequest(BaseModel):
    text: str
    length_scale: float | None = None  # >1 slower, <1 faster, None = use default


def _synthesize(engine, text: str, length_scale: float) -> bytes:
    """Render ``text`` to a WAV bytestring at the given speech tempo.

    Piper 1.4.x exposes ``synthesize_wav(text, wave_writer, syn_config=...)``.
    ``length_scale`` on ``SynthesisConfig`` controls speech tempo: 1.0 is
    native, higher slows down, lower speeds up.
    """
    from piper import SynthesisConfig
    syn_config = SynthesisConfig(length_scale=length_scale)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        engine.synthesize_wav(text, wav, syn_config=syn_config)
    return buf.getvalue()


@router.post("/api/voice/tts")
async def text_to_speech(body: TTSRequest, request: Request):
    """Synthesize text to WAV audio."""
    engine = request.app.state.tts_engine
    if engine is None:
        return Response(status_code=503, content="TTS model not available")

    if not body.text.strip():
        return Response(status_code=400, content="Empty text")

    length_scale = body.length_scale if body.length_scale and body.length_scale > 0 else PIPER_LENGTH_SCALE
    audio_bytes = await asyncio.to_thread(_synthesize, engine, body.text, length_scale)

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=response.wav"},
    )
