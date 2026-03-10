import os

# lucid-cc REST API base URL (internal docker network)
CC_URL = os.environ.get("LUCID_CC_URL", "http://localhost:5000")

# Postgres (used for persisting workflow history)
DB_URL = os.environ.get("LUCID_DB_URL", "postgresql://lucid:lucid_secret@localhost:5432/lucid")

# Ollama
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "llama3.1:8b")
