from infinite_coding_round.tools.sql_tool import execute_readonly_sql, validate_read_only


def test_rejects_write_statements():
    assert validate_read_only("DROP TABLE customers") is not None
    assert validate_read_only("DELETE FROM orders") is not None
    assert validate_read_only("INSERT INTO customers VALUES (1)") is not None


def test_rejects_multiple_statements():
    assert validate_read_only("SELECT 1; DROP TABLE customers") is not None


def test_allows_select_and_with():
    assert validate_read_only("SELECT * FROM customers") is None
    assert validate_read_only("WITH x AS (SELECT 1) SELECT * FROM x") is None


def test_execute_valid_query_returns_rows():
    result = execute_readonly_sql("SELECT COUNT(*) AS n FROM customers")
    assert result.success
    assert result.rows[0][0] == 10


def test_execute_invalid_sql_reports_error_not_exception():
    result = execute_readonly_sql("SELECT * FROM not_a_real_table")
    assert not result.success
    assert result.error is not None


def test_execute_blocks_write_before_hitting_db():
    result = execute_readonly_sql("DELETE FROM customers")
    assert not result.success
    assert "forbidden" in result.error.lower() or "select" in result.error.lower()
