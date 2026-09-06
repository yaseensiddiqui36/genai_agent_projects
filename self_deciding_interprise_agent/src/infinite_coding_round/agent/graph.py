"""LangGraph state machine implementing the self-correcting enterprise data agent.

Flow:
    router -> [run_sql] and/or [run_retrieval] (fan-out per route) -> synthesize -> validate
    If validation fails (or SQL execution failed) and a retry budget remains, the graph
    loops back through the same tool nodes (with error/failure context injected) once,
    then re-synthesizes and re-validates before terminating.
"""

from __future__ import annotations

import functools
import re
import time
from typing import Callable

from langgraph.graph import END, StateGraph

from infinite_coding_round.agent.llm import get_llm
from infinite_coding_round.agent.prompts import (
    ROUTER_PROMPT,
    SCHEMA_FOR_PROMPTS,
    SQL_GENERATION_PROMPT,
    SQL_RETRY_CONTEXT,
    SYNTHESIS_PROMPT,
    VALIDATION_PROMPT,
)
from infinite_coding_round.agent.state import AgentState
from infinite_coding_round.config import settings
from infinite_coding_round.tools.retrieval_tool import retrieve_passages
from infinite_coding_round.tools.sql_tool import execute_readonly_sql

_VALID_ROUTES = {"sql", "document", "hybrid"}


