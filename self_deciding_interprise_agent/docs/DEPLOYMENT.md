# Deployment Guide

## Local: one-command run

```bash
uv sync
uv run python app.py
```

This starts the FastAPI backend on `:8000` and the Streamlit UI on `:8501`, waits for
the backend health check before launching the UI, and stops both on Ctrl+C.

Use `uv run python app.py --no-browser` to skip auto-opening a browser tab (useful in
CI/headless environments).

### Troubleshooting: `WinError 10013` / `WinError 10048` on Windows

This means something is already bound to port 8000 — almost always a **stale
`uvicorn --reload` process** left over from a previous run (Windows' file-watcher
reload mode is known to leave orphaned socket holders). `app.py` checks for this up
front and tells you exactly what to do:

```bash
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

`app.py` itself does not use `--reload` for this reason — use
`uv run uvicorn infinite_coding_round.api.main:app --reload --port 8000` only for active
backend development, and make sure to fully stop it (Ctrl+C, not closing the terminal)
before starting it again.

## Public deployment (Streamlit Community Cloud)

The Streamlit UI (`src/infinite_coding_round/ui/streamlit_app.py`) can run **standalone**
— without a separately hosted FastAPI backend — because it calls the LangGraph agent
in-process when no backend is reachable (`AGENT_MODE=auto`, the default). This is what
makes a single-service deployment on Streamlit Community Cloud possible: Streamlit Cloud
only runs one process, so there's nothing to point a `POST /ask` HTTP call at.

On first run in a fresh environment it will:
1. Seed `data/enterprise.db` from `db/seed.py` if it doesn't exist.
2. Build the FAISS index from `data/documents/*.md` if it doesn't exist (downloads the
   `sentence-transformers/all-MiniLM-L6-v2` embedding model, ~90MB, on cold start).

### Steps

1. Push this repository to GitHub (see main [README](../README.md) for the commit/push
   flow — already configured to `origin` in this repo).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. **New app** → select this repository / `main` branch.
4. **Main file path**: `src/infinite_coding_round/ui/streamlit_app.py`
5. Under **Advanced settings → Secrets**, add:
   ```toml
   GROQ_API_KEY = "gsk_..."
   ```
   (`streamlit_app.py` promotes this secret to an environment variable before importing
   the agent, so `config.py`'s `Settings()` picks it up the same way it would from `.env`
   locally.)
6. Deploy. First load will take a bit longer (index build + model download); subsequent
   loads are fast since `@st.cache_resource` keeps the agent and index warm for the
   app's lifetime.

The app is then reachable at `https://<your-app-name>.streamlit.app` by anyone with the
link — no login required to view it.

### Verifying `POST /ask` still exists as a real API

The task requires a `POST /ask` endpoint independent of the UI. That's satisfied by
running the FastAPI backend separately (`uv run uvicorn infinite_coding_round.api.main:app
--port 8000`, or as part of `python app.py` locally) — the Streamlit Cloud deployment is
an additional, UI-only deployment path for public access, not a replacement for the API.
