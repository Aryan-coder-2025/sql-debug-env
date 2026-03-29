import sqlite3
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import TaskInfo

logger = logging.getLogger(__name__)

DB_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "databases", "analytics.db"
    )
)


def create_db():
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("DROP TABLE IF EXISTS sales")
        conn.execute("DROP TABLE IF EXISTS products")
        conn.execute(
            """
            CREATE TABLE products (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT    NOT NULL UNIQUE,
                category TEXT    NOT NULL
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE sales (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL REFERENCES products(id),
                amount     REAL    NOT NULL CHECK(amount > 0),
                sale_date  TEXT    NOT NULL
            )
        """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sales_product
            ON sales(product_id)
        """
        )
        products = [
            (f"Product_{i}", "Cat_A" if i % 2 == 0 else "Cat_B") for i in range(1, 51)
        ]
        sales = [((i % 50) + 1, float(i * 10), "2024-01-01") for i in range(1, 1001)]
        conn.executemany("INSERT INTO products(name, category) VALUES (?,?)", products)
        conn.executemany(
            "INSERT INTO sales(product_id, amount, sale_date) VALUES (?,?,?)", sales
        )
        conn.commit()
        conn.close()
        logger.info("analytics.db created ok")
    except Exception as e:
        logger.error(f"create_db failed: {e}")
        raise


def get_task() -> TaskInfo:
    create_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        """
        SELECT p.name, SUM(s.amount) AS total
        FROM products p
        JOIN sales s ON p.id = s.product_id
        GROUP BY p.id, p.name
        HAVING COUNT(s.id) > 5
        ORDER BY p.name
    """
    )
    cols = [c[0] for c in cursor.description]
    expected = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()

    return TaskInfo(
        task_id="hard",
        broken_query="""SELECT p.name,
       (SELECT SUM(s2.amount)
        FROM sales s2
        WHERE s2.product_id = p.id) AS total
FROM products p
WHERE (SELECT COUNT(*)
       FROM sales s3
       WHERE s3.product_id = p.id) > 5
ORDER BY p.name""",
        schema_sql="""
CREATE TABLE products (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT    NOT NULL UNIQUE,
    category TEXT    NOT NULL
);
CREATE TABLE sales (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    amount     REAL    NOT NULL CHECK(amount > 0),
    sale_date  TEXT    NOT NULL
);""".strip(),
        expected_output=expected,
        db_path=DB_PATH,
    )
