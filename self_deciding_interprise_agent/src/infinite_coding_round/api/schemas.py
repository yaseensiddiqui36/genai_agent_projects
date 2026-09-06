"""Pydantic request/response models for the /ask API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural-language business question.")


class RetrievedSource(BaseModel):
    source: str
    excerpt: str


class AskResponse(BaseModel):
    answer: str
    reasoning: str = Field(description="Router's rationale for the sql/document/hybrid decision.")
    tools_used: list[str]
    generated_sql: str | None = None
    retrieved_sources: list[RetrievedSource]
    confidence: float
    validation_result: str
    validation_passed: bool
    retry_count: int
    latency_ms: float = Field(description="Total end-to-end wall-clock latency for this request.")
    node_latencies_ms: dict[str, float] = Field(
        default_factory=dict, description="Per-node latency breakdown (router/run_sql/run_retrieval/synthesize/validate)."
    )


class StatsResponse(BaseModel):
    """Lightweight in-memory observability snapshot, reset on process restart."""

    total_queries: int
    avg_latency_ms: float
    avg_confidence: float
    retry_rate: float
    validation_pass_rate: float
    route_counts: dict[str, int]
