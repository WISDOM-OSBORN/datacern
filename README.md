# DataCern — evidence-grounded report generation

DataCern turns a **CSV or PDF** plus a plain-English question into a
professional analytical report with auto-generated charts.

- **Evidence-grounded**: every important number is computed deterministically
  (KPI engine) or cited to a retrieved source chunk — the LLM is instructed to
  never invent figures.
- **KPI + anomaly engine**: automatic totals, top/bottom groups, IQR outlier
  scan, and a data-quality profile feed every report.
- **Dual-provider failover**: Gemini (free tier) primary, OpenAI fallback —
  if one runs out of credits or errors, the other takes over automatically.
- **Safe chart code**: AST whitelist + child-process sandbox + timeout +
  self-healing retries, with PNG capture.
- **Multi-format publishing**: Markdown, styled PDF, and PPTX deck.
- **Run ledger**: every generation records provider, timings, warnings, and
  cost estimates in `run.json`.

## Quickstart (local)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .   # makes `datacern` / `datacern-web` available
Copy-Item .env.example .env   # set GEMINI_API_KEY and/or OPENAI_API_KEY
```

- **Gemini key** (free, no card): https://aistudio.google.com → “Get API key”.
- **OpenAI key** (pay-as-you-go): https://platform.openai.com → API keys.
  A ChatGPT Plus subscription does *not* include API credits.

## Usage — web UI

```powershell
datacern-web
# without install: $env:PYTHONPATH="src"
#   .\.venv\Scripts\python.exe -m streamlit run src/datacern/interfaces/streamlit_app.py
```

Open http://localhost:8501, upload a CSV/PDF, ask your question, tick PDF/PPTX
if you want exports, and hit **Generate Report**.

## Usage — CLI

```powershell
.\.venv\Scripts\python.exe -m datacern.interfaces.cli --file examples/data/sales_data.csv --query "Analyze revenue by region and product."
# with exports:
.\.venv\Scripts\python.exe -m datacern.interfaces.cli --file data.csv --query "..." --pdf --pptx
# after `pip install -e .`:
datacern --file examples/data/sales_data.csv --query "..." --pdf
```

Each run creates `var/outputs/<run_id>/` with `report.md`, `charts/*.png`,
optional PDF/PPTX, and `run.json`.

## Configuration

All settings live in `.env` (see `.env.example`); code defaults are in
`src/datacern/config/settings.py`.

| Variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` / `OPENAI_API_KEY` | — | At least one required |
| `LLM_PROVIDER_PREFERENCE` | `gemini` | `gemini` \| `openai` \| `auto` |
| `GEMINI_LLM_MODEL` | `gemini-flash-latest` | Chat model for Gemini |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | Embedding model for Gemini |
| `LLM_MODEL` / `EMBEDDING_MODEL` | `gpt-4o-mini` / `text-embedding-3-small` | OpenAI models |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` / `TOP_K` | `1000` / `150` / `8` | RAG retrieval params |
| `EXEC_TIMEOUT` / `CHART_MAX_ATTEMPTS` | `30` / `3` | Chart sandbox + retries |
| `MAX_UPLOAD_MB` | `50` | Upload size guard |

## Project layout

```
src/datacern/
├── config/        # settings + Gemini/OpenAI factories + failover
├── data/          # loaders + data-quality profiling
├── rag/           # Chroma pipeline (content-hash collections, reset on index)
├── analysis/      # KPIs, anomaly scan, insight assembly
├── charts/        # planner, AST-whitelisted sandboxed executor, validator
├── reports/       # prompts, generator, PDF/PPTX exporters
├── services/      # run storage (run IDs), cost tracking
├── interfaces/    # CLI + Streamlit UI
└── observability/ # logging
tests/ docs/ scripts/ examples/ var/
```

See [`docs/architecture.md`](docs/architecture.md) for the full design,
[`docs/security-model.md`](docs/security-model.md) for sandbox guarantees,
[`docs/providers.md`](docs/providers.md) for failover behavior, and
[`docs/deployment.md`](docs/deployment.md) for Docker/production notes.

## Development

```powershell
pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest        # tests
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m ruff format src tests scripts
```

## License

MIT — see [LICENSE](LICENSE). Trademark note: “DataCern” is used here as the
project’s working title; run your own clearance before commercial launch.
