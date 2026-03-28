from models import TaskInfo


def get_task() -> TaskInfo:
    return TaskInfo(
        task_id="medium",
        broken_query="SELECT u.name, COUNT(o.id) as order_count FROM users u LEFT JOIN orders o ON u.id = o.user_id GROUP BY u.id",
        schema_sql="""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            amount REAL
        );
        """,
        expected_output=[
            {"name": "Alice", "order_count": 2},
            {"name": "Bob", "order_count": 1},
        ],
        db_path="tasks/medium.db",
    )
