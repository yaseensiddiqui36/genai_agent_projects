"""Shared state definition for the self-correcting agent graph."""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

Route = Literal["sql", "document", "hybrid"]


class Source(TypedDict):
    source: str
    excerpt: str


def _merge_unique(a: list[str] | None, b: list[str] | None) -> list[str]:
    """Reducer allowing two parallel branches (sql/retrieval) to both append tool names."""
    return list(dict.fromkeys([*(a or []), *(b or [])]))


def _first_non_null(a: str | None, b: str | None) -> str | None:
    """Reducer for fields two parallel branches may both try to set; earliest failure wins."""
    return a or b


def _merge_dicts(a: dict[str, float] | None, b: dict[str, float] | None) -> dict[str, float]:
    """Reducer letting parallel branches (sql/retrieval) each add their own latency entry."""
    return {**(a or {}), **(b or {})}


class AgentState(TypedDict, total=False):
    question: str

    route: Route
    reasoning: str  # router's rationale for the sql/document/hybrid decision
    tools_used: Annotated[list[str], _merge_unique]

    sql_query: str | None
    sql_error: str | None
    sql_result_text: str | None

    retrieved_sources: list[Source]

    answer: str
    confidence: float

    validation_passed: bool
    validation_reason: str

    retry_count: int
    max_retries: int

    failure_reason: Annotated[str | None, _first_non_null]

    # Observability: per-node wall-clock timings (ms) and overall latency.
    node_latencies_ms: Annotated[dict[str, float], _merge_dicts]
    latency_ms: float
