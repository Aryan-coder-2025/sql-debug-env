import sqlite3
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import TaskInfo

logger = logging.getLogger(__name__)

DB_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "databases", "ecommerce.db"
    )
)


def create_db():
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("DROP TABLE IF EXISTS orders")
        conn.execute("DROP TABLE IF EXISTS customers")
        conn.execute(
            """
            CREATE TABLE customers (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name  TEXT    NOT NULL,
                email TEXT    NOT NULL UNIQUE
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE orders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER REFERENCES customers(id),
                amount      REAL    NOT NULL CHECK(amount >= 0)
            )
        """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_orders_customer
            ON orders(customer_id)
        """
        )
        conn.executemany(
            "INSERT INTO customers(name, email) VALUES (?,?)",
            [
                ("Alice", "alice@email.com"),
                ("Bob", "bob@email.com"),
                ("Carol", "carol@email.com"),
            ],
        )
        conn.executemany(
            "INSERT INTO orders(customer_id, amount) VALUES (?,?)",
            [
                (1, 150.0),
                (1, 200.0),
                (2, 300.0),
            ],
        )
        conn.commit()
        conn.close()
        logger.info("ecommerce.db created ok")
    except Exception as e:
        logger.error(f"create_db failed: {e}")
        raise


def get_task() -> TaskInfo:
    create_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        """
        SELECT c.name, o.amount
        FROM customers c
        LEFT JOIN orders o ON c.id = o.customer_id
        ORDER BY c.name, o.amount
    """
    )
    cols = [c[0] for c in cursor.description]
    expected = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()

    return TaskInfo(
        task_id="medium",
        broken_query=(
            "SELECT c.name, o.amount "
            "FROM customers c "
            "INNER JOIN orders o ON c.id = o.customer_id "
            "ORDER BY c.name, o.amount"
        ),
        schema_sql="""
CREATE TABLE customers (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT    NOT NULL,
    email TEXT    NOT NULL UNIQUE
);
CREATE TABLE orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER REFERENCES customers(id),
    amount      REAL    NOT NULL CHECK(amount >= 0)
);""".strip(),
        expected_output=expected,
        db_path=DB_PATH,
    )
