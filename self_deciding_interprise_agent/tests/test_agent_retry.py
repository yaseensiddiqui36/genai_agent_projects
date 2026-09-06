"""Deterministic test of the retry-on-invalid-SQL path using a scripted fake LLM.

Real LLM calls are non-deterministic (the model often self-corrects SQL on the first
try), so this test stubs the LLM to force a genuine SQL execution failure on attempt
one, and verifies the graph retries exactly once and recovers.
"""

from dataclasses import dataclass

from infinite_coding_round.agent import graph as agent_graph


@dataclass
class _FakeMessage:
    content: str


class _FakeLLM:
    def __init__(self):
        self.sql_calls = 0

    def invoke(self, prompt: str) -> _FakeMessage:
        if "You are a routing engine" in prompt:
            return _FakeMessage("ROUTE: sql\nREASONING: The question asks for a row count.")
        if "SQL query:" in prompt:
            self.sql_calls += 1
            if self.sql_calls == 1:
                return _FakeMessage("SELECT * FROM not_a_real_table")
            return _FakeMessage("SELECT COUNT(*) AS n FROM customers")
        if "VERDICT" in prompt:
            return _FakeMessage("VERDICT: PASS\nCONFIDENCE: 0.9\nREASON: Grounded in SQL result.")
        return _FakeMessage("There are 10 customers, based on [SQL result].")


def test_invalid_sql_triggers_single_retry_and_recovers(monkeypatch):
    fake = _FakeLLM()
    monkeypatch.setattr(agent_graph, "get_llm", lambda temperature=0.0: fake)

    final_state = agent_graph.run_agent("How many customers are there?")

    assert fake.sql_calls == 2, "expected exactly one retry (two SQL generation attempts)"
    assert final_state["retry_count"] == 1
    assert final_state["sql_error"] is None
    assert final_state["sql_query"] == "SELECT COUNT(*) AS n FROM customers"
    assert final_state["validation_passed"] is True
    assert final_state["reasoning"] == "The question asks for a row count."
    assert final_state["latency_ms"] >= 0
    assert "router" in final_state["node_latencies_ms"]
    assert "run_sql" in final_state["node_latencies_ms"]


def test_retry_budget_is_not_exceeded(monkeypatch):
    """Even if the SQL keeps failing, the graph must stop after max_retries."""

    class _AlwaysBadSQL(_FakeLLM):
        def invoke(self, prompt: str) -> _FakeMessage:
            if "Respond with ONLY one word" in prompt:
                return _FakeMessage("sql")
            if "SQL query:" in prompt:
                self.sql_calls += 1
                return _FakeMessage("SELECT * FROM not_a_real_table")
            if "VERDICT" in prompt:
                return _FakeMessage("VERDICT: FAIL\nCONFIDENCE: 0.1\nREASON: No evidence.")
            return _FakeMessage("Unable to answer.")

    fake = _AlwaysBadSQL()
    monkeypatch.setattr(agent_graph, "get_llm", lambda temperature=0.0: fake)

    final_state = agent_graph.run_agent("How many customers are there?")

    assert final_state["retry_count"] == 1  # max_retries defaults to 1
    assert final_state["validation_passed"] is False
    assert fake.sql_calls == 2
