"""Tests for scripts/generate_daily_orders.py, the synthetic order generator
that keeps the demo dataset's order/delivery dates fresh relative to today."""

import pandas as pd

import scripts.generate_daily_orders as gen
from database_creation import Order


def test_generate_orders_creates_requested_count(test_db):
    rows = gen.generate_orders(count=10, seed=1)
    assert len(rows) == 10

    session = test_db()
    assert session.query(Order).count() == 10
    session.close()


def test_generate_orders_references_existing_catalog(test_db):
    rows = gen.generate_orders(count=20, seed=2)
    for row in rows:
        assert row["customer_id"] == "CUST001"
        assert row["product_id"] == "PROD001"


def test_generate_orders_status_and_delivery_consistency(test_db):
    rows = gen.generate_orders(count=50, seed=3)
    for row in rows:
        if row["status"] in ("Delivered", "Shipped"):
            assert row["delivery_date"] is not None
            assert row["delivery_date"] >= row["order_date"]
        else:
            assert row["delivery_date"] is None


def test_generate_orders_ids_dont_collide_across_runs(test_db):
    gen.generate_orders(count=5, seed=4)
    gen.generate_orders(count=5, seed=5)

    session = test_db()
    order_ids = [o.order_id for o in session.query(Order).all()]
    session.close()

    assert len(order_ids) == 10
    assert len(set(order_ids)) == 10


def test_export_to_csv_appends_rows_with_date_only_format(test_db, tmp_path):
    rows = gen.generate_orders(count=3, seed=6)
    csv_path = tmp_path / "orders.csv"

    gen.export_to_csv(rows, csv_path=str(csv_path))

    df = pd.read_csv(csv_path)
    assert len(df) == 3
    # Dates are exported date-only (YYYY-MM-DD), matching the existing seed CSV's format
    for value in df["order_date"]:
        assert len(str(value)) == 10

    # A second export appends rather than overwriting
    gen.export_to_csv(rows, csv_path=str(csv_path))
    df_after = pd.read_csv(csv_path)
    assert len(df_after) == 6


def test_already_ran_today_idempotency(test_db):
    session = test_db()
    assert gen.already_ran_today(session) is False
    session.close()

    gen.mark_ran_today(orders_created=10)

    session = test_db()
    assert gen.already_ran_today(session) is True
    session.close()


def test_mark_ran_today_is_safe_to_call_twice_same_day(test_db):
    # main() with --force re-runs mark_ran_today on a day that already has a
    # row; this must update in place rather than violating the unique constraint.
    gen.mark_ran_today(orders_created=10)
    gen.mark_ran_today(orders_created=5)
