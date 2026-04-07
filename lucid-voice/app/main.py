"""LUCID Voice service — local STT (faster-whisper) and TTS (piper)."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.stt import load_stt_model
    from app.tts import load_tts_engine

    log.info("Loading STT model…")
    app.state.stt_model = load_stt_model()
    log.info("STT model loaded.")

    log.info("Loading TTS engine…")
    app.state.tts_engine = load_tts_engine()
    log.info("TTS engine loaded.")

    yield


app = FastAPI(title="LUCID Voice", lifespan=lifespan)

from app.stt import router as stt_router  # noqa: E402
from app.tts import router as tts_router  # noqa: E402

app.include_router(stt_router)
app.include_router(tts_router)


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "lucid-voice",
        "whisper_model": os.environ.get("WHISPER_MODEL", "base.en"),
        "piper_model": os.environ.get("PIPER_MODEL", "en_US-lessac-medium"),
    }
