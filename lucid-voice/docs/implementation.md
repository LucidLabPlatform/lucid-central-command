# lucid-voice — Implementation

> **Package:** `lucid-voice` | **Container:** `lucid-voice` | **Internal port:** 5100

## Overview

`lucid-voice` provides local speech-to-text (STT) and text-to-speech (TTS) services for the LUCID dashboard's voice interface. It runs entirely on-device using `faster-whisper` for transcription and `piper-tts` for synthesis, with no external API calls. Models are loaded once at startup and reused across requests.

## Key Modules and Responsibilities

| Module | Responsibility |
|--------|----------------|
| `main.py` | FastAPI app creation; lifespan loads STT and TTS models into `app.state`; health endpoint reports model names |
| `stt.py` | Speech-to-text: loads `faster-whisper` `WhisperModel`; transcribes uploaded audio files via `POST /api/voice/stt`; runs inference in a thread via `asyncio.to_thread` |
| `tts.py` | Text-to-speech: loads `piper` `PiperVoice` from ONNX model files; synthesizes text to WAV via `POST /api/voice/tts`; returns raw audio bytes with `audio/wav` content type |

## Important Implementation Details

### STT Pipeline

1. Client uploads audio (typically WebM from browser MediaRecorder) to `POST /api/voice/stt`.
2. Audio is written to a temporary file (required by faster-whisper's file-based API).
3. Transcription runs in a thread pool (`asyncio.to_thread`) to avoid blocking the event loop.
4. `WhisperModel.transcribe()` with `beam_size=5` produces segments; text is concatenated.
5. Returns `{"text": "...", "language": "en", "duration": 3.14}`.
6. Rejects audio shorter than 100 bytes or producing no speech.

Configuration via environment variables:
- `WHISPER_MODEL` — Model size (default: `base.en`)
- `WHISPER_DEVICE` — Inference device: `cpu` or `cuda` (default: `cpu`)
- `WHISPER_COMPUTE_TYPE` — Compute precision: `int8`, `float16`, etc. (default: `int8`)

### TTS Pipeline

1. Client sends `{"text": "..."}` to `POST /api/voice/tts`.
2. Synthesis runs in a thread pool.
3. Piper outputs raw PCM samples; these are wrapped in a WAV container (1 channel, 16-bit, model's native sample rate).
4. Returns the WAV file as `audio/wav` with inline content disposition.
5. Returns 503 if the Piper model was not found at startup.

Configuration:
- `PIPER_MODEL` — Voice model name (default: `en_US-lessac-medium`)
- `PIPER_MODEL_DIR` — Directory containing `.onnx` and `.onnx.json` model files (default: `/models/piper`)

### Model Loading

Both models are loaded during the FastAPI lifespan (before accepting requests) and stored on `app.state`:
- `app.state.stt_model` — `WhisperModel` instance
- `app.state.tts_engine` — `PiperVoice` instance (or `None` if model files are missing)

The Docker volume `lucid-voice-models` persists downloaded models across container restarts.

## How It Connects to Other Services

- **lucid-ui** — Receives proxied requests from the UI at `/api/voice/*`
- No database, MQTT, or orchestrator connections
- Self-contained inference using local model files
