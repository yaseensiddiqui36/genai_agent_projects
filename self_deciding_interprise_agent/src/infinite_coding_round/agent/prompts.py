"""Prompt templates used by the agent graph nodes."""

from infinite_coding_round.tools.sql_tool import SCHEMA_DESCRIPTION

ROUTER_PROMPT = """You are a routing engine for an enterprise data assistant.
Decide which tool(s) are needed to answer the user's question.

- "sql": the question needs structured data from the database (customers, orders, \
products, support ticket records/status/counts).
- "document": the question needs enterprise policy knowledge (refund rules, \
escalation rules, support procedures).
- "hybrid": the question needs both structured data AND policy knowledge to answer \
(e.g. "should this specific order be refunded/escalated").

Database schema available for "sql":
{schema}

Respond in exactly this format:
ROUTE: <sql, document, or hybrid>
REASONING: <one concise sentence explaining why this route was chosen>

Question: {question}
"""

SQL_GENERATION_PROMPT = """You write read-only SQLite SELECT queries for an enterprise database.

Schema:
{schema}

Rules:
- Output ONLY the SQL query, no explanation, no markdown fences.
- Only generate SELECT statements (a leading WITH clause is allowed before SELECT).
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, or PRAGMA.
- Use explicit column names rather than SELECT *.
- Add a LIMIT clause if the result could be large.

Question: {question}
{retry_context}
SQL query:
"""

SQL_RETRY_CONTEXT = """
The previous attempt failed with this error, fix the query:
Previous SQL: {previous_sql}
Error: {error}
"""

SYNTHESIS_PROMPT = """You are an enterprise support assistant. Answer the user's question \
using ONLY the evidence provided below. Cite sources inline using the bracketed tags shown \
(e.g. [refund_policy.md] or [SQL result]). If the evidence is insufficient to answer \
confidently, say so explicitly instead of guessing.

Question: {question}

Evidence:
{evidence}

Write a concise, accurate answer grounded strictly in the evidence above, with inline \
citations.
"""

VALIDATION_PROMPT = """You are a strict fact-checking validator. Determine whether the ANSWER \
below is fully grounded in the EVIDENCE, with no unsupported claims or hallucinated facts.

Question: {question}

Evidence:
{evidence}

Answer:
{answer}

Respond in exactly this format:
VERDICT: <PASS or FAIL>
CONFIDENCE: <a number between 0.0 and 1.0>
REASON: <one sentence explaining the verdict>
"""

SCHEMA_FOR_PROMPTS = SCHEMA_DESCRIPTION
