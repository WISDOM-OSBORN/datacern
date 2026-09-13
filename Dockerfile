FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 10001 datacern
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY examples ./examples
COPY README.md CHANGELOG.md LICENSE ./

RUN mkdir -p var/uploads var/chroma var/outputs var/cache && chown -R datacern:datacern /app
USER datacern

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=8)"

CMD ["python", "-m", "streamlit", "run", "src/datacern/interfaces/streamlit_app.py"]
