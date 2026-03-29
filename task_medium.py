import sqlite3
import os
import logging
from models import TaskInfo

logger = logging.getLogger(_name_)

DB_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(_file_)),
    "..", "databases", "ecommerce.db"
))


def create_db():
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        conn.execute("DROP TABLE IF EXISTS orders")
        conn.execute("DROP TABLE IF EXISTS customers")

        conn.execute("""
            CREATE TABLE customers (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name  TEXT    NOT NULL,
                email TEXT    NOT NULL UNIQUE
            )
        """)

        conn.execute("""
            CREATE TABLE orders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER REFERENCES customers(id),
                amount      REAL    NOT NULL CHECK(amount >= 0),
                order_date  TEXT    DEFAULT (date('now'))
            )
        """)

        conn.execute("""
            CREATE INDEX idx_orders_customer
            ON orders(customer_id)
        """)

        conn.executemany(
            "INSERT INTO customers(name, email) VALUES (?,?)",
            [
                ("Alice", "alice@email.com"),
                ("Bob",   "bob@email.com"),
                ("Carol", "carol@email.com"),  # Carol has NO orders on purpose
            ]
        )

        conn.executemany(
            "INSERT INTO orders(customer_id, amount) VALUES (?,?)",
            [
                (1, 150.0),
                (1, 200.0),
                (2, 300.0),
                # customer_id 3 (Carol) intentionally has no orders
                # This is what makes INNER JOIN vs LEFT JOIN matter
            ]
        )

        conn.commit()
        conn.close()
        logger.info("ecommerce.db created successfully")

    except Exception as e:
        logger.error(f"Failed to create ecommerce.db: {e}")
        raise


def get_task() -> TaskInfo:
    create_db()

    # Get expected output directly from DB using the CORRECT query
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT c.name, o.amount
        FROM customers c
        LEFT JOIN orders o ON c.id = o.customer_id
        ORDER BY c.name, o.amount
    """)
    cols = [c[0] for c in cursor.description]
    expected = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()

    return TaskInfo(
        task_id="medium",
        broken_query="""
SELECT c.name, o.amount
FROM customers c
INNER JOIN orders o ON c.id = o.customer_id
ORDER BY c.name, o.amount
        """.strip(),
        schema_sql="""
CREATE TABLE customers (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT    NOT NULL,
    email TEXT    NOT NULL UNIQUE
);
CREATE TABLE orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER REFERENCES customers(id),
    amount      REAL    NOT NULL CHECK(amount >= 0),
    order_date  TEXT    DEFAULT (date('now'))
);
CREATE INDEX idx_orders_customer ON orders(customer_id);
        """.strip(),
        expected_output=expected,
        db_path=DB_PATH
    )