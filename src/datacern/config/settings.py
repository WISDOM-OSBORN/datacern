"""Central configuration for DataCern.

Environment is loaded from ``.env`` at the repository root. Importing this
module has no side effects: directories are created lazily by
:func:`ensure_runtime_dirs`.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------- paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

DATA_DIR = BASE_DIR / "examples" / "data"
VAR_DIR = BASE_DIR / "var"
UPLOAD_DIR = VAR_DIR / "uploads"
CHROMA_PATH = VAR_DIR / "chroma"
OUTPUT_PATH = VAR_DIR / "outputs"
CACHE_DIR = VAR_DIR / "cache"


def ensure_runtime_dirs() -> None:
    """Create runtime directories (uploads, chroma, outputs, cache)."""
    for _path in (UPLOAD_DIR, CHROMA_PATH, OUTPUT_PATH, CACHE_DIR):
        _path.mkdir(parents=True, exist_ok=True)


def new_run_id() -> str:
    """Return a short unique run identifier for output naming."""
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------- env
load_dotenv(BASE_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# ---------------------------------------------------------------- models
LLM_PROVIDER_PREFERENCE = os.getenv("LLM_PROVIDER_PREFERENCE", "gemini").strip().lower()

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
GEMINI_LLM_MODEL = os.getenv("GEMINI_LLM_MODEL", "gemini-2.0-flash")
GROQ_LLM_MODEL = os.getenv("GROQ_LLM_MODEL", "openai/gpt-oss-20b")
OPENROUTER_LLM_MODEL = os.getenv("OPENROUTER_LLM_MODEL", "google/gemma-4-26b-a4b-it:free")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

# ---------------------------------------------------------------- RAG params
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
TOP_K = int(os.getenv("TOP_K", "8"))

# ---------------------------------------------------------------- executor
EXEC_TIMEOUT = int(os.getenv("EXEC_TIMEOUT", "30"))
CHART_MAX_ATTEMPTS = int(os.getenv("CHART_MAX_ATTEMPTS", "3"))

# ---------------------------------------------------------------- uploads / retention
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
SUPPORTED_EXTENSIONS = {".csv", ".pdf"}
