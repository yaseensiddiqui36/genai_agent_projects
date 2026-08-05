from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.search import RAGSearch

_rag_search: Optional[RAGSearch] = None


def get_rag_search() -> RAGSearch:
    global _rag_search
    if _rag_search is None:
        _rag_search = RAGSearch()
    return _rag_search


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build/load the vector store and LLM once at startup instead of per-request.
    get_rag_search()
    yield


app = FastAPI(
    title="Clinical Knowledge Assistant",
    description="RAG API that answers questions from a medical document corpus.",
    version="1.0.0",
    lifespan=lifespan,
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Question about the document corpus.")
    top_k: int = Field(5, ge=1, le=20, description="Number of chunks to retrieve.")


class SourceDocumentResponse(BaseModel):
    source: str
    page: Optional[int] = None
    snippet: str
    distance: float


class AskResponse(BaseModel):
    answer: str
    sources: List[SourceDocumentResponse]
    latency_seconds: float


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    rag = get_rag_search()
    try:
        result = rag.search_and_summarize(request.question, top_k=request.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to answer question: {exc}") from exc
    return AskResponse(**result)
