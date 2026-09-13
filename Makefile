.PHONY: install dev test lint format typecheck run-web run-cli sample-data docker-build docker-up clean

PY ?= .venv/Scripts/python.exe
ifeq ($(OS),Windows_NT)
PY := .venv/Scripts/python.exe
else
PY := .venv/bin/python
endif

install:
	$(PY) -m pip install -r requirements.txt

dev:
	$(PY) -m pip install -r requirements-dev.txt
	pre-commit install

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check src tests scripts

format:
	$(PY) -m ruff format src tests scripts

typecheck:
	$(PY) -m mypy src

run-web:
	$(PY) -m streamlit run src/datacern/interfaces/streamlit_app.py

run-cli:
	$(PY) -m datacern.interfaces.cli --file examples/data/sales_data.csv --query "Analyze revenue by region and product."

sample-data:
	$(PY) scripts/make_sample_dataset.py

docker-build:
	docker build -t datacern:latest .

docker-up:
	docker compose up --build

clean:
	Get-ChildItem -Recurse -Directory -Include "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
