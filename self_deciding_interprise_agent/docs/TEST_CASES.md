# Test Cases — Self-Correcting Enterprise Data Agent

These are the 5 mandatory test cases from the task spec, run against `POST /ask`.
Outputs below are captured from real runs (LLM: `llama-3.3-70b-versatile` via Groq,
temperature 0), except where noted. LLM wording will vary slightly between runs since
the model is not fully deterministic; the **structure and routing behavior** shown
here is what's being verified, not exact wording.

Run the automated, deterministic checks with:

```bash
uv run python -m pytest tests/ -q
```

Note: the abridged JSON snippets below predate two fields that are now always present
on every response — `reasoning` (the router's rationale for the sql/document/hybrid
choice) and `latency_ms` / `node_latencies_ms` (timing). They're omitted here only to
keep the examples focused on routing/grounding behavior; see the main
[README](../README.md#response-shape-post-ask) for the full current shape.

---

## 1. SQL-only question

**Request**

```json
{ "question": "How many orders does customer Alice Chen have?" }
```

**Expected behavior**: router selects `sql`, generates a read-only SELECT joining
`customers` and `orders`, executes it, and grounds the answer in the row count only.

**Actual response (abridged)**

```json
{
  "answer": "According to the [SQL result], customer Alice Chen has 3 orders.",
  "tools_used": ["sql"],
  "generated_sql": "SELECT COUNT(o.order_id) FROM customers c JOIN orders o ON c.customer_id = o.customer_id WHERE c.name = 'Alice Chen' LIMIT 1",
  "retrieved_sources": [],
  "confidence": 1.0,
  "validation_passed": true,
  "retry_count": 0
}
```

---

## 2. Document-only question

**Request**

```json
{ "question": "What is the refund window for furniture items?" }
```

**Expected behavior**: router selects `document`, no SQL is generated, retrieved
passages come from `refund_policy.md`, and the answer cites the furniture-specific
45-day window (not the default 30-day window).

**Actual response (abridged)**

```json
{
  "answer": "The refund window for furniture items is 45 days from delivery, as stated in [refund_policy.md] ... instead of the standard 30 days ...",
  "tools_used": ["document_retrieval"],
  "generated_sql": null,
  "retrieved_sources": [{ "source": "refund_policy.md", "excerpt": "..." }],
  "confidence": 1.0,
  "validation_passed": true,
  "retry_count": 0
}
```

---

## 3. Hybrid SQL + document question

**Request**

```json
{
  "question": "Customer Hassan Ali reported a standing desk motor is noisy after 40 days. Is he still eligible for a refund, and does this ticket need to be escalated?"
}
```

**Expected behavior**: router selects `hybrid`; both `run_sql` and `run_retrieval`
execute (in parallel, fanned out from the router), pulling the customer's order/ticket
record AND the refund/escalation policy text, and the final answer combines both kinds
of evidence with citations to each.

**Actual response (abridged)**

```json
{
  "tools_used": ["sql", "document_retrieval"],
  "generated_sql": "SELECT t1.ticket_id, t1.status, t1.priority, t1.created_date, t2.order_date, t2.status FROM support_tickets t1 JOIN orders t2 ON t1.order_id = t2.order_id JOIN customers t3 ON t2.customer_id = t3.customer_id WHERE t3.name = 'Hassan Ali' ...",
  "retrieved_sources": [
    { "source": "refund_policy.md", "excerpt": "..." },
    { "source": "escalation_policy.md", "excerpt": "..." }
  ],
  "confidence": 0.9,
  "validation_passed": true,
  "retry_count": 0
}
```

---

## 4. Invalid SQL generation requiring retry

Because the model frequently self-corrects on the first attempt, we verify the retry
mechanism **deterministically** with a scripted fake LLM
(`tests/test_agent_retry.py::test_invalid_sql_triggers_single_retry_and_recovers`)
rather than relying on the model reliably failing on a live call:

1. First `run_sql` attempt generates `SELECT * FROM not_a_real_table`.
2. `execute_readonly_sql` catches the resulting `sqlite3.OperationalError` and stores
   it as `sql_error` instead of raising.
3. `validate_answer` sees no usable SQL evidence and fails validation.
4. `after_validation` routes to `prepare_retry` (`retry_count` 0 → 1), which clears the
   stale failure reason and re-enters `run_sql` with the previous query + error
   appended to the prompt as retry context.
5. The second attempt generates valid SQL, execution succeeds, and validation passes.

**Expected final state**: `retry_count == 1`, `sql_error is None`, `validation_passed == True`.

A second test, `test_retry_budget_is_not_exceeded`, confirms that if the SQL keeps
failing, the graph stops after exactly one retry (`max_retries = 1` by default) instead
of looping indefinitely, and returns `validation_passed == False`.

---

## 5. Question with insufficient evidence

**Request**

```json
{ "question": "What is the CEO's stance on remote work policy?" }
```

**Expected behavior**: router selects `document` (or `hybrid`), retrieval returns the
closest-matching but topically irrelevant passages (escalation/support guide content),
and the synthesis step must explicitly say the evidence does not answer the question
rather than fabricating a policy that doesn't exist. Validation should pass specifically
*because* the "I don't know" statement is itself grounded in — i.e., consistent with —
the retrieved evidence; if the model asserts something is true without evidence,
validation should fail and retry.

**Actual response (abridged)**

```json
{
  "answer": "The provided evidence does not mention the CEO's stance on remote work policy. The documents [escalation_policy.md] and [support_guide.md] discuss support ticket escalation policies ... Therefore, based on the evidence, it is impossible to determine the CEO's stance on remote work policy.",
  "tools_used": ["document_retrieval"],
  "retrieved_sources": [
    { "source": "escalation_policy.md", "excerpt": "..." },
    { "source": "support_guide.md", "excerpt": "..." }
  ],
  "confidence": 1.0,
  "validation_passed": true,
  "retry_count": 0
}
```

If retrieval returns **zero** passages at all (e.g., an empty/corrupted index),
`validate_answer` short-circuits to `validation_passed = False` with
`validation_reason = "No relevant document passages were retrieved."` before even
calling the LLM validator, since there is nothing to ground an answer in.
