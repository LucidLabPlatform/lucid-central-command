FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download Whisper model at build time
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8')"

# Pre-download Piper voice at build time. Voice can be overridden at run time
# via the PIPER_MODEL env var; the service will fetch a missing voice on
# startup via app/tts.py::_ensure_voice (adds ~10s to first boot).
RUN mkdir -p /models/piper && \
    python -c "import urllib.request; \
urllib.request.urlretrieve('https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_male/medium/en_US-hfc_male-medium.onnx', '/models/piper/en_US-hfc_male-medium.onnx'); \
urllib.request.urlretrieve('https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_male/medium/en_US-hfc_male-medium.onnx.json', '/models/piper/en_US-hfc_male-medium.onnx.json'); \
print('Piper models downloaded')"

COPY app/ ./app/
EXPOSE 5100
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5100"]
