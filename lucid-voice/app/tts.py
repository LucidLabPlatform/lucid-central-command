"""Text-to-speech endpoint using piper-tts."""

import asyncio
import io
import logging
import os
import wave

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter()
log = logging.getLogger(__name__)

PIPER_MODEL_DIR = os.environ.get("PIPER_MODEL_DIR", "/models/piper")
PIPER_MODEL = os.environ.get("PIPER_MODEL", "en_US-lessac-medium")


def load_tts_engine():
    """Load a piper voice model from the model directory."""
    model_path = os.path.join(PIPER_MODEL_DIR, f"{PIPER_MODEL}.onnx")
    config_path = f"{model_path}.json"

    if not os.path.exists(model_path):
        log.warning("Piper model not found at %s — TTS will be unavailable", model_path)
        return None

    from piper import PiperVoice
    return PiperVoice.load(model_path, config_path=config_path)


class TTSRequest(BaseModel):
    text: str


def _synthesize(engine, text: str) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(engine.config.sample_rate)
        engine.synthesize(text, wav)
    return buf.getvalue()


@router.post("/api/voice/tts")
async def text_to_speech(body: TTSRequest, request: Request):
    """Synthesize text to WAV audio."""
    engine = request.app.state.tts_engine
    if engine is None:
        return Response(status_code=503, content="TTS model not available")

    if not body.text.strip():
        return Response(status_code=400, content="Empty text")

    audio_bytes = await asyncio.to_thread(_synthesize, engine, body.text)

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=response.wav"},
    )
