# Deployment

## Local (venv)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # add keys
.\.venv\Scripts\python.exe -m streamlit run src/datacern/interfaces/streamlit_app.py
```

## Docker (recommended for sharing/hosting)

```powershell
Copy-Item .env.example .env   # add keys
docker compose up --build
# open http://localhost:8501
```

Notes:

- The image runs as non-root, headless Streamlit on port 8501 with a
  healthcheck on `/_stcore/health`.
- Persistent state lives in mounted volumes: `var/uploads`, `var/chroma`,
  `var/outputs`, `var/cache`. Back up or purge per your retention policy.
- Never bake `.env` into the image (it is excluded via `.dockerignore`).

## Production checklist

- [ ] Set `MAX_UPLOAD_MB` and reverse-proxy limits (nginx/client_max_body_size).
- [ ] Put the app behind HTTPS with authentication (Streamlit exposes none).
- [ ] Restrict CORS/XSRF and set `STREAMLIT_SERVER_ENABLE_CSRF_PROTECTION`
      per your hosting docs if embedding the UI.
- [ ] Apply container memory/CPU limits (chart sandbox has a timeout but no
      memory cap).
- [ ] Define retention: purge `var/uploads`, stale Chroma collections, and old
      `var/outputs/<run_id>` dirs on a schedule.
- [ ] Ship logs (`datacern.*` loggers → stderr) to your aggregator.
- [ ] Decide on PII handling before processing personal data (no redaction yet).
- [ ] Pin versions (`pip freeze` / lockfile) for release builds.
