# DataCern — evidence-grounded report generation

DataCern turns a **CSV or PDF** plus a plain-English question into a
professional analytical report with auto-generated charts.

- **Evidence-grounded**: every important number is computed deterministically
  (KPI engine) or cited to a retrieved source chunk — the LLM is instructed to
  never invent figures.
- **KPI + anomaly engine**: automatic totals, top/bottom groups, IQR outlier
  scan, and a data-quality profile feed every report.
- **Preprocessing (opt-in, lineage-tracked)**: column sanitization, type
  coercion, missing-value strategies, duplicate/constant handling — preview +
  apply before analysis; lineage saved to `run.json` and injected into prompts.
- **4-provider failover**: Gemini/Groq/OpenRouter/OpenAI — if one hits quota
  (429), auth or model errors (404), the next takes over automatically.
- **Safe chart code**: AST whitelist + child-process sandbox + timeout +
  self-healing retries, with PNG capture.
- **Multi-format publishing**: Markdown, styled PDF, and PPTX deck.
- **Web UX**: data preview, quality heatmap, cleaning controls, history
  browser, editable report, `st.status` progress, accessible alt text.
- **Run ledger**: every generation records provider, preprocessing lineage,
  timings, warnings, and cost estimates in `run.json`.

## Quickstart (local)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .   # makes `datacern` / `datacern-web` available
Copy-Item .env.example .env   # set GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY
```

- **Gemini key** (free, no card): https://aistudio.google.com → “Get API key”.
- **Groq key** (free, no card): https://console.groq.com/keys → Create API key.
- **OpenRouter key** (free :free models): https://openrouter.ai/keys → Create key.
- **OpenAI key** (pay-as-you-go): https://platform.openai.com → API keys.

## Usage — web UI

```powershell
datacern-web
# without install: $env:PYTHONPATH="src"
#   .\.venv\Scripts\python.exe -m streamlit run src/datacern/interfaces/streamlit_app.py
```

Open http://localhost:8501, upload a CSV/PDF → preview Data/Quality/Cleaning
tabs → adjust missing/duplicate handling → ask your question → tick PDF/PPTX →
hit **Generate Report** → edit Markdown inline → use History sidebar to reload
past runs.

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
| `GEMINI_API_KEY` / `GROQ_API_KEY` / `OPENROUTER_API_KEY` / `OPENAI_API_KEY` | — | At least one required |
| `LLM_PROVIDER_PREFERENCE` | `gemini` | `gemini` \| `groq` \| `openrouter` \| `openai` \| `auto` |
| `GEMINI_LLM_MODEL` | `gemini-2.0-flash` | Gemini chat model |
| `GROQ_LLM_MODEL` | `openai/gpt-oss-20b` | Groq chat model |
| `OPENROUTER_LLM_MODEL` | `google/gemma-4-26b-a4b-it:free` | OpenRouter free model |
| `LLM_MODEL` / `EMBEDDING_MODEL` | `gpt-4o-mini` / `text-embedding-3-small` | OpenAI models |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` / `TOP_K` | `1000` / `150` / `8` | RAG retrieval params |
| `EXEC_TIMEOUT` / `CHART_MAX_ATTEMPTS` | `30` / `3` | Chart sandbox + retries |
| `MAX_UPLOAD_MB` | `50` | Upload size guard |

## Project layout

```
src/datacern/
├── config/        # settings + 4-provider factories + failover
├── data/          # loaders + profiling + preprocessing (opt-in cleaning)
├── rag/           # Chroma pipeline (content-hash collections, reset on index)
├── analysis/      # KPIs, anomaly scan, insight assembly
├── charts/        # planner, AST-whitelisted sandboxed executor, validator
├── reports/       # prompts, generator, PDF/PPTX exporters
├── services/      # run storage (run IDs), cost tracking
├── interfaces/    # CLI + Streamlit UI (preview, cleaning, history, editor)
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
