import sqlite3
import os
import sys
import logging
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import TaskInfo

logger = logging.getLogger(__name__)

DB_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "databases", "analytics.db"
    )
)

HARD_SCENARIOS = [
    # ── Original scenarios ──────────────────────────────────────────────────
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
        "description": "Correlated subquery - slow and runs N+1 times",
    },
    {
        "name": "missing_having",
        "broken": """SELECT p.name, SUM(s.amount) AS total
FROM products p
JOIN sales s ON p.id = s.product_id
WHERE COUNT(s.id) > 5
GROUP BY p.id, p.name
ORDER BY p.name""",
        "description": "WHERE instead of HAVING for aggregate filter",
    },
    {
        "name": "wrong_join_type",
        "broken": """SELECT p.name, SUM(s.amount) AS total
FROM products p
RIGHT JOIN sales s ON p.id = s.product_id
GROUP BY p.id, p.name
HAVING COUNT(s.id) > 5
ORDER BY p.name""",
        "description": "RIGHT JOIN instead of JOIN loses some products",
    },
    {
        "name": "missing_group_by_column",
        "broken": """SELECT p.name, p.category, SUM(s.amount) AS total
FROM products p
JOIN sales s ON p.id = s.product_id
GROUP BY p.name
HAVING COUNT(s.id) > 5
ORDER BY p.name""",
        "description": "SELECT includes p.category but GROUP BY only has p.name — p.category is non-aggregated and unaggregated in strict SQL",
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
        "description": "Double join on sales causes duplicated counts",
    },
    # ── NEW: CTE scenario ────────────────────────────────────────────────────
    {
        "name": "cte_wrong_filter",
        "broken": """WITH product_totals AS (
    SELECT p.id, p.name, SUM(s.amount) AS total, COUNT(s.id) AS sale_count
    FROM products p
    JOIN sales s ON p.id = s.product_id
    GROUP BY p.id, p.name
)
SELECT name, total
FROM product_totals
WHERE sale_count > 5
ORDER BY total DESC""",
        "description": "CTE result ordered by total DESC instead of name — returns correct rows but wrong order",
    },
    {
        "name": "cte_self_reference_missing",
        "broken": """WITH ranked AS (
    SELECT p.name, SUM(s.amount) AS total,
           RANK() OVER (ORDER BY SUM(s.amount) DESC) AS rnk
    FROM products p
    JOIN sales s ON p.id = s.product_id
    GROUP BY p.id, p.name
)
SELECT name, total, rnk
FROM products
WHERE rnk <= 10
ORDER BY rnk""",
        "description": "SELECT FROM products instead of FROM ranked CTE — rnk column doesn't exist on products table",
    },
    # ── NEW: Index / performance scenario ────────────────────────────────────
    {
        "name": "missing_index_scan",
        "broken": """SELECT p.name, SUM(s.amount) AS total
FROM products p
JOIN sales s ON CAST(p.id AS TEXT) = CAST(s.product_id AS TEXT)
GROUP BY p.id, p.name
HAVING COUNT(s.id) > 5
ORDER BY p.name""",
        "description": "CAST on join columns prevents index use on idx_sales_product — full table scan on 100k rows",
    },
    # ── NEW: Subquery scenario ───────────────────────────────────────────────
    {
        "name": "subquery_wrong_aggregation_level",
        "broken": """SELECT p.name,
       SUM(s.amount) AS total,
       (SELECT AVG(amount) FROM sales) AS overall_avg
FROM products p
JOIN sales s ON p.id = s.product_id
GROUP BY p.id, p.name
HAVING SUM(s.amount) > (SELECT AVG(amount) FROM sales)
ORDER BY p.name""",
        "description": "Scalar subquery AVG(amount) computes average per sale row, not per product total — HAVING threshold is wrong level of aggregation",
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
            "CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product_id)"
        )

        # Products 1-50 all get sales; Product_51 has NO sales intentionally
        # so that RIGHT JOIN vs INNER JOIN produces different results
        products = [
            (f"Product_{i}", "Cat_A" if i % 2 == 0 else "Cat_B")
            for i in range(1, 52)  # 51 products total
        ]
        conn.executemany("INSERT INTO products(name, category) VALUES (?,?)", products)

        # product_ids 1-50 get sales; product_id 51 gets none
        sales = [((i % 50) + 1, float(i * 10), "2024-01-01") for i in range(1, 100001)]
        conn.executemany(
            "INSERT INTO sales(product_id, amount, sale_date) VALUES (?,?,?)", sales
        )

        conn.commit()
        conn.close()
        logger.info("analytics.db created ok with 100k rows")

    except Exception as e:
        logger.error(f"create_db failed: {e}")
        raise


# Canonical correct query
_CORRECT_SQL = """
    SELECT p.name, SUM(s.amount) AS total
    FROM products p
    JOIN sales s ON p.id = s.product_id
    GROUP BY p.id, p.name
    HAVING COUNT(s.id) > 5
    ORDER BY p.name
"""

# Scenarios whose expected output differs from the canonical query
_CUSTOM_EXPECTED = {
    "missing_group_by_column": """
        SELECT p.name, p.category, SUM(s.amount) AS total
        FROM products p
        JOIN sales s ON p.id = s.product_id
        GROUP BY p.id, p.name, p.category
        HAVING COUNT(s.id) > 5
        ORDER BY p.name
    """,
    "cte_wrong_filter": """
        WITH product_totals AS (
            SELECT p.id, p.name, SUM(s.amount) AS total, COUNT(s.id) AS sale_count
            FROM products p
            JOIN sales s ON p.id = s.product_id
            GROUP BY p.id, p.name
        )
        SELECT name, total
        FROM product_totals
        WHERE sale_count > 5
        ORDER BY name
    """,
    "cte_self_reference_missing": """
        WITH ranked AS (
            SELECT p.name, SUM(s.amount) AS total,
                   RANK() OVER (ORDER BY SUM(s.amount) DESC) AS rnk
            FROM products p
            JOIN sales s ON p.id = s.product_id
            GROUP BY p.id, p.name
        )
        SELECT name, total, rnk
        FROM ranked
        WHERE rnk <= 10
        ORDER BY rnk
    """,
    "subquery_wrong_aggregation_level": """
        SELECT p.name,
               SUM(s.amount) AS total,
               (SELECT AVG(amount) FROM sales) AS overall_avg
        FROM products p
        JOIN sales s ON p.id = s.product_id
        GROUP BY p.id, p.name
        HAVING SUM(s.amount) > (SELECT AVG(total) FROM (
            SELECT SUM(amount) AS total FROM sales GROUP BY product_id
        ))
        ORDER BY p.name
    """,
}


def get_task(scenario_name: str = None) -> TaskInfo:
    create_db()

    if scenario_name:
        scenario = next(
            (s for s in HARD_SCENARIOS if s["name"] == scenario_name), HARD_SCENARIOS[0]
        )
    else:
        scenario = random.choice(HARD_SCENARIOS)

    conn = sqlite3.connect(DB_PATH)
    sql = _CUSTOM_EXPECTED.get(scenario["name"], _CORRECT_SQL)
    cursor = conn.execute(sql)
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
        db_path=DB_PATH,
    )
