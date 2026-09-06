# Clinical Knowledge Assistant

A RAG (Retrieval-Augmented Generation) app that answers medical questions using a fixed set of clinical documents as its only source of truth. Ask it something covered in the documents and it answers with citations — it won't answer from general LLM knowledge outside that corpus.

## Tech Stack

- **Groq** — LLM inference (`llama-3.3-70b-versatile` by default)
- **Custom vector store / embeddings** (`src/embedding.py`, `src/vectorstore.py`) for document search
- **FastAPI** — REST API (`src/api.py`)
- **Streamlit** — chat UI (`streamlit_app.py`)
- **Docker** — containerized deployment

## Features

- Answers grounded strictly in the documents under `data/` (cardiovascular risk factors, hypertension, seasonal influenza, type 2 diabetes, mental health)
- Citations included with each answer
- Both a REST API and a Streamlit chat interface
- Configurable retrieval distance threshold and embedding/LLM model via environment variables

## Setup / Installation

Requires Python 3.11+ and a free [Groq API key](https://console.groq.com/keys).

```bash
# with uv
uv sync

# or with pip
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_groq_api_key_here
# optional
GROQ_MODEL=llama-3.3-70b-versatile
RAG_DISTANCE_THRESHOLD=1.6
```

## Usage

```bash
# Streamlit UI
streamlit run streamlit_app.py

# REST API
uvicorn src.api:app --reload
```

Or via Docker (`Dockerfile` + `docker-entrypoint.sh` provided). See `eval_questions.md` for a sample evaluation question set.
