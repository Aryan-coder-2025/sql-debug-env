import sqlite3
import os
import logging
from models import TaskInfo

logger = logging.getLogger(_name_)

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(_file_)),
    "..", "databases", "employees.db"
)
DB_PATH = os.path.normpath(DB_PATH)


def create_db():
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        conn.execute("DROP TABLE IF EXISTS employees")
        conn.execute("""
            CREATE TABLE employees (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                salary     REAL    NOT NULL CHECK(salary > 0),
                department TEXT    NOT NULL
            )
        """)

        # Create index for faster queries
        conn.execute("""
            CREATE INDEX idx_employees_department
            ON employees(department)
        """)

        conn.executemany(
            "INSERT INTO employees(name, salary, department) VALUES (?,?,?)",
            [
                ("Alice",   90000.0, "Engineering"),
                ("Bob",     85000.0, "Engineering"),
                ("Carol",   95000.0, "Engineering"),
                ("Dave",    70000.0, "Marketing"),
                ("Eve",     75000.0, "Marketing"),
                ("Frank",   88000.0, "Engineering"),
                ("Grace",   92000.0, "Engineering"),
            ]
        )

        conn.commit()
        conn.close()
        logger.info("employees.db created successfully")

    except Exception as e:
        logger.error(f"Failed to create employees.db: {e}")
        raise


def get_task() -> TaskInfo:
    create_db()

    # Get expected output directly from DB — alw