FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download Whisper model at build time
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8')"

# Pre-download Piper voice at build time
RUN mkdir -p /models/piper && \
    python -c "import urllib.request; \
urllib.request.urlretrieve('https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx', '/models/piper/en_US-lessac-medium.onnx'); \
urllib.request.urlretrieve('https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json', '/models/piper/en_US-lessac-medium.onnx.json'); \
print('Piper models downloaded')"

COPY app/ ./app/
EXPOSE 5100
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5100"]