def _clean_sql(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"^```(sql)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _timed(node_name: str) -> Callable[[Callable[[AgentState], dict]], Callable[[AgentState], dict]]:
    """Wraps a node so its wall-clock latency is recorded into node_latencies_ms.

    Portfolio note: this is what powers the per-step latency breakdown surfaced in
    the API response and UI, without cluttering each node's own logic with timing code.
    """

    def decorator(fn: Callable[[AgentState], dict]) -> Callable[[AgentState], dict]:
        @functools.wraps(fn)
        def wrapper(state: AgentState) -> dict:
            start = time.perf_counter()
            update = fn(state)
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            update["node_latencies_ms"] = {node_name: elapsed_ms}
            return update

        return wrapper

    return decorator


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #


@_timed("router")
def route_question(state: AgentState) -> dict:
    llm = get_llm()
    prompt = ROUTER_PROMPT.format(schema=SCHEMA_FOR_PROMPTS, question=state["question"])
    raw = llm.invoke(prompt).content.strip()

    route_match = re.search(r"ROUTE:\s*(sql|document|hybrid)", raw, re.IGNORECASE)
    reasoning_match = re.search(r"REASONING:\s*(.+)", raw, re.IGNORECASE)

    if route_match:
        route = route_match.group(1).lower()
    else:
        lowered = raw.lower()
        route = next((r for r in _VALID_ROUTES if r in lowered), "hybrid")
    reasoning = reasoning_match.group(1).strip() if reasoning_match else raw.strip()

    return {
        "route": route,
        "reasoning": reasoning,
        "tools_used": [],
        "retry_count": 0,
        "max_retries": settings.max_retries,
        "retrieved_sources": [],
        "sql_query": None,
        "sql_error": None,
        "sql_result_text": None,
        "failure_reason": None,
    }


@_timed("run_sql")
def run_sql(state: AgentState) -> dict:
    llm = get_llm()
    retry_context = ""
    if state.get("sql_error") and state.get("sql_query"):
        retry_context = SQL_RETRY_CONTEXT.format(
            previous_sql=state["sql_query"], error=state["sql_error"]
        )
    prompt = SQL_GENERATION_PROMPT.format(
        schema=SCHEMA_FOR_PROMPTS, question=state["question"], retry_context=retry_context
    )
    raw_sql = llm.invoke(prompt).content
    sql = _clean_sql(raw_sql)
    result = execute_readonly_sql(sql)

    tools_used = list(dict.fromkeys([*state.get("tools_used", []), "sql"]))
    if not result.success:
        return {
            "sql_query": sql,
            "sql_error": result.error,
            "sql_result_text": None,
            "tools_used": tools_used,
            "failure_reason": f"SQL execution failed: {result.error}",
        }
    return {
        "sql_query": sql,
        "sql_error": None,
        "sql_result_text": result.as_markdown_table(),
        "tools_used": tools_used,
        "failure_reason": None,
    }


@_timed("run_retrieval")
def run_retrieval(state: AgentState) -> dict:
    passages = retrieve_passages(state["question"])
    seen: set[str] = set()
    sources: list[dict] = []
    for p in passages:
        key = p.content.strip()
        if key in seen:
            continue
        seen.add(key)
        sources.append({"source": p.source, "excerpt": key})
    tools_used = list(dict.fromkeys([*state.get("tools_used", []), "document_retrieval"]))
    failure_reason = "No relevant document passages were retrieved." if not sources else None
    return {"retrieved_sources": sources, "tools_used": tools_used, "failure_reason": failure_reason}


def _build_evidence_block(state: AgentState) -> str:
    parts: list[str] = []
    if state.get("sql_query"):
        parts.append(f"[SQL result] Query: {state['sql_query']}")
        if state.get("sql_result_text"):
            parts.append(state["sql_result_text"])
        elif state.get("sql_error"):
            parts.append(f"(SQL failed: {state['sql_error']})")
    for src in state.get("retrieved_sources", []):
        parts.append(f"[{src['source']}]\n{src['excerpt']}")
    if not parts:
        return "(no evidence retrieved)"
    return "\n\n".join(parts)


@_timed("synthesize")
def synthesize_answer(state: AgentState) -> dict:
    llm = get_llm()
    evidence = _build_evidence_block(state)
    prompt = SYNTHESIS_PROMPT.format(question=state["question"], evidence=evidence)
    answer = llm.invoke(prompt).content.strip()
    return {"answer": answer}


@_timed("validate")
def validate_answer(state: AgentState) -> dict:
    # If the SQL step failed outright and there is no other evidence, fail validation directly.
    has_evidence = bool(state.get("sql_result_text")) or bool(state.get("retrieved_sources"))
    if not has_evidence:
        return {
            "validation_passed": False,
            "validation_reason": state.get("failure_reason") or "No evidence was available to ground an answer.",
            "confidence": 0.0,
        }

    llm = get_llm()
    evidence = _build_evidence_block(state)
    prompt = VALIDATION_PROMPT.format(
        question=state["question"], evidence=evidence, answer=state["answer"]
    )
    raw = llm.invoke(prompt).content

    verdict_match = re.search(r"VERDICT:\s*(PASS|FAIL)", raw, re.IGNORECASE)
    confidence_match = re.search(r"CONFIDENCE:\s*([0-9.]+)", raw)
    reason_match = re.search(r"REASON:\s*(.+)", raw)

    passed = bool(verdict_match) and verdict_match.group(1).upper() == "PASS"
    confidence = float(confidence_match.group(1)) if confidence_match else (0.5 if passed else 0.2)
    reason = reason_match.group(1).strip() if reason_match else raw.strip()

    if confidence < settings.confidence_threshold:
        passed = False

    return {"validation_passed": passed, "validation_reason": reason, "confidence": confidence}


def prepare_retry(state: AgentState) -> dict:
    # Clear the prior failure reason so a successful retry branch doesn't get shadowed
    # by the _first_non_null reducer picking up the stale value.
    return {"retry_count": state.get("retry_count", 0) + 1, "failure_reason": None}


# --------------------------------------------------------------------------- #
# Conditional edge routers
# --------------------------------------------------------------------------- #


def fan_out_tools(state: AgentState) -> list[str]:
    route = state["route"]
    if route == "sql":
        return ["run_sql"]
    if route == "document":
        return ["run_retrieval"]
    return ["run_sql", "run_retrieval"]


def after_validation(state: AgentState) -> str:
    if state.get("validation_passed"):
        return "end"
    if state.get("retry_count", 0) >= state.get("max_retries", settings.max_retries):
        return "end"
    return "retry"


# --------------------------------------------------------------------------- #
# Graph assembly
# --------------------------------------------------------------------------- #


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("router", route_question)
    graph.add_node("run_sql", run_sql)
    graph.add_node("run_retrieval", run_retrieval)
    graph.add_node("synthesize", synthesize_answer)
    graph.add_node("validate", validate_answer)
    graph.add_node("prepare_retry", prepare_retry)

    graph.set_entry_point("router")
    graph.add_conditional_edges("router", fan_out_tools, ["run_sql", "run_retrieval"])
    graph.add_edge("run_sql", "synthesize")
    graph.add_edge("run_retrieval", "synthesize")
    graph.add_edge("synthesize", "validate")
    graph.add_conditional_edges("validate", after_validation, {"end": END, "retry": "prepare_retry"})
    graph.add_conditional_edges("prepare_retry", fan_out_tools, ["run_sql", "run_retrieval"])

    return graph.compile()


_compiled_graph = None


def get_agent():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def run_agent(question: str) -> AgentState:
    agent = get_agent()
    start = time.perf_counter()
    final_state = agent.invoke({"question": question})
    final_state["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
    return final_state
