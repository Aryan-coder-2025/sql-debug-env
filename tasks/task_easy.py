from models import TaskInfo


def get_task() -> TaskInfo:
    return TaskInfo(
        task_id="easy",
        broken_query="SELECT * FORM users WHERE id = 1",
        schema_sql="""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT
        );
        """,
        expected_output=[
            {"id": 1, "name": "Alice", "email": "alice@example.com"}
        ],
        db_path="tasks/easy.db",
    )
