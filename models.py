import sqlite3
import time
import logging
import re
from typing import Optional, List, Dict, Any, Literal, Tuple
from pydantic import BaseModel, Field, field_validator, ConfigDict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["run_sql", "fix_query", "analyze"]
    sql: Optional[str] = Field(default=None, max_length=10000)
    reasoning: Optional[str] = Field(default=None, max_length=2000)


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    broken_query: str
    db_schema: str
    query_result: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None
    step_count: int
    done: bool


class Reward(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_reward: float
    cumulative_reward: float
    correctness: float = Field(..., ge=0.0, le=1.0)
    performance: Optional[float] = None

    @field_validator("cumulative_reward")
    def validate_reward(cls, v):
        if not (-1000 <= v <= 1000):
            raise ValueError("cumulative_reward out of bounds")
        return v


class TaskInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    broken_query: str
    schema_sql: str
    expected_output: List[Dict[str, Any]]
    db_path: str


def normalize_result(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda x: sorted(x.items()))


def is_safe_query(sql: str) -> bool:
    forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER"]
    sql_upper = sql.upper()
    return not any(word in sql_upper for word in forbidden)


def extract_schema(schema_sql: str) -> Dict[str, List[str]]:
    tables = {}
    table_defs = re.findall(
        r"CREATE TABLE (\w+)\s*\((.*?)\);", schema_sql, re.IGNORECASE | re.DOTALL
    )

    for table_name, columns_block in table_defs:
        columns = []
        for col in columns_block.split(","):
            col_name = col.strip().split()[0]
            columns.append(col_name)
        tables[table_name.upper()] = columns

    return tables


def validate_query(sql: str, schema: Dict[str, List[str]]) -> bool:
    sql_upper = sql.upper()

    table_valid = any(table in sql_upper for table in schema.keys())
    if not table_valid:
        return False

    for table, cols in schema.items():
        if table in sql_upper:
            if not any(col.upper() in sql_upper for col in cols):
                return False

    return True


class SQLEnvironment:
    def __init__(self, task: TaskInfo, max_rows: int = 100):
        self.task = task
        self.max_rows = max_rows
        self.step_count = 0
        self.cumulative_reward = 0.0
        self.schema = extract_schema(task.schema_sql)

    def _execute(self, sql: str) -> Tuple[Optional[List[Dict]], Optional[str], float]:
        start = time.perf_counter()

        if not is_safe_query(sql):
            return None, "Unsafe query detected", 0.0

        if not validate_query(sql, self.schema):
            return None, "Schema validation failed", 0.0

        try:
            db_uri = f"file:{self.task.db_path}?mode=ro"

            with sqlite3.connect(db_uri, uri=True, timeout=2) as conn:
                cursor = conn.cursor()
                cursor.execute(sql)

                if cursor.description is None:
                    return [], None, (time.perf_counter() - start) * 1000

                columns = [c[0] for c in cursor.description]
                rows = cursor.fetchmany(self.max_rows)
                result = [dict(zip(columns, r)) for r in rows]

                return result, None, (time.perf_counter() - start) * 1000

        except sqlite3.Error as e:
            return None, f"SQL Error: {e}", (time.perf_counter() - start) * 1000
        except Exception as e:
            return None, f"System Error: {e}", (time.perf_counter() - start) * 1000

    def step(self, action: Action) -> Tuple[Observation, Reward]:
        self.step_count += 1

        logger.info(f"Step {self.step_count} | Action: {action.type}")

        result, error, exec_time = None, None, 0.0

        if action.sql:
            result, error, exec_time = self._execute(action.sql)

        done = False
        correctness = 0.0
        reward = -1.0

        if error:
            reward = -10.0
        elif result is not None:
            if normalize_result(result) == normalize_result(self.task.expected_output):
                reward = 100.0
                correctness = 1.0
                done = True
            else:
                reward = 5.0
                correctness = 0.5

        self.cumulative_reward += reward

        obs = Observation(
            task_id=self.task.task_id,
            broken_query=self.task.broken_query,
            db_schema=self.task.schema_sql,
            query_result=result,
            error_message=error,
            step_count=self.step_count,
            done=done,
        )

        rew = Reward(
            step_reward=reward,
            cumulative_reward=self.cumulative_reward,
            correctness=correctness,
            performance=exec_time,
        )

        return obs, rew


if __name__ == "__main__":
    task = TaskInfo(
        task_id="task-1",
        broken_query="SELECT * FROM users",
        schema_sql="CREATE TABLE users (id INTEGER, name TEXT);",
        expected_output=[{"id": 1, "name": "Alice"}],
        db_path="test.db",
    )

    env = SQLEnvironment(task)

    action = Action(
        type="run_sql", sql="SELECT id, name FROM users WHERE id = 1 LIMIT 1;"
    )

    obs, rew = env.step(action)

    print(obs)
    print(rew)
