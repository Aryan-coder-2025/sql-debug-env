import sqlite3
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import TaskInfo

logger = logging.getLogger(__name__)

DB_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "databases", "employees.db"
))


def create_db():
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("DROP TABLE IF EXISTS employees")
        conn.execute("""
            CREATE TABLE employees (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                salary     REAL    NOT NULL CHECK(salary > 0),
                department TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_dept
            ON employees(department)
        """)
        conn.executemany(
            "INSERT INTO employees(name, salary, department) VALUES (?,?,?)",
            [
                ("Alice", 90000.0, "Engineering"),
                ("Bob",   85000.0, "Engineering"),
                ("Carol", 95000.0, "Engineering"),
                ("Dave",  70000.0, "Marketing"),
                ("Eve",   75000.0, "Marketing"),
                ("Frank", 88000.0, "Engineering"),
                ("Grace", 92000.0, "Engineering"),
            ]
        )
        conn.commit()
        conn.close()
        logger.info("employees.db created ok")
    except Exception as e:
        logger.error(f"create_db failed: {e}")
        raise


def get_task() -> TaskInfo:
    create_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT name, salary FROM employees "
        "WHERE department = 'Engineering' "
        "ORDER BY name"
    )
    cols = [c[0] for c in cursor.description]
    expected = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()

    return TaskInfo(
        task_id="easy",
        broken_query=(
            "SELECT name, salary FORM employees "
            "WHERE department = 'Engineering' ORDER BY name"
        ),
        schema_sql="""
CREATE TABLE employees (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    salary     REAL    NOT NULL CHECK(salary > 0),
    department TEXT    NOT NULL
);""".strip(),
        expected_output=expected,
        db_path=DB_PATH
    )