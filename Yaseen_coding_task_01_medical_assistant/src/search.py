import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from src.data_loader import load_all_documents
from src.vectorstore import FaissVectorStore

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

NO_CONTEXT_MESSAGE = "I don't have enough information in the provided documents to answer that question."

# L2 distance (all-MiniLM-L6-v2, unnormalized) above which a retrieved chunk is treated as
# unrelated to the query. 
# primary grounding mechanism, since embedding distance alone is not a reliable relevance cutoff.
DEFAULT_DISTANCE_THRESHOLD = float(os.getenv("RAG_DISTANCE_THRESHOLD", "1.6"))

SYSTEM_PROMPT = (
    "You are a clinical knowledge assistant. Answer the user's question using ONLY the "
    "context excerpts below. Do not use outside/general medical knowledge, and do not "
    "speculate or fill gaps with assumptions.\n\n"
    "If the context does not contain enough information to answer the question, respond with "
    f'exactly this sentence and nothing else: "{NO_CONTEXT_MESSAGE}"\n\n'
    "When you do answer, ground every statement in the context and keep the answer concise."
)


@dataclass
class SourceDocument:
    source: str
    page: Optional[int]
    snippet: str
    distance: float


class RAGSearch:
    def __init__(
        self,
        persist_dir: str = "faiss_store",
        embedding_model: str = "all-MiniLM-L6-v2",
        llm_model: str = GROQ_MODEL,
        distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
    ):
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")

        self.distance_threshold = distance_threshold
        self.vectorstore = FaissVectorStore(persist_dir, embedding_model)

        faiss_path = os.path.join(persist_dir, "faiss.index")
        meta_path = os.path.join(persist_dir, "metadata.pkl")
        if os.path.exists(faiss_path) and os.path.exists(meta_path):
            self.vectorstore.load()
        else:
            docs = load_all_documents("data")
            self.vectorstore.build_from_documents(docs)

        self.llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name=llm_model)
        print(f"[INFO] Groq LLM initialized: {llm_model}")

    def _retrieve(self, query: str, top_k: int) -> List[SourceDocument]:
        results = self.vectorstore.query(query, top_k=top_k)
        sources = []
        for r in results:
            meta = r.get("metadata") or {}
            text = meta.get("text", "")
            if not text:
                continue
            sources.append(
                SourceDocument(
                    source=meta.get("source", "unknown"),
                    page=meta.get("page"),
                    snippet=text,
                    distance=float(r["distance"]),
                )
            )
        return sources

    def search_and_summarize(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        start = time.perf_counter()
        sources = self._retrieve(query, top_k=top_k)
        relevant = [s for s in sources if s.distance <= self.distance_threshold]

        if not relevant:
            return {
                "answer": NO_CONTEXT_MESSAGE,
                "sources": [],
                "latency_seconds": round(time.perf_counter() - start, 3),
            }

        context = "\n\n".join(
            f"[Source: {s.source}, page {s.page}]\n{s.snippet}" for s in relevant
        )
        user_prompt = f"Question: {query}\n\nContext:\n{context}"

        response = self.llm.invoke(
            [
                ("system", SYSTEM_PROMPT),
                ("human", user_prompt),
            ]
        )

        return {
            "answer": response.content,
            "sources": [
                {
                    "source": s.source,
                    "page": s.page,
                    "snippet": s.snippet[:300],
                    "distance": round(s.distance, 4),
                }
                for s in relevant
            ],
            "latency_seconds": round(time.perf_counter() - start, 3),
        }


# Example usage
if __name__ == "__main__":
    rag_search = RAGSearch()
    query = "What are the findings of the study?"
    result = rag_search.search_and_summarize(query, top_k=3)
    print("Answer:", result["answer"])
    print("Sources:", result["sources"])
    print("Latency (s):", result["latency_seconds"])
