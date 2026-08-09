"""Tests for the deterministic refund-eligibility logic in src/db_tools.py.

This is the highest-value place to test in the whole app: a bug here
(validate_refund_eligibility never being wired into the agent workflow, and
then a parameter-chaining bug once it was) previously let an order 541 days
past its 45-day return window get approved. See CLAUDE.md for the incident.
"""

from datetime import datetime, timedelta

from database_creation import Order, ProcessedRequest

import src.db_tools as db_tools


def _add_order(session_factory, order_id, delivery_days_ago, product_id="PROD001",
                customer_id="CUST001", status="Delivered"):
    session = session_factory()
    order_date = datetime.now() - timedelta(days=delivery_days_ago + 2)
    delivery_date = datetime.now() - timedelta(days=delivery_days_ago) if status in ("Delivered", "Shipped") else None
    session.add(Order(
        order_id=order_id, customer_id=customer_id, product_id=product_id,
        order_date=order_date, quantity=1, unit_price=50.0, total_amount=50.0,
        status=status, delivery_date=delivery_date, shipping_address="test",
    ))
    session.commit()
    session.close()


def test_eligible_within_return_window(test_db):
    _add_order(test_db, "ORD001", delivery_days_ago=5)  # window is 30 days
    result = db_tools.validate_refund_eligibility.invoke({"order_id": "ORD001"})
    assert result["eligible"] is True


def test_not_eligible_outside_return_window(test_db):
    _add_order(test_db, "ORD002", delivery_days_ago=45)  # window is 30 days
    result = db_tools.validate_refund_eligibility.invoke({"order_id": "ORD002"})
    assert result["eligible"] is False
    assert "expired" in result["reason"].lower()


def test_not_eligible_order_not_found(test_db):
    result = db_tools.validate_refund_eligibility.invoke({"order_id": "DOES_NOT_EXIST"})
    assert result["eligible"] is False
    assert result["reason"] == "Order not found"


def test_not_eligible_wrong_customer(test_db):
    _add_order(test_db, "ORD003", delivery_days_ago=5)
    result = db_tools.validate_refund_eligibility.invoke({"order_id": "ORD003", "customer_id": "SOMEONE_ELSE"})
    assert result["eligible"] is False
    assert "does not belong" in result["reason"].lower()


def test_eligibility_skips_ownership_check_when_customer_id_omitted(test_db):
    # The agent should never need to chain a customer_id from a prior tool call
    # just to check eligibility - order_id alone must be enough.
    _add_order(test_db, "ORD004", delivery_days_ago=5)
    result = db_tools.validate_refund_eligibility.invoke({"order_id": "ORD004"})
    assert result["eligible"] is True


def test_not_eligible_not_delivered(test_db):
    _add_order(test_db, "ORD005", delivery_days_ago=0, status="Processing")
    result = db_tools.validate_refund_eligibility.invoke({"order_id": "ORD005"})
    assert result["eligible"] is False
    assert "not been delivered" in result["reason"].lower()


def test_blocked_by_previous_approved_refund(test_db):
    _add_order(test_db, "ORD006", delivery_days_ago=5)
    session = test_db()
    session.add(ProcessedRequest(
        request_id="REQ1", customer_id="CUST001", order_id="ORD006", product_id="PROD001",
        request_type="Refund", reason="test", description="test", request_date=datetime.now(),
        status="Approved", decision_reason="ok", refund_amount=50.0, processing_date=datetime.now(),
    ))
    session.commit()
    session.close()

    result = db_tools.validate_refund_eligibility.invoke({"order_id": "ORD006"})
    assert result["eligible"] is False
    assert "already been refunded" in result["reason"].lower()


def test_check_previous_refund_requests_no_history(test_db):
    _add_order(test_db, "ORD007", delivery_days_ago=5)
    result = db_tools.check_previous_refund_requests.invoke({"order_id": "ORD007"})
    assert result["has_previous_requests"] is False


def test_check_previous_refund_requests_order_not_found(test_db):
    result = db_tools.check_previous_refund_requests.invoke({"order_id": "NOPE"})
    assert result["has_previous_requests"] is False
    assert "error" in result


def test_check_previous_refund_requests_pending_does_not_block(test_db):
    _add_order(test_db, "ORD008", delivery_days_ago=5)
    session = test_db()
    session.add(ProcessedRequest(
        request_id="REQ2", customer_id="CUST001", order_id="ORD008", product_id="PROD001",
        request_type="Refund", reason="test", description="test", request_date=datetime.now(),
        status="In Progress", decision_reason="", refund_amount=0.0, processing_date=datetime.now(),
    ))
    session.commit()
    session.close()

    result = db_tools.check_previous_refund_requests.invoke({"order_id": "ORD008"})
    assert result["has_previous_requests"] is True
    assert result["blocking"] is False

    # And the full eligibility check should still pass through as eligible.
    eligibility = db_tools.validate_refund_eligibility.invoke({"order_id": "ORD008"})
    assert eligibility["eligible"] is True
