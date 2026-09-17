# Architecture

## Pipeline

```
upload (CLI path / Streamlit tempfile)
  → loaders.load_file            # CSV (CSVLoader + DataFrame) or PDF
  → data/preprocessing           # sanitize, coerce, missing/duplicate/constant (opt-in, lineage)
  → profiling + analysis         # quality profile, KPIs, anomaly scan on cleaned df
  → providers.active_embedding_provider   # one-time probe (Gemini/OpenAI), cached per process
  → rag.pipeline.RAGPipeline     # content-hash collection, reset, index, retrieve top-k
  → reports.generator            # LLM report (context + KPIs + preprocessing lineage + citations)
  → charts.planner               # rule-based chart-type plan
  → charts.secure_executor       # AST whitelist → child process → PNG capture
  → charts.validator             # warnings on failures/empty/tiny figures
  → services.storage.RunStore    # var/outputs/<run_id>/{report.md,charts/,run.json (+preprocessing)}
  → reports.exporters            # optional styled PDF / PPTX
```

## Key design decisions

- **Embeddings are provider-pinned per run.** Chroma vectors from different
  providers live in different spaces, so the first working provider (in
  preference order) is probed once and reused for indexing *and* querying.
- **LLM calls fail over per call.** Report writing and chart-code generation
  each retry on the other provider on quota/auth/rate-limit errors.
- **Numbers come from code, narrative from the LLM.** Totals, top/bottom
  groups, outliers, and quality stats are computed with pandas and injected
  into the prompt with “cite these exactly” instructions; retrieved chunks
  carry `[chunk N]` references the report must preserve.
- **Chart code is untrusted.** AST whitelist (parse time) + spawned process
  with `join(timeout)` + `terminate()` (run time) + error-feedback retries.
  PNGs travel via files, never through the IPC pipe (avoids pipe-buffer
  deadlock on large images).
- **State is content-addressed.** Chroma collections are keyed by
  `sha1(filename + file_bytes)`; re-indexing deletes the old collection so
  reruns never duplicate vectors. Output filenames use the *original* upload
  name plus a run id — random temp names never leak into artifacts.

## Module map

| Module | Responsibility |
|---|---|
| `config/settings.py` | Env, paths (`var/`), model names, limits; lazy dir creation |
| `config/providers.py` | 4-provider LLM/embedding factories, probe, `call_llm` failover |
| `data/loaders.py` | CSV/PDF loading, size guard, merged CSV documents |
| `data/preprocessing.py` | Opt-in cleaning (sanitize, coerce, missing, dedupe) + lineage |
| `data/profiling.py` | Missing/duplicates/constant/suspicious-value profile |
| `rag/pipeline.py` | Split → embed → persist → retrieve → context assembly |
| `analysis/kpis.py` | Totals/means/top-bottom per measure × group |
| `analysis/anomalies.py` | IQR outliers + monthly spike scan |
| `analysis/insights.py` | Assembles the deterministic brief for prompts |
| `charts/planner.py` | Rule-based chart-type recommendations |
| `charts/secure_executor.py` | Sandbox execution + PNG capture |
| `charts/validator.py` | Post-execution sanity warnings |
| `reports/prompts.py` | Report + chart prompt templates |
| `reports/generator.py` | Orchestration (`generate()`) |
| `reports/exporters.py` | reportlab PDF + python-pptx deck |
| `services/storage.py` | Run directories, sanitized names, `run.json` ledger |
| `services/cost_tracking.py` | Token/latency estimates per run |
| `interfaces/cli.py` | `datacern` console script |
| `interfaces/streamlit_app.py` | Web UI (preview, quality, cleaning, history, editor, status) |
| `observability/logging.py` | stderr structured logging |
