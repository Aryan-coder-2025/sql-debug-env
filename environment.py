import sqlite3
import os
import sys
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import Optional, List, Dict, Any, Tuple
from models import Action, Observation, Reward, TaskInfo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SQLDebugEnv:

    def __init__(self):
        self.current_task: Optional[TaskInfo] = None
        self.step_count: int = 0
        self.max_steps: int = 10
        self.cumulative_reward: float = 0.0
        self.history: List[Dict[str, Any]] = []

    def reset(self, task_id: str = "easy") -> Observation:
        logger.info(f"Resetting environment for task: {task_id}")

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

    def step(self, action: Action) -> Tuple:
        if not self.current_task:
            raise ValueError("Call reset() before step()")

        self.step_count += 1
        task = self.current_task

        logger.info(
            f"Step {self.step_count} | "
            f"type={action.type} | "
            f"sql={str(action.sql)[:80]}"
        )

        result, error, exec_time = self._execute_query(
            action.sql, task.db_path
        )

        correctness = self._get_correctness(result, task.expected_output)
        step_reward = self._calculate_reward(result, error, correctness)
        self.cumulative_reward = round(
            self.cumulative_reward + step_reward, 4
        )

        done = (self.step_count >= self.max_steps) or (correctness >= 1.0)

        reward = Reward(
            step_reward=round(step_reward, 4),
            cumulative_reward=self.cumulative_reward,
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

        self.history.append({
            "step": self.step_count,
            "action": action.model_dump(),
            "reward": reward.model_dump(),
            "done": done,
        })

        logger.info(
            f"Step {self.step_count} result | "
            f"correctness={correctness:.3f} | "
            f"reward={step_reward:.4f} | "
            f"done={done}"
        )

        return obs, reward, done, {}

    def state(self) -> Dict[str, Any]:
        return {
            "task_id": (
                self.current_task.task_id
                if self.current_task else None
            ),
            "step_count": self.step_count,
            "max_steps": self.max_steps,
            "cumulative_reward": self.cumulative_reward,
            "done": self.step_count >= self.max_steps,
            "history_length": len(self.history),
        }

    def _execute_query(
        self,
        sql: Optional[str],
        db_path: str
    ) -> Tuple[Optional[List[Dict]], Optional[str], float]:

        start = time.perf_counter()

        # Check 1 — empty query
        if not sql or not sql.strip():
            return None, "Empty query submitted", 0.0

        # Check 2 — safety filter
        blocked, reason = self._safety_filter(sql)
        if blocked:
            logger.warning(f"Blocked query: {reason}")
            return None, f"Blocked: {reason}", 0.0

        # Check 3 — database file must exist
        if not os.path.exists(db_path):
            return None, f"Database not found: {db_path}", 0.0

        # Run the query safely
        try:
            db_uri = f"file:{db_path}?mode=ro"
            with sqlite3.connect(
                db_uri, uri=True, timeout=5
            ) as conn:
                cursor = conn.cursor()
                cursor.execute(sql)

                if cursor.description is None:
                    exec_time = (time.perf_counter() - start) * 1000
                    return [], None, exec_time

                cols = [c[0] for c in cursor.description]
                rows = cursor.fetchmany(200)
                result = [dict(zip(cols, row)) for row in rows]
                exec_time = (time.perf_counter() - start) * 1000

                logger.info(
                    f"Query returned {len(result)} rows "
                    f"in {exec_time:.2f}ms"
                )
                return result, None, exec_time

        except sqlite3.OperationalError as e:
            exec_time = (time.perf_counter() - start) * 1000
            return None, f"SQL Error: {str(e)}", exec_time

        except sqlite3.Error as e:
            exec_time = (time.perf_counter() - start) * 1000
            return None, f"Database Error: {str(e)}", exec_time

        except Exception as e:
            exec_time = (time.perf_counter() - start) * 1000
            return None, f"System Error: {str(e)}", exec_time

    def _safety_filter(self, sql: str) -> Tuple[bool, str]:
        sql_clean = sql.strip().upper()

        # Block dangerous starting keywords
        dangerous_starts = [
            "DROP", "DELETE", "TRUNCATE",
            "UPDATE", "INSERT", "ALTER",
            "CREATE", "REPLACE", "ATTACH"
        ]

        for word in dangerous_starts:
            if sql_clean.startswith(word):
                return True, f"{word} not allowed"

        # Block dangerous patterns anywhere
        dangerous_patterns = [
            "DROP TABLE", "DROP DATABASE",
            "DELETE FROM", "TRUNCATE TABLE",
            "--", "/*", "*/"
        ]

        for pattern in dangerous_patterns:
            if pattern in sql_clean:
                return True, f"Pattern '{pattern}' not allowed"

        # Only allow SELECT, WITH, EXPLAIN
        allowed_starts = ["SELECT", "WITH", "EXPLAIN"]
        if not any(sql_clean.startswith(w) for w in allowed_starts):
            return True, "Only SELECT queries are allowed"

        return False, ""

    def _get_correctness(
        self,
        result: Optional[List[Dict]],
        expected: List[Dict]
    ) -> float:

        if result is None:
            return 0.0

        if not expected:
            return 1.0 if not result else 0.0

        if not result:
            return 0.0

        result_normalized = [
            tuple(sorted((k, str(v)) for k, v in row.items()))
            for row in result
        ]
        expected_normalized = [
            tuple(sorted((k, str(v)) for k, v in row.items()))
            for row in expected
        ]

        # Full credit — exact order match
        if result_normalized == expected_normalized:
            return 1.0

        # Partial credit — right rows wrong order (max 0.7)
        matches = sum(
            1 for row in result_normalized
            if row in expected_normalized
        )
        return round(min(0.7, (matches / len(expected_normalized)) * 0.7), 4)

    def _calculate_reward(
        self,
        result: Optional[List[Dict]],
        error: Optional[str],
        correctness: float
    ) -> float:

        if error:
            return -0.05

        reward = 0.0

        if result is not None:
            reward += 0.05

        if correctness >= 0.5:
            reward += 0.20

        if correctness >= 0.9:
            reward += 0.40

        if correctness >= 1.0:
            reward += 0.20

        if self.step_count > 5:
            reward -= 0.05 * (self.step_count - 5)

        return round(reward, 4)

    def _load_task(self, task_id: str) -> TaskInfo:
        valid = ["easy", "medium", "hard"]

        if task_id not in valid:
            raise ValueError(
                f"Unknown task '{task_id}'. Valid: {valid}"
            )

        if task_id == "easy":
            from tasks.task_easy import get_task as get_task
        elif task_id == "medium":
            from tasks.task_medium import get_task as get_task
        elif task_id == "hard":
            from tasks.task_hard import get_task as get_task
        else:
            raise ValueError(f"Unhandled task_id: {task_id}")

        return get_task()