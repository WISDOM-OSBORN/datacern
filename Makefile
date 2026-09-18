.PHONY: install dev venv test lint format typecheck web report sample-data docker-build docker-up clean help

PY ?= python
VENV ?= .venv
# Detect Windows vs Unix for venv python path
ifeq ($(OS),Windows_NT)
  VENV_PY := $(VENV)/Scripts/python.exe
else
  VENV_PY := $(VENV)/bin/python
endif

# Override PY to use venv if it exists
ifneq (,$(wildcard $(VENV_PY)))
  PY := $(VENV_PY)
endif

FILE ?= examples/data/sales_data.csv
QUERY ?= Analyze revenue by region and product; identify top and bottom performers.
PORT ?= 8501

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

venv: ## Create virtual environment
	python -m venv $(VENV)
	@echo "Activate: Windows: .\.venv\Scripts\Activate.ps1  |  Unix: source .venv/bin/activate"

install: ## Install runtime deps + editable package
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install -e .
	@echo "Copy .env.example -> .env and set GEMINI/GROQ/OPENROUTER keys"

dev: ## Install dev deps + pre-commit
	$(PY) -m pip install -r requirements-dev.txt
	pre-commit install || echo "pre-commit not required"

test: ## Run tests (38 tests)
	$(PY) -m pytest

lint: ## Ruff lint
	$(PY) -m ruff check src tests scripts

format: ## Ruff format
	$(PY) -m ruff format src tests scripts

typecheck: ## mypy
	$(PY) -m mypy src

web: ## Run Streamlit web UI (PORT=8501)
	$(PY) -m streamlit run src/datacern/interfaces/streamlit_app.py --server.port $(PORT)

report: ## Run CLI report (FILE=... QUERY="...")
	$(PY) -m datacern.interfaces.cli --file $(FILE) --query "$(QUERY)" --pdf --pptx

sample-data:
	$(PY) scripts/make_sample_dataset.py

docker-build:
	docker build -t datacern:latest .

docker-up:
	docker compose up --build

clean: ## Remove caches (safe)
	$(PY) -c "import shutil,pathlib; [shutil.rmtree(p,ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
	-$(PY) -m pip cache purge 2>nul || true
	@rm -rf .pytest_cache .ruff_cache 2>nul || true
	@echo "Clean done (kept var/outputs, .venv, Chroma)"
