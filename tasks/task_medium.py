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
        os.path.dirname(os.path.abspath(__file__)), "..", "databases", "ecommerce.db"
    )
)

MEDIUM_SCENARIOS = [
    # ── Original scenarios ──────────────────────────────────────────────────
    {
        "name": "inner_join",
        "broken": """SELECT
    c.name              AS customer_name,
    COUNT(o.id)         AS total_orders,
    COALESCE(SUM(oi.amount), 0) AS total_spent
FROM customers c
INNER JOIN orders o
    ON c.id = o.customer_id
INNER JOIN order_items oi
    ON o.id = oi.order_id
GROUP BY c.id, c.name
ORDER BY c.name""",
        "description": "INNER JOIN loses customers with no orders",
    },
    {
        "name": "wrong_join_condition",
        "broken": """SELECT
    c.name              AS customer_name,
    COUNT(o.id)         AS total_orders,
    COALESCE(SUM(oi.amount), 0) AS total_spent
FROM customers c
LEFT JOIN orders o
    ON c.name = o.customer_id
LEFT JOIN order_items oi
    ON o.id = oi.order_id
GROUP BY c.id, c.name
ORDER BY c.name""",
        "description": "Wrong join condition - comparing name to id",
    },
    {
        "name": "missing_group_by",
        "broken": """SELECT
    c.name              AS customer_name,
    COUNT(o.id)         AS total_orders,
    COALESCE(SUM(oi.amount), 0) AS total_spent
FROM customers c
LEFT JOIN orders o
    ON c.id = o.customer_id
LEFT JOIN order_items oi
    ON o.id = oi.order_id
ORDER BY c.name""",
        "description": "Missing GROUP BY causes wrong aggregation",
    },
    {
        "name": "wrong_count_column",
        "broken": """SELECT
    c.name              AS customer_name,
    COUNT(*)            AS total_orders,
    COALESCE(SUM(oi.amount), 0) AS total_spent
FROM customers c
LEFT JOIN orders o
    ON c.id = o.customer_id
LEFT JOIN order_items oi
    ON o.id = oi.order_id
GROUP BY c.id, c.name
ORDER BY c.name""",
        "description": "COUNT(*) counts nulls, COUNT(o.id) does not",
    },
    {
        "name": "missing_coalesce",
        "broken": """SELECT
    c.name              AS customer_name,
    COUNT(o.id)         AS total_orders,
    SUM(oi.amount)      AS total_spent
FROM customers c
LEFT JOIN orders o
    ON c.id = o.customer_id
LEFT JOIN order_items oi
    ON o.id = oi.order_id
GROUP BY c.id, c.name
ORDER BY c.name""",
        "description": "Missing COALESCE causes NULL instead of 0",
    },
    # ── NEW: JOIN scenarios ──────────────────────────────────────────────────
    {
        "name": "cross_join_missing_on",
        "broken": """SELECT
    c.name              AS customer_name,
    COUNT(o.id)         AS total_orders,
    COALESCE(SUM(oi.amount), 0) AS total_spent
FROM customers c, orders o
LEFT JOIN order_items oi
    ON o.id = oi.order_id
GROUP BY c.id, c.name
ORDER BY c.name""",
        "description": "Implicit comma cross join instead of LEFT JOIN ON produces cartesian product",
    },
    {
        "name": "duplicate_join_inflation",
        "broken": """SELECT
    c.name              AS customer_name,
    COUNT(o.id)         AS total_orders,
    COALESCE(SUM(oi.amount), 0) AS total_spent
FROM customers c
LEFT JOIN orders o     ON c.id = o.customer_id
LEFT JOIN orders o2    ON c.id = o2.customer_id
LEFT JOIN order_items oi ON o.id = oi.order_id
GROUP BY c.id, c.name
ORDER BY c.name""",
        "description": "Double join on orders table inflates order count and total_spent",
    },
    # ── NEW: Subquery / CTE scenario ─────────────────────────────────────────
    {
        "name": "subquery_no_alias",
        "broken": """SELECT customer_name, total_orders, total_spent
FROM (
    SELECT
        c.name              AS customer_name,
        COUNT(o.id)         AS total_orders,
        COALESCE(SUM(oi.amount), 0) AS total_spent
    FROM customers c
    LEFT JOIN orders o ON c.id = o.customer_id
    LEFT JOIN order_items oi ON o.id = oi.order_id
    GROUP BY c.id, c.name
)
ORDER BY customer_name""",
        "description": "Subquery missing alias causes 'every derived table must have its own alias' error",
    },
    # ── NEW: Aggregation / HAVING scenario ───────────────────────────────────
    {
        "name": "having_wrong_alias",
        "broken": """SELECT
    c.name              AS customer_name,
    COUNT(o.id)         AS total_orders,
    COALESCE(SUM(oi.amount), 0) AS total_spent
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
LEFT JOIN order_items oi ON o.id = oi.order_id
GROUP BY c.id, c.name
HAVING total_spent > 50000
ORDER BY c.name""",
        "description": "HAVING references SELECT alias total_spent which is not valid in standard SQL — must repeat the expression",
    },
]


