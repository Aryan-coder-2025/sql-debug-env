from models import TaskInfo


def get_task() -> TaskInfo:
    return TaskInfo(
        task_id="hard",
        broken_query="SELECT o.id, o.amount, u.name FROM orders o INNER JOIN users u ON o.user_id = u.id WHERE o.amount > 100 ORDER BY o.amount DESC",
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
        CREATE INDEX idx_orders_amount ON orders(amount);
        """,
        expected_output=[
            {"id": 5, "amount": 500.0, "name": "Alice"},
            {"id": 3, "amount": 250.0, "name": "Bob"},
        ],
        db_path="tasks/hard.db",
    )
