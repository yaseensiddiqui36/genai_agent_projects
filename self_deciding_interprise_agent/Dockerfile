FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000 8501

# Backend only by default; override CMD (or use docker-compose) to also run Streamlit.
CMD ["uv", "run", "uvicorn", "infinite_coding_round.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
