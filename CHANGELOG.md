# DataCern Changelog (Keep a Changelog / Semantic Versioning)

## [Unreleased]

## [0.2.0] - 2026-09-12
### Added
- Dual-provider LLM/embeddings with automatic Gemini <-> OpenAI failover.
- Streamlit web UI with PDF/PPTX export and download buttons.
- Self-healing chart-code generation (error feedback, up to 3 attempts).
- Deterministic KPI engine, IQR anomaly scan, and data-quality profiling.
- Grounded citations: retrieved chunk references in context and report prompt.
- Run ledger (`run.json`) with provider, timings, warnings, and cost estimates.
- Styled PDF (`reportlab`) and PPTX (`python-pptx`) exporters.
- Professional `src/datacern` layout, `pyproject.toml`, Dockerfile, CI.
- MIT license.
### Changed
- Runtime state moved to `var/` (uploads, chroma, outputs, cache).
- Chroma collections keyed by file-content hash; re-indexing resets vectors.
- Output filenames preserve the original upload name plus run id.
- Chart execution timeout default 30s.
### Removed
- Root debug scripts (`check_deps.py`, `import_test.py`, `test_providers.py`,
  `test_gemini_models.py`, `diag_*`) and generated artifacts from version control.

## [0.1.0] - 2026-08-05
### Added
- Initial prototype: CSV/PDF loaders, Chroma RAG, OpenAI reports, sandboxed
  chart execution, CLI entry point.
