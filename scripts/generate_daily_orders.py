"""Generate synthetic daily order volume for demo/testing purposes.

The bundled dataset (data/*.csv) is a static snapshot, so its order/delivery
dates drift into the past every day the demo runs - eventually every order
falls outside any product's return window and the refund workflow can never
demonstrate an approval. This script simulates a live order stream by
inserting a batch of new orders against the existing customer/product
catalog, dated relative to *today*, so there's always a realistic mix of
recently-delivered (in-window) and older (out-of-window) orders to test
against.

Idempotent per calendar day: running it twice on the same day is a no-op
unless --force is passed, so it's safe to invoke from a daily scheduler
(cron, Task Scheduler, GitHub Actions) without double-inserting.

Usage:
    python scripts/generate_daily_orders.py [--count 100] [--force] [--seed 42]
"""

import argparse
import logging
import os
import random
import sys
from datetime import datetime, timedelta

from faker import Faker
from sqlalchemy import func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_creation import Customer, Order, Product, SessionLocal, SyntheticDataRun

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

fake = Faker()

# Roughly matches the distribution in the original seed dataset
STATUS_WEIGHTS = {
    "Delivered": 0.80,
    "Shipped": 0.10,
    "Processing": 0.05,
    "Cancelled": 0.05,
}

# Orders are dated across the last ~75 days so, combined with products' return
# windows (14-45 days in the seed data), a meaningful mix ends up inside and
# outside their return window - not just uniformly all-eligible or all-expired.
MAX_ORDER_AGE_DAYS = 75


def _next_order_id(session) -> int:
    """Continue the ORD###### numbering sequence from whatever's already in the DB."""
    last_id = session.query(func.max(Order.order_id)).scalar()
    if not last_id:
        return 1
    return int(last_id.replace("ORD", "")) + 1


def already_ran_today(session) -> bool:
    today = datetime.now().date().isoformat()
    return session.query(SyntheticDataRun).filter(SyntheticDataRun.run_date == today).first() is not None


def generate_orders(count: int = 100, seed: int = None) -> list:
    """Insert `count` new synthetic orders against the existing catalog.

    Returns the list of created rows as plain dicts (used both for the DB insert
    and, by the caller, to append the same rows to data/orders.csv for a
    text-diffable git history).
    """
    if seed is not None:
        random.seed(seed)
        Faker.seed(seed)

    session = SessionLocal()
    try:
        customer_ids = [row[0] for row in session.query(Customer.customer_id).all()]
        products = session.query(Product).all()
        if not customer_ids or not products:
            raise RuntimeError(
                "No customers/products found in the database - run database_creation.py first"
            )

        next_num = _next_order_id(session)
        statuses = list(STATUS_WEIGHTS.keys())
        weights = list(STATUS_WEIGHTS.values())

        rows = []
        for i in range(count):
            customer_id = random.choice(customer_ids)
            product = random.choice(products)
            status = random.choices(statuses, weights=weights, k=1)[0]

            order_date = datetime.now() - timedelta(
                days=random.randint(0, MAX_ORDER_AGE_DAYS), hours=random.randint(0, 23)
            )
            delivery_date = None
            if status in ("Delivered", "Shipped"):
                delivery_date = order_date + timedelta(days=random.randint(1, 7))

            quantity = random.randint(1, 3)
            total_amount = round(product.price * quantity, 2)

            rows.append({
                "order_id": f"ORD{next_num + i:06d}",
                "customer_id": customer_id,
                "product_id": product.product_id,
                "order_date": order_date,
                "quantity": quantity,
                "unit_price": product.price,
                "total_amount": total_amount,
                "status": status,
                "delivery_date": delivery_date,
                "shipping_address": fake.address().replace("\n", ", "),
            })

        for row in rows:
            session.add(Order(**row))
        session.commit()
        return rows
    finally:
        session.close()


def export_to_csv(rows: list, csv_path: str = "data/orders.csv"):
    """Append newly generated orders to the CSV seed file (date-only, matching its existing format)."""
    import pandas as pd

    formatted = []
    for row in rows:
        formatted.append({
            **row,
            "order_date": row["order_date"].strftime("%Y-%m-%d"),
            "delivery_date": row["delivery_date"].strftime("%Y-%m-%d") if row["delivery_date"] else "",
        })

    new_df = pd.DataFrame(formatted)
    file_exists = os.path.exists(csv_path)
    new_df.to_csv(csv_path, mode="a", header=not file_exists, index=False)


def mark_ran_today(orders_created: int):
    """Record (or update, if --force re-ran today) today's generation run."""
    session = SessionLocal()
    try:
        today = datetime.now().date().isoformat()
        run = session.query(SyntheticDataRun).filter(SyntheticDataRun.run_date == today).first()
        if run:
            run.orders_created += orders_created
            run.run_timestamp = datetime.now()
        else:
            session.add(SyntheticDataRun(
                run_date=today,
                orders_created=orders_created,
                run_timestamp=datetime.now(),
            ))
        session.commit()
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic daily order volume")
    parser.add_argument("--count", type=int, default=100, help="Number of orders to generate")
    parser.add_argument("--force", action="store_true", help="Generate even if already run today")
    parser.add_argument("--seed", type=int, default=None, help="Random seed, for reproducible test runs")
    parser.add_argument(
        "--no-csv-export", action="store_true",
        help="Skip appending to data/orders.csv (DB-only; CSV export is on by default so a git-based "
             "deploy like Streamlit Cloud can commit the new rows and rebuild on next boot)",
    )
    args = parser.parse_args()

    session = SessionLocal()
    try:
        if not args.force and already_ran_today(session):
            logger.info(
                "Synthetic orders already generated today (%s); skipping. Use --force to override.",
                datetime.now().date().isoformat(),
            )
            return
    finally:
        session.close()

    rows = generate_orders(count=args.count, seed=args.seed)
    mark_ran_today(len(rows))

    if not args.no_csv_export:
        export_to_csv(rows)

    logger.info("Created %d new synthetic orders.", len(rows))


if __name__ == "__main__":
    main()
