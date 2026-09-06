"""Builds and loads a FAISS vector store over the enterprise policy documents."""

from __future__ import annotations

from functools import lru_cache

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from infinite_coding_round.config import DOCUMENTS_DIR, FAISS_INDEX_DIR, settings


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=settings.embedding_model)


def _load_source_documents() -> list[Document]:
    documents: list[Document] = []
    for path in sorted(DOCUMENTS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        documents.append(Document(page_content=text, metadata={"source": path.name}))
    if not documents:
        raise FileNotFoundError(f"No policy documents found in {DOCUMENTS_DIR}")
    return documents


def build_index() -> FAISS:
    """Chunks all policy documents and builds a fresh FAISS index on disk."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
    chunks = splitter.split_documents(_load_source_documents())
    store = FAISS.from_documents(chunks, get_embeddings())
    FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    store.save_local(str(FAISS_INDEX_DIR))
    return store


@lru_cache(maxsize=1)
def load_or_build_index() -> FAISS:
    """Loads the persisted FAISS index, building it on first run."""
    if (FAISS_INDEX_DIR / "index.faiss").exists():
        return FAISS.load_local(
            str(FAISS_INDEX_DIR),
            get_embeddings(),
            allow_dangerous_deserialization=True,
        )
    return build_index()


if __name__ == "__main__":
    build_index()
    print(f"FAISS index built at {FAISS_INDEX_DIR}")
