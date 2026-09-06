# Self-Correcting Enterprise Data Agent

A GenAI agent that takes a natural-language business question, decides whether it needs SQL, document retrieval, or both, executes the chosen tool(s), validates that its answer is grounded in the retrieved evidence, and retries automatically once if execution or validation fails.

## Tech Stack

- **LangGraph** — agent orchestration / routing graph
- **Groq** — LLM inference
- **FAISS + HuggingFace sentence-transformers** — document retrieval (RAG)
- **FastAPI** — backend API
- **Streamlit** — chat/inspection UI
- **Docker / docker-compose** — containerized deployment
- **pytest** — test suite (agent retry logic, SQL tool)

## How It Works

1. **Router** — an LLM classifies the incoming question as `sql`, `document`, or `hybrid`.
2. **Tool execution** — the SQL tool queries a seeded database; the retrieval tool searches a FAISS vector store built from policy/support documents in `data/documents/`.
3. **Validation** — the agent checks that its answer is actually grounded in the tool output.
4. **Retry** — if execution or validation fails, the agent retries once automatically before surfacing an error.
5. Exposed via a FastAPI backend (`src/infinite_coding_round/api/`) with a Streamlit UI (`src/infinite_coding_round/ui/`) on top, including an architecture-visualization page.

## Setup / Installation

Requires Python (see `.python-version`) and either `uv` or `pip`.

```bash
# with uv
uv sync

# or with pip
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

Configure environment variables as needed (Groq API key, DB path) — see `src/infinite_coding_round/config.py`.

## Usage

```bash
# run the API
uvicorn src.infinite_coding_round.api.main:app --reload

# run the Streamlit UI
streamlit run app.py
```

Or via Docker:

```bash
docker-compose up --build
```

Run the test suite with:

```bash
pytest
```

See `docs/DEPLOYMENT.md` for deployment notes and `docs/TEST_CASES.md` for the test case catalogue.
