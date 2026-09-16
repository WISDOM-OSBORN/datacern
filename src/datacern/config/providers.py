"""Provider abstraction with automatic failover across Gemini, OpenAI, Groq, OpenRouter.

Two independent mechanisms:

* ``active_embedding_provider()`` — a **one-time probe** (cached per process)
  that picks the first provider whose embeddings actually work. Only
  Gemini and OpenAI provide embeddings (Groq has no embeddings API);
  Groq/OpenRouter are skipped for embeddings and fall back to Gemini.
  Required because Chroma vectors are provider-specific.

* ``call_llm()`` — **per-call failover** for chat completions. On any
  provider error (quota exhausted, rate limit, bad/expired key, ...) it
  automatically retries with the next provider, so reports and chart code
  keep working as long as at least one provider is functional.

The priority order is controlled by ``LLM_PROVIDER_PREFERENCE`` in ``.env``
(``gemini`` by default; ``openai`` | ``groq`` | ``openrouter`` | ``auto``).
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

PROVIDERS = ("gemini", "openai", "groq", "openrouter")
EMBEDDING_PROVIDERS = ("gemini", "openai")


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
    if provider == "openai":
        return ChatOpenAI(
            model=config.LLM_MODEL,
            temperature=config.LLM_TEMPERATURE,
            api_key=config.OPENAI_API_KEY,
        )
    if provider == "groq":
        return ChatOpenAI(
            model=config.GROQ_LLM_MODEL,
            temperature=config.LLM_TEMPERATURE,
            api_key=config.GROQ_API_KEY,
            base_url=config.GROQ_BASE_URL,
        )
    if provider == "openrouter":
        return ChatOpenAI(
            model=config.OPENROUTER_LLM_MODEL,
            temperature=config.LLM_TEMPERATURE,
            api_key=config.OPENROUTER_API_KEY,
            base_url=config.OPENROUTER_BASE_URL,
            default_headers={"HTTP-Referer": "https://github.com/WISDOM-OSBORN/datacern"},
        )
    raise ValueError(f"Unknown LLM provider {provider!r}")


def get_embeddings(provider: str) -> Embeddings:
    """Build an embeddings model for the given provider.

    Groq has no embeddings API — it falls back to Gemini so that the RAG
    vector store remains provider-consistent. OpenRouter also delegates
    to Gemini (free) when available.
    """
    if provider == "gemini":
        return GoogleGenerativeAIEmbeddings(
            model=config.GEMINI_EMBEDDING_MODEL,
            google_api_key=config.GEMINI_API_KEY,
        )
    if provider == "openai":
        return OpenAIEmbeddings(model=config.EMBEDDING_MODEL, api_key=config.OPENAI_API_KEY)
    if provider in ("groq", "openrouter"):
        # No native embeddings — delegate to Gemini/OpenAI so probe can
        # still succeed when only Groq/OpenRouter keys exist for LLM.
        if config.GEMINI_API_KEY:
            return GoogleGenerativeAIEmbeddings(
                model=config.GEMINI_EMBEDDING_MODEL,
                google_api_key=config.GEMINI_API_KEY,
            )
        return OpenAIEmbeddings(model=config.EMBEDDING_MODEL, api_key=config.OPENAI_API_KEY)
    raise ValueError(f"Unknown embedding provider {provider!r}")


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

    Only embedding-capable providers are probed (Groq/OpenRouter delegate
    to Gemini so they are skipped here to keep vector identity clear).

    Raises RuntimeError if no embedding provider works.
    """
    errors: dict[str, str] = {}
    # Probe only providers with native embeddings; Groq/OpenRouter share Gemini's store.
    order = [p for p in provider_order() if p in EMBEDDING_PROVIDERS]
    # If preference is Groq/OpenRouter, still need an embedding provider — try all.
    if not order:
        order = list(EMBEDDING_PROVIDERS)
    for provider in order:
        error = _probe(provider)
        if error is None:
            return provider
        errors[provider] = error

    detail = "; ".join(f"{k} -> {v}" for k, v in errors.items())
    raise RuntimeError(
        f"No working embedding provider. Checked {order}. {detail}"
    )


# ---------------------------------------------------------------- LLM failover
def _is_failover_worthy(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    markers = (
        "429",
        "401",
        "403",
        "404",
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
        "model_not_found",
        "not_found",
        "invalid_request",
        "does not exist",
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
    errors: list[str] = []
    for provider in provider_order():
        # Skip providers with no key configured — treat as failover.
        if provider == "gemini" and not config.GEMINI_API_KEY:
            errors.append("gemini -> skipped (no GEMINI_API_KEY)")
            continue
        if provider == "openai" and not config.OPENAI_API_KEY:
            errors.append("openai -> skipped (no OPENAI_API_KEY)")
            continue
        if provider == "groq" and not config.GROQ_API_KEY:
            errors.append("groq -> skipped (no GROQ_API_KEY)")
            continue
        if provider == "openrouter" and not config.OPENROUTER_API_KEY:
            errors.append("openrouter -> skipped (no OPENROUTER_API_KEY)")
            continue
        try:
            response = get_llm(provider).invoke(messages)
            return _extract_text(response.content)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            errors.append(f"{provider} -> {type(exc).__name__}: {exc}")
            if not _is_failover_worthy(exc):
                break
    detail = "; ".join(errors) if errors else "no providers attempted"
    if last_error:
        raise RuntimeError(
            f"All LLM providers failed. Tried: {detail}. "
            f"Last: {type(last_error).__name__}: {last_error}"
        ) from last_error
    raise RuntimeError(f"All LLM providers failed. {detail}") from last_error
