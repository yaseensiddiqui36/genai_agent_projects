"""Creates and seeds the enterprise SQLite database with dummy data.

Run with: python -m infinite_coding_round.db.seed
"""

from __future__ import annotations

import sqlite3

from infinite_coding_round.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    region TEXT NOT NULL,
    signup_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
    FOREIGN KEY (product_id) REFERENCES products (product_id)
);

CREATE TABLE IF NOT EXISTS support_tickets (
    ticket_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_id INTEGER,
    subject TEXT NOT NULL,
    status TEXT NOT NULL,
    priority TEXT NOT NULL,
    created_date TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
    FOREIGN KEY (order_id) REFERENCES orders (order_id)
);
"""

CUSTOMERS = [
    (1, "Alice Chen", "alice.chen@example.com", "North America", "2023-01-15"),
    (2, "Bruno Silva", "bruno.silva@example.com", "South America", "2023-02-20"),
    (3, "Chidi Okafor", "chidi.okafor@example.com", "Africa", "2023-03-05"),
    (4, "Diya Sharma", "diya.sharma@example.com", "Asia", "2023-04-12"),
    (5, "Emma Novak", "emma.novak@example.com", "Europe", "2023-05-30"),
    (6, "Felix Wagner", "felix.wagner@example.com", "Europe", "2023-06-18"),
    (7, "Grace Kim", "grace.kim@example.com", "Asia", "2023-07-22"),
    (8, "Hassan Ali", "hassan.ali@example.com", "Middle East", "2023-08-09"),
    (9, "Ivy Zhang", "ivy.zhang@example.com", "Asia", "2023-09-14"),
    (10, "Jack Miller", "jack.miller@example.com", "North America", "2023-10-01"),
]

PRODUCTS = [
    (1, "Wireless Mouse", "Electronics", 25.99),
    (2, "Mechanical Keyboard", "Electronics", 89.99),
    (3, "USB-C Hub", "Electronics", 39.99),
    (4, "Standing Desk", "Furniture", 349.00),
    (5, "Ergonomic Chair", "Furniture", 259.50),
    (6, "Noise Cancelling Headphones", "Electronics", 199.99),
    (7, "4K Monitor", "Electronics", 329.00),
    (8, "Laptop Stand", "Accessories", 45.00),
    (9, "Webcam HD", "Electronics", 59.99),
    (10, "Desk Lamp", "Accessories", 22.50),
]

ORDERS = [
    (1, 1, 4, 1, "2024-01-10", "delivered"),
    (2, 1, 1, 2, "2024-01-10", "delivered"),
    (3, 2, 6, 1, "2024-02-05", "delivered"),
    (4, 3, 2, 1, "2024-02-18", "cancelled"),
    (5, 4, 7, 1, "2024-03-02", "delivered"),
    (6, 5, 5, 1, "2024-03-15", "shipped"),
    (7, 6, 3, 3, "2024-03-20", "delivered"),
    (8, 7, 9, 1, "2024-04-01", "delivered"),
    (9, 8, 4, 1, "2024-04-11", "returned"),
    (10, 9, 8, 2, "2024-04-19", "delivered"),
    (11, 10, 6, 1, "2024-05-03", "delivered"),
    (12, 2, 10, 4, "2024-05-14", "shipped"),
    (13, 3, 7, 1, "2024-05-22", "delivered"),
    (14, 1, 9, 1, "2024-06-01", "delivered"),
    (15, 4, 2, 1, "2024-06-10", "returned"),
]

SUPPORT_TICKETS = [
    (1, 9, 10, "Received wrong item color", "closed", "medium", "2024-04-20"),
    (2, 8, 4, "Standing desk motor is noisy, requesting refund", "resolved", "high", "2024-04-12"),
    (3, 3, 4, "Order cancelled, wanted status update", "closed", "low", "2024-02-19"),
    (4, 4, 2, "Keyboard arrived with a defective key, needs replacement", "open", "high", "2024-06-12"),
    (5, 1, 4, "Standing desk arrived with a scratch", "open", "medium", "2024-01-12"),
    (6, 6, 3, "Missing one USB-C hub from order of three", "resolved", "medium", "2024-03-21"),
    (7, 10, 6, "Headphones left earcup not producing sound", "escalated", "high", "2024-05-05"),
    (8, 2, 12, "Desk lamp flickers intermittently", "open", "low", "2024-05-16"),
]


def seed_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.executescript(SCHEMA)
        cur.executemany("DELETE FROM customers WHERE customer_id = ?", [])
        cur.execute("DELETE FROM support_tickets")
        cur.execute("DELETE FROM orders")
        cur.execute("DELETE FROM products")
        cur.execute("DELETE FROM customers")
        cur.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?)", CUSTOMERS)
        cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", PRODUCTS)
        cur.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)", ORDERS)
        cur.executemany(
            "INSERT INTO support_tickets VALUES (?, ?, ?, ?, ?, ?, ?)", SUPPORT_TICKETS
        )
        conn.commit()
    finally:
        conn.close()
    print(f"Seeded database at {DB_PATH}")


if __name__ == "__main__":
    seed_database()
