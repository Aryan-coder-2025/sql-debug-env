import sqlite3
import os
import sys
import logging
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import TaskInfo

logger = logging.getLogger(__name__)

DB_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "databases", "analytics.db"
))

HARD_SCENARIOS = [
    {
        "name": "correlated_subquery",
        "broken": """SELECT p.name,
       (SELECT SUM(s2.amount)
        FROM sales s2
        WHERE s2.product_id = p.id) AS total
FROM products p
WHERE (SELECT COUNT(*)
       FROM sales s3
       WHERE s3.product_id = p.id) > 5
ORDER BY p.name""",
        "description": "Correlated subquery - slow and runs N+1 times"
    },
    {
        "name": "missing_having",
        "broken": """SELECT p.name, SUM(s.amount) AS total
FROM products p
JOIN sales s ON p.id = s.product_id
WHERE COUNT(s.id) > 5
GROUP BY p.id, p.name
ORDER BY p.name""",
        "description": "WHERE instead of HAVING for aggregate filter"
    },
    {
        "name": "wrong_join_type",
        "broken": """SELECT p.name, SUM(s.amount) AS total
FROM products p
RIGHT JOIN sales s ON p.id = s.product_id
GROUP BY p.id, p.name
HAVING COUNT(s.id) > 5
ORDER BY p.name""",
        "description": "RIGHT JOIN instead of JOIN loses some products"
    },
    {
        "name": "missing_group_by_column",
        "broken": """SELECT p.name, SUM(s.amount) AS total
FROM products p
JOIN sales s ON p.id = s.product_id
GROUP BY p.name
HAVING COUNT(s.id) > 5
ORDER BY p.name""",
        "description": "GROUP BY missing p.id causes ambiguous grouping"
    },
    {
        "name": "double_count",
        "broken": """SELECT p.name,
       SUM(s.amount) AS total,
       COUNT(s.id) AS sale_count
FROM products p
JOIN sales s ON p.id = s.product_id
JOIN sales s2 ON p.id = s2.product_id
GROUP BY p.id, p.name
HAVING COUNT(s.id) > 5
ORDER BY p.name""",
        "description": "Double join on sales causes duplicated counts"
    },
]


def create_db():
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)

        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")

        conn.execute("DROP TABLE IF EXISTS sales")
        conn.execute("DROP TABLE IF EXISTS products")

        conn.execute("""
            CREATE TABLE products (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT    NOT NULL UNIQUE,
                category TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE sales (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL REFERENCES products(id),
                amount     REAL    NOT NULL CHECK(amount > 0),
                sale_date  TEXT    NOT NULL
            )
        """)

        products = [
            (f"Product_{i}", "Cat_A" if i % 2 == 0 else "Cat_B")
            for i in range(1, 51)
        ]
        conn.executemany(
            "INSERT INTO products(name, category) VALUES (?,?)",
            products
        )

        sales = [
            ((i % 50) + 1, float(i * 10), "2024-01-01")
            for i in range(1, 100001)
        ]
        conn.executemany(
            "INSERT INTO sales(product_id, amount, sale_date) VALUES (?,?,?)",
            sales
        )

        conn.commit()
        conn.close()
        logger.info("analytics.db created ok with 100k rows")

    except Exception as e:
        logger.error(f"create_db failed: {e}")
        raise


def get_task(scenario_name: str = None) -> TaskInfo:
    create_db()

    if scenario_name:
        scenario = next(
            (s for s in HARD_SCENARIOS if s["name"] == scenario_name),
            HARD_SCENARIOS[0]
        )
    else:
        scenario = random.choice(HARD_SCENARIOS)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT p.name, SUM(s.amount) AS total
        FROM products p
        JOIN sales s ON p.id = s.product_id
        GROUP BY p.id, p.name
        HAVING COUNT(s.id) > 5
        ORDER BY p.name
    """)
    cols = [c[0] for c in cursor.description]
    expected = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()

    return TaskInfo(
        task_id="hard",
        broken_query=scenario["broken"],
        schema_sql="""CREATE TABLE products (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT    NOT NULL UNIQUE,
    category TEXT    NOT NULL
);
CREATE TABLE sales (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    amount     REAL    NOT NULL CHECK(amount > 0),
    sale_date  TEXT    NOT NULL
);
CREATE INDEX idx_sales_product ON sales(product_id);""",
        expected_output=expected,
        db_path=DB_PATH
    )