"""
task_security.py — Security-focused SQL debugging task.
OpenEnv Hackathon by Meta × Hugging Face × Scaler School of Technology

Presents the agent with SQL queries that contain security vulnerabilities
(SQL injection patterns, unsafe concatenation, info leaks) and asks the
agent to identify and fix them to produce safe, correct output.
"""

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

SECURITY_SCENARIOS = [
    {
        "name": "union_injection",
        "broken": (
            "SELECT name, salary FROM employees WHERE department = 'Engineering' "
            "UNION SELECT name, salary FROM employees WHERE department = 'Marketing' "
            "ORDER BY name"
        ),
        "description": (
            "UNION-based injection: query accidentally leaks Marketing data. "
            "Fix: remove the UNION clause to return only Engineering employees."
        ),
    },
    {
        "name": "wildcard_data_leak",
        "broken": (
            "SELECT * FROM employees WHERE department = 'Engineering' "
            "ORDER BY name"
        ),
        "description": (
            "SELECT * exposes all columns including sensitive id. "
            "Fix: specify only name and salary columns."
        ),
    },
    {
        "name": "tautology_where_clause",
        "broken": (
            "SELECT name, salary FROM employees WHERE department = 'Engineering' "
            "OR 1=1 ORDER BY name"
        ),
        "description": (
            "OR 1=1 tautology bypasses the WHERE filter and returns all rows. "
            "Fix: remove the OR 1=1 to restrict to Engineering department."
        ),
    },
    {
        "name": "comment_injection",
        "broken": (
            "SELECT name, salary FROM employees WHERE department = 'Engineering' "
            "OR department = 'Marketing' ORDER BY name"
        ),
        "description": (
            "Extra OR condition leaks data from the Marketing department. "
            "Fix: remove the OR clause to return only Engineering employees."
        ),
    },
    {
        "name": "subquery_escalation",
        "broken": (
            "SELECT name, salary FROM employees WHERE salary > "
            "(SELECT MIN(salary) FROM employees) AND department = 'Engineering' "
            "ORDER BY name"
        ),
        "description": (
            "Subquery uses MIN(salary) from ALL departments as threshold, "
            "not just Engineering. Fix: add WHERE department = 'Engineering' "
            "inside the subquery so it only compares within department."
        ),
    },
]


def _ensure_db():
    """Ensure the employees database exists (do NOT recreate if present)."""
    if os.path.exists(DB_PATH):
        return
    # If task_easy hasn't been run yet, create a minimal DB
    from tasks.task_easy import create_db
    create_db()


def get_task(scenario_name: str = None) -> TaskInfo:
    """Load a security-focused SQL debugging task.

    Args:
        scenario_name: Optional specific scenario. Random if not provided.

    Returns:
        TaskInfo with the insecure query and expected secure output.
    """
    _ensure_db()

    if scenario_name:
        scenario = next(
            (s for s in SECURITY_SCENARIOS if s["name"] == scenario_name),
            SECURITY_SCENARIOS[0],
        )
    else:
        scenario = random.choice(SECURITY_SCENARIOS)

    # All security scenarios should produce the same correct output:
    # Engineering employees with only name and salary columns
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT name, salary FROM employees WHERE department = 'Engineering' ORDER BY name"
    )
    cols = [c[0] for c in cursor.description]
    expected = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()

    # Handle special case for subquery_escalation
    if scenario["name"] == "subquery_escalation":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute(
            "SELECT name, salary FROM employees WHERE salary > "
            "(SELECT MIN(salary) FROM employees WHERE department = 'Engineering') "
            "AND department = 'Engineering' ORDER BY name"
        )
        cols = [c[0] for c in cursor.description]
        expected = [dict(zip(cols, row)) for row in cursor.fetchall()]
        conn.close()

    return TaskInfo(
        task_id="security",
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
