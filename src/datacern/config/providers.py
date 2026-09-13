"""Provider abstraction with automatic failover between Gemini and OpenAI.

Two independent mechanisms:

* ``active_embedding_provider()`` — a **one-time probe** (cached per process)
  that picks the first provider whose embeddings actually work. This is
  required because Chroma vectors are provider-specific: switching embedding
  providers mid-stream would corrupt retrieval. The chosen provider is then
  used for both indexing and querying.

* ``call_llm()`` — **per-call failover** for chat completions. On any
  provider error (quota exhausted, rate limit, bad/expired key, ...) it
  automatically retries with the other provider, so reports and chart code
  keep working as long as at least one provider is functional.

The priority order is controlled by ``LLM_PROVIDER_PREFERENCE`` in ``.env``
(``gemini`` by default, or ``openai``).
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    GoogleGenerativeAIEmbeddings,
)
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from datacern.config import settings as config

PROVIDERS = ("gemini", "openai")


# ---------------------------------------------------------------- ordering
def provider_order() -> list[str]:
    """Return providers in fallback order based on LLM_PROVIDER_PREFERENCE."""
    preference = config.LLM_PROVIDER_PREFERENCE or "gemini"
    if preference == "auto":
        return list(PROVIDERS)
    if preference not in PROVIDERS:
        raise ValueError(
            f"LLM_PROVIDER_PREFERENCE must be one of {PROVIDERS} or 'auto', got {preference!r}"
        )
    others = [p for p in PROVIDERS if p != preference]
    return [preference] + others


# ---------------------------------------------------------------- factories
def get_llm(provider: str) -> BaseChatModel:
    """Build a chat model for the given provider."""
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=config.GEMINI_LLM_MODEL,
            google_api_key=config.GEMINI_API_KEY,
            temperature=config.LLM_TEMPERATURE,
        )
    return ChatOpenAI(
        model=config.LLM_MODEL,
        temperature=config.LLM_TEMPERATURE,
        api_key=config.OPENAI_API_KEY,
    )


def get_embeddings(provider: str) -> Embeddings:
    """Build an embeddings model for the given provider."""
    if provider == "gemini":
        return GoogleGenerativeAIEmbeddings(
            model=config.GEMINI_EMBEDDING_MODEL,
            google_api_key=config.GEMINI_API_KEY,
        )
    return OpenAIEmbeddings(model=config.EMBEDDING_MODEL, api_key=config.OPENAI_API_KEY)


# ---------------------------------------------------------------- embeddings probe
def _probe(provider: str) -> str | None:
    """Return a short error message if the provider's embeddings fail."""
    try:
        get_embeddings(provider).embed_query("probe")
        return None
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"


@lru_cache(maxsize=1)
def active_embedding_provider() -> str:
    """Pick (once per process) the first provider whose embeddings work.

    Raises RuntimeError if neither provider works.
    """
    errors: dict[str, str] = {}
    for provider in provider_order():
        error = _probe(provider)
        if error is None:
            return provider
        errors[provider] = error

    detail = "; ".join(f"{k} -> {v}" for k, v in errors.items())
    raise RuntimeError(
        f"No working provider for embeddings/LLM. Checked in order {provider_order()}. {detail}"
    )


# ---------------------------------------------------------------- LLM failover
def _is_failover_worthy(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    markers = (
        "429",
        "401",
        "403",
        "quota",
        "rate limit",
        "billing",
        "payment",
        "api key",
        "authentication",
        "permission",
        "insufficient",
        "resource_exhausted",
        "access_not_configured",
        "not enabled",
        "connection error",
        "timed out",
        "500",
        "503",
        "permission_denied",
        "unauthenticated",
    )
    return any(marker in text for marker in markers)


def _extract_text(content) -> str:
    """Normalize AIMessage.content (str or list of content blocks) to text."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                else:
                    parts.append(str(block))
        return "\n".join(parts).strip()
    return str(content).strip()


def call_llm(messages: list[BaseMessage]) -> str:
    """Invoke a chat model across providers, failing over automatically."""
    last_error: BaseException | None = None
    for provider in provider_order():
        try:
            response = get_llm(provider).invoke(messages)
            return _extract_text(response.content)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if not _is_failover_worthy(exc):
                break
    raise RuntimeError(
        f"All LLM providers failed. Last error: {type(last_error).__name__}: {last_error}"
    ) from last_error
