# Providers & failover

DataCern works with **Google Gemini** (free tier) and **OpenAI**, with
automatic failover in both directions.

## Configuration

Set at least one key in `.env`:

```env
GEMINI_API_KEY=...
OPENAI_API_KEY=...
LLM_PROVIDER_PREFERENCE=gemini   # gemini | openai | auto
```

Model defaults (all overridable via env, see `.env.example`):

| Purpose | Gemini | OpenAI |
|---|---|---|
| Chat | `gemini-flash-latest` | `gpt-4o-mini` |
| Embeddings | `gemini-embedding-001` | `text-embedding-3-small` |

## How failover works

1. **Order** comes from `LLM_PROVIDER_PREFERENCE` (`gemini` → tries Gemini
   first, then OpenAI).
2. **Embeddings are probed once per process** (`active_embedding_provider`,
   `lru_cache`). The first provider whose `embed_query("probe")` succeeds
   becomes the embedding provider for all indexing *and* querying in that
   process. This is mandatory: mixing providers mid-stream corrupts Chroma
   retrieval because vector spaces differ.
3. **LLM calls fail over per call** (`call_llm`). On quota/rate-limit/auth
   errors (429/401/403 markers, `RESOURCE_EXHAUSTED`, billing messages…),
   the call is retried once on the other provider.
4. If **both** fail, a single `RuntimeError` lists both providers’ messages.

## Free-tier notes (verified 2026)

- Gemini free tier: `gemini-2.5-flash` is unavailable to new users — use
  `gemini-flash-latest`; embeddings use `gemini-embedding-001` (not
  `text-embedding-004`); embed-content is capped around 100 req/min, so CSV
  rows are merged into few documents before chunking.
- OpenAI: needs prepaid API credits; a ChatGPT Plus subscription does **not**
  grant API quota (`insufficient_quota` / `credit_balance_exhausted`).

## Testing failover without spending

`tests/test_providers.py` stubs the LLM clients and asserts the fallback
order. To exercise it live, set `LLM_PROVIDER_PREFERENCE=openai` with an
out-of-credit OpenAI key: embeddings and chat should both land on Gemini.
