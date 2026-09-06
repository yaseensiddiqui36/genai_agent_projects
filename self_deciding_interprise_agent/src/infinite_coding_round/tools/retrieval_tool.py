"""Document retrieval over the enterprise policy FAISS index."""

from __future__ import annotations

from dataclasses import dataclass

from infinite_coding_round.config import settings
from infinite_coding_round.rag.vectorstore import load_or_build_index


@dataclass
class RetrievedPassage:
    source: str
    content: str
    distance: float  # raw FAISS L2 distance; lower means more relevant

    def citation(self) -> str:
        return f"[{self.source}]"


def retrieve_passages(query: str, k: int | None = None) -> list[RetrievedPassage]:
    store = load_or_build_index()
    top_k = k or settings.retrieval_top_k
    results = store.similarity_search_with_score(query, k=top_k)
    passages = [
        RetrievedPassage(source=doc.metadata.get("source", "unknown"), content=doc.page_content, distance=score)
        for doc, score in results
    ]
    return passages