def create_db():
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        conn.execute("DROP TABLE IF EXISTS order_items")
        conn.execute("DROP TABLE IF EXISTS orders")
        conn.execute("DROP TABLE IF EXISTS products")
        conn.execute("DROP TABLE IF EXISTS customers")

        conn.execute(
            """
            CREATE TABLE customers (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name  TEXT    NOT NULL,
                email TEXT    NOT NULL UNIQUE,
                city  TEXT    NOT NULL
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE products (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name  TEXT    NOT NULL,
                price REAL    NOT NULL CHECK(price > 0)
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE orders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER REFERENCES customers(id),
                order_date  TEXT    NOT NULL DEFAULT (date('now')),
                status      TEXT    NOT NULL DEFAULT 'pending'
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE order_items (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id   INTEGER NOT NULL REFERENCES orders(id),
                product_id INTEGER NOT NULL REFERENCES products(id),
                quantity   INTEGER NOT NULL CHECK(quantity > 0),
                amount     REAL    NOT NULL CHECK(amount > 0)
            )
        """
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id)"
        )

        conn.executemany(
            "INSERT INTO customers(name, email, city) VALUES (?,?,?)",
            [
                ("Alice", "alice@email.com", "Mumbai"),
                ("Bob", "bob@email.com", "Delhi"),
                ("Carol", "carol@email.com", "Bangalore"),
                ("Dave", "dave@email.com", "Chennai"),
                ("Eve", "eve@email.com", "Hyderabad"),
            ],
        )
        conn.executemany(
            "INSERT INTO products(name, price) VALUES (?,?)",
            [
                ("Laptop", 75000.0),
                ("Phone", 25000.0),
                ("Tablet", 35000.0),
                ("Watch", 15000.0),
            ],
        )
        conn.executemany(
            "INSERT INTO orders(customer_id, order_date, status) VALUES (?,?,?)",
            [
                (1, "2024-01-10", "completed"),
                (1, "2024-02-15", "completed"),
                (2, "2024-01-20", "completed"),
                (2, "2024-03-05", "pending"),
                (1, "2024-03-10", "pending"),
            ],
        )
        conn.executemany(
            "INSERT INTO order_items(order_id, product_id, quantity, amount) VALUES (?,?,?,?)",
            [
                (1, 1, 1, 75000.0),
                (1, 4, 1, 15000.0),
                (2, 2, 2, 50000.0),
                (3, 3, 1, 35000.0),
                (4, 1, 1, 75000.0),
                (5, 2, 1, 25000.0),
            ],
        )
        conn.commit()
        conn.close()
        logger.info("ecommerce.db created ok")
    except Exception as e:
        logger.error(f"create_db failed: {e}")
        raise


# Canonical correct query (used for all scenarios)
_CORRECT_SQL = """
    SELECT
        c.name              AS customer_name,
        COUNT(o.id)         AS total_orders,
        COALESCE(SUM(oi.amount), 0) AS total_spent
    FROM customers c
    LEFT JOIN orders o
        ON c.id = o.customer_id
    LEFT JOIN order_items oi
        ON o.id = oi.order_id
    GROUP BY c.id, c.name
    ORDER BY c.name
"""

# Scenarios that need a different expected output
_CUSTOM_EXPECTED = {
    "having_wrong_alias": """
        SELECT
            c.name              AS customer_name,
            COUNT(o.id)         AS total_orders,
            COALESCE(SUM(oi.amount), 0) AS total_spent
        FROM customers c
        LEFT JOIN orders o ON c.id = o.customer_id
        LEFT JOIN order_items oi ON o.id = oi.order_id
        GROUP BY c.id, c.name
        HAVING COALESCE(SUM(oi.amount), 0) > 50000
        ORDER BY c.name
    """,
}


def get_task(scenario_name: str = None) -> TaskInfo:
    create_db()

    if scenario_name:
        scenario = next(
            (s for s in MEDIUM_SCENARIOS if s["name"] == scenario_name),
            MEDIUM_SCENARIOS[0],
        )
    else:
        scenario = random.choice(MEDIUM_SCENARIOS)

    conn = sqlite3.connect(DB_PATH)
    sql = _CUSTOM_EXPECTED.get(scenario["name"], _CORRECT_SQL)
    cursor = conn.execute(sql)
    cols = [c[0] for c in cursor.description]
    expected = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()

    return TaskInfo(
        task_id="medium",
        broken_query=scenario["broken"],
        schema_sql="""CREATE TABLE customers (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT    NOT NULL,
    email TEXT    NOT NULL UNIQUE,
    city  TEXT    NOT NULL
);
CREATE TABLE products (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT    NOT NULL,
    price REAL    NOT NULL CHECK(price > 0)
);
CREATE TABLE orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER REFERENCES customers(id),
    order_date  TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'pending'
);
CREATE TABLE order_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity   INTEGER NOT NULL CHECK(quantity > 0),
    amount     REAL    NOT NULL CHECK(amount > 0)
);""",
        expected_output=expected,
        db_path=DB_PATH,
    )
