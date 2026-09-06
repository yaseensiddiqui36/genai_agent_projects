"""Central configuration for the self-correcting enterprise data agent."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
DB_PATH = DATA_DIR / "enterprise.db"
FAISS_INDEX_DIR = DATA_DIR / "faiss_index"


class Settings(BaseSettings):
    """Runtime settings, populated from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    max_retries: int = 1
    sql_row_limit: int = 50
    retrieval_top_k: int = 4
    confidence_threshold: float = 0.55


settings = Settings()
