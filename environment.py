import sqlite3
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from typing import Tuple, Optional, List, Dict, Any
from models import Action, Observation, Reward, TaskInfo


class SQLDebugEnv:

    def __init__(self):
        self.current_task: Optional[TaskInfo] = None
        self.step_count = 0
        self.max_steps = 10
        self.cumulative_reward = 0.0
        self.history: List[Dict[str, Any]] = []

    def reset(self, task_id: str = "easy") -> Observation:
        task = self._load_task(task_id)
        self.current_task = task
        self.step_count = 0
        self.cumulative_reward = 0.0
        self.history = []

        return Observation(
            task_id=task.task_id,
            broken_query=task.broken_query,
            db_schema=task.schema_sql,
            query_result=None,
            error_message=None,
            step_count=0,
            done=False,
        )

    def step(self, action: Action):
        if not self.current_task:
            raise ValueError("Environment not initialized. Call reset() first.")

        self.step_count += 1
        task = self.current_task

        result, error, exec_time = self._run_query(action.sql, task.db_path)

        correctness = self._get_correctness(result, task.expected_output)
        step_reward = self._calculate_reward(result, error, correctness)
        self.cumulative_reward += step_reward

        done = (self.step_count >= self.max_steps) or (correctness >= 1.0)

        reward = Reward(
            step_reward=round(step_reward, 4),
            cumulative_reward=round(self.cumulative_reward, 4),
            correctness=round(correctness, 4),
            performance=round(exec_time, 4),
        )

        obs = Observation(
            task_id=task.task_id,
            broken_query=task.broken_query,
            db_schema=task.schema_sql,
            query_result=result,
            error_message=error,
            step_count=self.step_count,
            done=done,
        )

        self.history.append(
            {
                "action": action.model_dump(),
                "reward": reward.model_dump(),
                "done": done,
            }
        )

        return obs, reward, done, {}

    def state(self):
        return {
            "task_id": self.current_task.task_id if self.current_task else None,
            "step_count": self.step_count,
            "cumulative_reward": round(self.cumulative_reward, 4),
            "done": self.step_count >= self.max_steps,
        }

    def _run_query(
        self, sql: Optional[str], db_path: str
    ) -> Tuple[Optional[List[Dict]], Optional[str], float]:
        start = time.perf_counter()

        if not sql:
            return None, "Empty query", 0.0

        forbidden = ["DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER"]
        sql_upper = sql.upper()

        if any(word in sql_upper for word in forbidden):
            return None, "Dangerous query blocked", 0.0

        try:
            db_uri = f"file:{db_path}?mode=ro"

            with sqlite3.connect(db_uri, uri=True, timeout=2) as conn:
                cursor = conn.cursor()
                cursor.execute(sql)

                if cursor.description is None:
                    return [], None, (time.perf_counter() - start) * 1000

                cols = [c[0] for c in cursor.description]
                rows = cursor.fetchmany(100)

                result = [dict(zip(cols, row)) for row in rows]

                return result, None, (time.perf_counter() - start) * 1000

        except sqlite3.Error as e:
            return None, f"SQL Error: {e}", (time.perf_counter() - start) * 1000
        except Exception as e:
            return None, f"System Error: {e}", (time.perf_counter() - start) * 1000

    def _get_sample_rows(self, db_path: str) -> List[Dict[str, Any]]:
        try:
            db_uri = f"file:{db_path}?mode=ro"

            with sqlite3.connect(db_uri, uri=True) as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = [row[0] for row in cursor.fetchall()]

                samples = []
                for table in tables:
                    cur2 = conn.execute(f"SELECT * FROM {table} LIMIT 3")
                    cols = [c[0] for c in cur2.description]
                    for row in cur2.fetchall():
                        samples.append(dict(zip(cols, row)))

                return samples

        except Exception:
            return []

    def _get_correctness(self, result, expected):
        if result is None:
            return 0.0

        if not expected:
            return 1.0 if not result else 0.0

        result_set = [tuple(sorted(r.items())) for r in result]
        expected_set = [tuple(sorted(r.items())) for r in expected]

        matches = sum(1 for r in result_set if r in expected_set)

        return min(1.0, matches / len(expected_set))

    def _calculate_reward(self, result, error, correctness):
        if error:
            return -0.05

        reward = 0.0

        if result is not None:
            reward += 0.05

        if correctness >= 0.5:
            reward += 0.2

        if correctness >= 0.9:
            reward += 0.4

        if correctness >= 1.0:
            reward += 0.2

        if self.step_count > 5:
            reward -= 0.05

        return round(reward, 4)

    def _load_task(self, task_id: str) -> TaskInfo:
        if task_id == "easy":
            from tasks.task_easy import get_task
        elif task_id == "medium":
            from tasks.task_medium import get_task
        elif task_id == "hard":
            from tasks.task_hard import get_task
        else:
            raise ValueError(f"Unknown task_id: {task_id}")

        return get_task()
