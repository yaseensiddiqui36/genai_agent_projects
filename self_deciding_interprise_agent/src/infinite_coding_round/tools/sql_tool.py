"""Read-only SQL generation and execution against the enterprise SQLite database."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

from infinite_coding_round.config import DB_PATH, settings

_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum)\b",
    re.IGNORECASE,
)

SCHEMA_DESCRIPTION = """\
Table customers(customer_id INTEGER, name TEXT, email TEXT, region TEXT, signup_date TEXT)
Table products(product_id INTEGER, name TEXT, category TEXT, price REAL)
Table orders(order_id INTEGER, customer_id INTEGER, product_id INTEGER, quantity INTEGER, \
order_date TEXT, status TEXT)  -- status is one of: shipped, delivered, cancelled, returned
Table support_tickets(ticket_id INTEGER, customer_id INTEGER, order_id INTEGER, subject TEXT, \
status TEXT, priority TEXT, created_date TEXT)  -- status is one of: open, resolved, closed, \
escalated; priority is one of: low, medium, high
"""


@dataclass
class SQLExecutionResult:
    query: str
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None

    def as_markdown_table(self) -> str:
        if not self.success:
            return f"(query failed: {self.error})"
        if not self.rows:
            return "(no rows returned)"
        header = " | ".join(self.columns)
        sep = " | ".join("---" for _ in self.columns)
        body = "\n".join(" | ".join(str(v) for v in row) for row in self.rows)
        return f"{header}\n{sep}\n{body}"


def validate_read_only(sql: str) -> str | None:
    """Returns an error message if the SQL is not a safe, read-only SELECT."""
    stripped = sql.strip().rstrip(";")
    if not stripped:
        return "Empty SQL query."
    if not re.match(r"^\s*(with\b.*?)?select\b", stripped, re.IGNORECASE | re.DOTALL):
        return "Only SELECT (optionally with a WITH clause) statements are allowed."
    if _FORBIDDEN_KEYWORDS.search(stripped):
        return "Query contains a forbidden write/DDL keyword."
    if ";" in stripped:
        return "Multiple statements are not allowed."
    return None


def execute_readonly_sql(sql: str) -> SQLExecutionResult:
    """Executes a validated, read-only SQL query with a row limit and returns results."""
    error = validate_read_only(sql)
    if error:
        return SQLExecutionResult(query=sql, error=error)

    limited_sql = sql.strip().rstrip(";")
    if "limit" not in limited_sql.lower():
        limited_sql = f"{limited_sql} LIMIT {settings.sql_row_limit}"

    uri = f"file:{DB_PATH}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        try:
            cur = conn.cursor()
            cur.execute(limited_sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return SQLExecutionResult(query=sql, columns=columns, rows=rows)
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return SQLExecutionResult(query=sql, error=str(exc))
