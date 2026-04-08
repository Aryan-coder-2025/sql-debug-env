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
        os.path.dirname(os.path.abspath(__file__)), "..", "databases", "employees.db"
    )
)

EASY_SCENARIOS = [
    # ── Original scenarios ──────────────────────────────────────────────────
    {
        "name": "typo_from",
        "broken": "SELECT name, salary FORM employees WHERE department = 'Engineering' ORDER BY name",
        "description": "FORM instead of FROM typo",
    },
    {
        "name": "typo_where",
        "broken": "SELECT name, salary FROM employees WERE department = 'Engineering' ORDER BY name",
        "description": "WERE instead of WHERE typo",
    },
    {
        "name": "typo_select",
        "broken": "SELCT name, salary FROM employees WHERE department = 'Engineering' ORDER BY name",
        "description": "SELCT instead of SELECT typo",
    },
    {
        "name": "wrong_column",
        "broken": "SELECT name, wages FROM employees WHERE department = 'Engineering' ORDER BY name",
        "description": "wages instead of salary wrong column",
    },
    {
        "name": "case_sensitivity",
        "broken": "SELECT name, salary FROM employees WHERE department = 'engineering' ORDER BY name",
        "description": "lowercase engineering vs Engineering case bug",
    },
    {
        "name": "empty_result",
        "broken": "SELECT name, salary FROM employees WHERE department = 'Finance' ORDER BY name",
        "description": "Finance department does not exist returns empty",
    },
    {
        "name": "null_handling",
        "broken": "SELECT name, salary FROM employees WHERE salary = NULL ORDER BY name",
        "description": "= NULL instead of IS NULL returns nothing",
    },
    # ── NEW: Aggregation scenarios ───────────────────────────────────────────
    {
        "name": "agg_missing_group_by",
        "broken": "SELECT department, AVG(salary) AS avg_salary FROM employees ORDER BY department",
        "description": "AVG with no GROUP BY — aggregates entire table instead of per department",
    },
    {
        "name": "agg_count_star_vs_column",
        "broken": "SELECT department, COUNT(*) AS headcount FROM employees WHERE salary > 80000 GROUP BY department ORDER BY department",
        "description": "COUNT(*) counts NULLs; should be COUNT(salary) to exclude NULL salaries",
    },
    {
        "name": "agg_having_vs_where",
        "broken": "SELECT department, AVG(salary) AS avg_salary FROM employees GROUP BY department WHERE AVG(salary) > 88000 ORDER BY department",
        "description": "WHERE used after GROUP BY instead of HAVING for aggregate filter",
    },
    # ── NEW: Index / performance scenario ───────────────────────────────────
    {
        "name": "no_index_like",
        "broken": "SELECT name, salary FROM employees WHERE department LIKE '%ing' ORDER BY name",
        "description": "LIKE '%ing' matches both Engineering AND Marketing — returns wrong rows, should use = 'Engineering'",
    },
]


def create_db():
    if os.path.exists(DB_PATH):
        return
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("DROP TABLE IF EXISTS employees")
        conn.execute(
            """
            CREATE TABLE employees (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                salary     REAL,
                department TEXT    NOT NULL
            )
        """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_dept
            ON employees(department)
        """
        )
        conn.executemany(
            "INSERT INTO employees(name, salary, department) VALUES (?,?,?)",
            [
                ("Alice", 90000.0, "Engineering"),
                ("Bob", 85000.0, "Engineering"),
                ("Carol", 95000.0, "Engineering"),
                ("Dave", 70000.0, "Marketing"),
                ("Eve", 75000.0, "Marketing"),
                ("Frank", 88000.0, "Engineering"),
                ("Grace", 92000.0, "Engineering"),
                ("Hank", None, "Engineering"),
            ],
        )
        conn.commit()
        conn.close()
        logger.info("employees.db created ok")
    except Exception as e:
        logger.error(f"create_db failed: {e}")
        raise


def get_expected_output(conn, scenario_name):
    queries = {
        "case_sensitivity": (
            "SELECT name, salary FROM employees "
            "WHERE department = 'Engineering' ORDER BY name"
        ),
        "empty_result": (
            "SELECT name, salary FROM employees "
            "WHERE department = 'Engineering' ORDER BY name"
        ),
        "null_handling": (
            "SELECT name, salary FROM employees " "WHERE salary IS NULL ORDER BY name"
        ),
        # new aggregation fixes
        "agg_missing_group_by": (
            "SELECT department, AVG(salary) AS avg_salary "
            "FROM employees GROUP BY department ORDER BY department"
        ),
        "agg_count_star_vs_column": (
            "SELECT department, COUNT(salary) AS headcount "
            "FROM employees WHERE salary > 80000 "
            "GROUP BY department ORDER BY department"
        ),
        "agg_having_vs_where": (
            "SELECT department, AVG(salary) AS avg_salary "
            "FROM employees GROUP BY department "
            "HAVING AVG(salary) > 88000 ORDER BY department"
        ),
        # new index fix
        "no_index_like": (
            "SELECT name, salary FROM employees "
            "WHERE department = 'Engineering' ORDER BY name"
        ),
    }
    sql = queries.get(
        scenario_name,
        "SELECT name, salary FROM employees "
        "WHERE department = 'Engineering' ORDER BY name",
    )
    cursor = conn.execute(sql)
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def get_task(scenario_name: str = None) -> TaskInfo:
    create_db()

    if scenario_name:
        scenario = next(
            (s for s in EASY_SCENARIOS if s["name"] == scenario_name), EASY_SCENARIOS[0]
        )
    else:
        scenario = random.choice(EASY_SCENARIOS)

    conn = sqlite3.connect(DB_PATH)
    expected = get_expected_output(conn, scenario["name"])
    conn.close()

    return TaskInfo(
        task_id="easy",
        broken_query=scenario["broken"],
        schema_sql="""CREATE TABLE employees (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    salary     REAL,
    department TEXT    NOT NULL
);
CREATE INDEX idx_dept ON employees(department);""",
        expected_output=expected,
        db_path=DB_PATH,
    )
