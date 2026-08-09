import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import scripts.generate_daily_orders as generate_daily_orders
import src.db_tools as db_tools
from database_creation import Base, Customer, Product


@pytest.fixture()
def test_db(tmp_path, monkeypatch):
    """Isolated SQLite database for a single test, seeded with one customer/product.

    Patches the SessionLocal that db_tools.py and scripts/generate_daily_orders.py
    already bound at import time, so tests never touch the real refunds_agent.db.
    """
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setattr(db_tools, "SessionLocal", TestSessionLocal)
    monkeypatch.setattr(generate_daily_orders, "SessionLocal", TestSessionLocal)

    session = TestSessionLocal()
    session.add(Customer(
        customer_id="CUST001", first_name="Jane", last_name="Doe",
        email="jane@example.com", customer_tier="Silver",
    ))
    session.add(Product(
        product_id="PROD001", product_name="Widget", category="Electronics",
        price=50.0, return_window_days=30, fragile=False, restockable=True,
    ))
    session.commit()
    session.close()

    yield TestSessionLocal
