"""Speech-to-text endpoint using faster-whisper."""

import asyncio
import logging
import os
import tempfile

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from faster_whisper import WhisperModel

router = APIRouter()
log = logging.getLogger(__name__)

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base.en")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")


def load_stt_model() -> WhisperModel:
    return WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)


def _transcribe(model: WhisperModel, audio_path: str) -> tuple[str, dict]:
    segments, info = model.transcribe(audio_path, beam_size=5)
    text = " ".join(seg.text.strip() for seg in segments)
    return text, {"language": info.language, "duration": round(info.duration, 2)}


@router.post("/api/voice/stt")
async def speech_to_text(request: Request, audio: UploadFile = File(...)):
    """Transcribe uploaded audio to text."""
    model = request.app.state.stt_model
    audio_bytes = await audio.read()

    if len(audio_bytes) < 100:
        raise HTTPException(400, "Audio too short")

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=True) as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        text, info = await asyncio.to_thread(_transcribe, model, tmp.name)

    if not text.strip():
        raise HTTPException(400, "No speech detected")

    return {"text": text.strip(), **info}
