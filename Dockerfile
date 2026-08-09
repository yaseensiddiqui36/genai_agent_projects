# syntax=docker/dockerfile:1
FROM python:3.12-slim

# uv handles dependency installation (see pyproject.toml / uv.lock)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install dependencies first so this layer is cached across code-only changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Copy the rest of the app - this brings in the committed policy_vector_db/
# (built from sop_documents/ with local embeddings, no API key needed) and
# data/*.csv, which the app seeds refunds_agent.db from on first boot
# (see ensure_database_seeded() in chatbot_app.py) since the DB file itself
# is gitignored/not baked into the image.
COPY . .

EXPOSE 8501

HEALTHCHECK CMD uv run python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# GROQ_API_KEY must be supplied at runtime, e.g.:
#   docker run --env-file .env -p 8501:8501 <image>
ENTRYPOINT ["uv", "run", "streamlit", "run", "chatbot_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
