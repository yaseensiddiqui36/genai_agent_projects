"""FastAPI application exposing the self-correcting enterprise data agent."""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, HTTPException

from infinite_coding_round.agent.graph import run_agent
from infinite_coding_round.api.metrics import metrics
from infinite_coding_round.api.schemas import AskRequest, AskResponse, RetrievedSource, StatsResponse

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Self-Correcting Enterprise Data Agent",
    description="Answers business questions via SQL, document retrieval, or both, "
    "with grounding validation and a single automatic retry on failure.",
    version="1.0.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    """Lightweight runtime observability snapshot (avg latency/confidence, retry rate, ...)."""
    return StatsResponse(**metrics.snapshot())


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    request_id = uuid.uuid4().hex[:8]
    logger.info("request_id=%s question=%r", request_id, request.question)

    try:
        state = run_agent(request.question)
    except Exception as exc:  # noqa: BLE001 - surface as a 500 with context
        logger.exception("request_id=%s agent execution failed", request_id)
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {exc}") from exc

    metrics.record(
        route=state.get("route", "unknown"),
        latency_ms=state.get("latency_ms", 0.0),
        confidence=state.get("confidence", 0.0),
        retry_count=state.get("retry_count", 0),
        validation_passed=state.get("validation_passed", False),
    )
    logger.info(
        "request_id=%s route=%s latency_ms=%s retries=%s validation_passed=%s",
        request_id,
        state.get("route"),
        state.get("latency_ms"),
        state.get("retry_count"),
        state.get("validation_passed"),
    )

    return AskResponse(
        answer=state.get("answer", ""),
        reasoning=state.get("reasoning", ""),
        tools_used=state.get("tools_used", []),
        generated_sql=state.get("sql_query"),
        retrieved_sources=[RetrievedSource(**s) for s in state.get("retrieved_sources", [])],
        confidence=state.get("confidence", 0.0),
        validation_result=state.get("validation_reason", ""),
        validation_passed=state.get("validation_passed", False),
        retry_count=state.get("retry_count", 0),
        latency_ms=state.get("latency_ms", 0.0),
        node_latencies_ms=state.get("node_latencies_ms", {}),
    )
