"""
environment.py — SQL Debug Environment
OpenEnv Hackathon by Meta × Hugging Face × Scaler School of Technology

Core RL environment for training AI agents to debug SQL queries.
Subclasses the OpenEnv framework's Environment base class for full
compatibility with the OpenEnv ecosystem (WebSocket, MCP, validation).
"""

import sqlite3
import os
import sys
import time
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openenv.core.env_server import Environment as OpenEnvEnvironment
from openenv.core.env_server.types import EnvironmentMetadata
from models import SQLAction, SQLObservation, SQLState, Reward, TaskInfo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directory for trajectory logs
TRAJECTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "trajectories")
os.makedirs(TRAJECTORY_DIR, exist_ok=True)

# Global metrics (shared across sessions for telemetry)
_metrics = {
    "total_sessions": 0,
    "total_steps": 0,
    "total_episodes": 0,
    "successful_episodes": 0,
    "steps_per_episode": [],
    "scores": [],
}


def get_metrics() -> Dict[str, Any]:
    """Return a snapshot of global environment metrics for the /metrics endpoint."""
    avg_steps = (
        sum(_metrics["steps_per_episode"]) / len(_metrics["steps_per_episode"])
        if _metrics["steps_per_episode"]
        else 0.0
    )
    avg_score = (
        sum(_metrics["scores"]) / len(_metrics["scores"])
        if _metrics["scores"]
        else 0.0
    )
    return {
        "total_sessions": _metrics["total_sessions"],
        "total_steps": _metrics["total_steps"],
        "total_episodes": _metrics["total_episodes"],
        "successful_episodes": _metrics["successful_episodes"],
        "success_rate": round(
            _metrics["successful_episodes"] / max(1, _metrics["total_episodes"]), 4
        ),
        "avg_steps_per_episode": round(avg_steps, 2),
        "avg_score": round(avg_score, 4),
    }


class SQLDebugEnv(OpenEnvEnvironment[SQLAction, SQLObservation, SQLState]):
    """Reinforcement learning environment for SQL debugging tasks.

    An agent receives a broken SQL query and a database schema. It must
    iteratively fix the query by submitting SQL commands and observing
    the results. Rewards are based on correctness, efficiency, and
    query performance.

    Supports concurrent sessions via the OpenEnv session management.

    Attributes:
        SUPPORTS_CONCURRENT_SESSIONS: True — each instance is isolated.
        current_task: The active task definition (broken query + expected output).
        step_count: Number of steps taken in the current episode.
        max_steps: Maximum steps allowed per episode.
        cumulative_reward: Total reward accumulated this episode.
        history: List of step records for grading and trajectory replay.
    """

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        """Initialize a new SQL debug environment session."""
        super().__init__()
        self.current_task: Optional[TaskInfo] = None
        self.step_count: int = 0
        self.max_steps: int = 10
        self.cumulative_reward: float = 0.0
        self.history: List[Dict[str, Any]] = []
        self._episode_id: Optional[str] = None
        _metrics["total_sessions"] += 1

    def get_metadata(self) -> EnvironmentMetadata:
        """Return metadata about this environment for discovery and documentation."""
        return EnvironmentMetadata(
            name="SQL Debug Environment",
            description=(
                "An OpenEnv-compatible RL environment for training AI agents to "
                "debug and fix broken SQL queries across multiple difficulty levels."
            ),
            version="1.0.0",
            author="Aarush, Chetanya & Aryan",
        )

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        task_id: str = "easy",
        scenario: Optional[str] = None,
        **kwargs: Any,
    ) -> SQLObservation:
        """Reset the environment and load a new task.

        Args:
            seed: Optional random seed for reproducibility.
            episode_id: Optional custom episode identifier.
            task_id: Difficulty level — 'easy', 'medium', or 'hard'.
            scenario: Optional specific scenario name within the task.

        Returns:
            Initial observation containing the broken query and schema.
        """
        logger.info(f"Resetting environment for task: {task_id}")

        self._episode_id = episode_id or str(uuid.uuid4())
        task = self._load_task(task_id, scenario)
        self.current_task = task
        self.step_count = 0
        self.cumulative_reward = 0.0
        self.history = []

        _metrics["total_episodes"] += 1

        return SQLObservation(
            task_id=task.task_id,
            broken_query=task.broken_query,
            db_schema=task.schema_sql,
            query_result=None,
            error_message=None,
            hint=None,
            step_count=0,
            done=False,
            reward=0.0,
        )

    def step(
        self,
        action: SQLAction,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> SQLObservation:
        """Execute an agent action and return the resulting observation.

        The agent submits a SQL query. The environment executes it against
        the task's database and computes a reward based on correctness.

        Args:
            action: The SQL action to execute.
            timeout_s: Optional timeout for query execution.

        Returns:
            Observation with query results, reward, and done flag.

        Raises:
            ValueError: If reset() has not been called first.
        """
        if not self.current_task:
            raise ValueError("Call reset() before step()")

        self.step_count += 1
        _metrics["total_steps"] += 1
        task = self.current_task

        logger.info(
            f"Step {self.step_count} | type={action.type} | sql={str(action.sql)[:80]}"
        )

        # Execute the query
        result, error, exec_time = self._execute_query(action.sql, task.db_path)

        # Generate hint using EXPLAIN QUERY PLAN if there was an error
        hint = None
        if error and action.sql and action.sql.strip():
            hint = self._generate_hint(error, action.sql, task)

        # Compute correctness and reward
        correctness = self._get_correctness(result, task.expected_output)

        # Track algorithmic efficiency using Query Cost Estimator
        cost_modifier = 0.0
        if not error and action.sql and action.sql.strip():
            cost_modifier = self._get_query_plan_cost(action.sql, task.db_path)

        step_reward = self._calculate_reward(result, error, correctness, cost_modifier)
        self.cumulative_reward = round(self.cumulative_reward + step_reward, 4)

        done = (self.step_count >= self.max_steps) or (correctness >= 1.0)

        reward_detail = Reward(
            step_reward=round(step_reward, 4),
            cumulative_reward=self.cumulative_reward,
            correctness=round(correctness, 4),
            performance=round(exec_time, 4),
        )

        # Record step in history (for grading + trajectory replay)
        self.history.append({
            "step": self.step_count,
            "action": action.model_dump(),
            "reward": reward_detail.model_dump(),
            "done": done,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Track success in global metrics
        if done and correctness >= 1.0:
            _metrics["successful_episodes"] += 1

        if done:
            _metrics["steps_per_episode"].append(self.step_count)
            _metrics["scores"].append(correctness)
            self._save_trajectory()

        logger.info(
            f"Step {self.step_count} result | correctness={correctness:.3f} | "
            f"reward={step_reward:.4f} | done={done}"
        )

        return SQLObservation(
            task_id=task.task_id,
            broken_query=task.broken_query,
            db_schema=task.schema_sql,
            query_result=result,
            error_message=error,
            hint=hint,
            step_count=self.step_count,
            done=done,
            reward=round(step_reward, 4),
            metadata={
                "correctness": round(correctness, 4),
                "cumulative_reward": self.cumulative_reward,
                "performance_ms": round(exec_time, 4),
                "episode_id": self._episode_id,
            },
        )

    @property
    def state(self) -> SQLState:
        """Return the current episode state for observability."""
        return SQLState(
            episode_id=self._episode_id,
            step_count=self.step_count,
            task_id=self.current_task.task_id if self.current_task else None,
            max_steps=self.max_steps,
            cumulative_reward=self.cumulative_reward,
            history_length=len(self.history),
        )

    # =========================================================================
    # Query Execution
    # =========================================================================

    def _execute_query(
        self, sql: Optional[str], db_path: str
    ) -> Tuple[Optional[List[Dict]], Optional[str], float]:
        """Execute a SQL query safely against the task database.

        Opens the database in read-only mode to prevent mutations.

        Args:
            sql: The SQL query string to execute.
            db_path: Path to the SQLite database file.

        Returns:
            Tuple of (result_rows, error_message, execution_time_ms).
        """
        start = time.perf_counter()

        if not sql or not sql.strip():
            return None, "Empty query submitted", 0.0

        blocked, reason = self._safety_filter(sql)
        if blocked:
            logger.warning(f"Blocked query: {reason}")
            return None, f"Blocked: {reason}", 0.0

        if not os.path.exists(db_path):
            return None, f"Database not found: {db_path}", 0.0

        try:
            db_uri = f"file:{db_path}?mode=ro"
            with sqlite3.connect(db_uri, uri=True, timeout=5) as conn:
                cursor = conn.cursor()
                cursor.execute(sql)

                if cursor.description is None:
                    exec_time = (time.perf_counter() - start) * 1000
                    return [], None, exec_time

                cols = [c[0] for c in cursor.description]
                rows = cursor.fetchmany(200)
                result = [dict(zip(cols, row)) for row in rows]
                exec_time = (time.perf_counter() - start) * 1000

                logger.info(f"Query returned {len(result)} rows in {exec_time:.2f}ms")
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

    def _get_query_plan_cost(self, sql: str, db_path: str) -> float:
        """Analyze the query plan to determine algorithmic cost modifiers.
        
        Penalizes full table scans (O(N)) and rewards optimal index searches (O(log N)).
        """
        if not sql or not os.path.exists(db_path):
            return 0.0
            
        blocked, _ = self._safety_filter(sql)
        if blocked:
            return 0.0
            
        try:
            db_uri = f"file:{db_path}?mode=ro"
            with sqlite3.connect(db_uri, uri=True, timeout=2) as conn:
                cursor = conn.cursor()
                cursor.execute(f"EXPLAIN QUERY PLAN {sql}")
                plan_rows = cursor.fetchall()
                
                cost_modifier = 0.0
                scan_detected = False
                search_detected = False
                
                for row in plan_rows:
                    if len(row) >= 4:
                        detail = str(row[3]).upper()
                        # Detect Full Table Scans (avoid targeting covering index loops)
                        if "SCAN" in detail and "COVERING INDEX" not in detail:
                            scan_detected = True
                        # Detect Optimized Lookups
                        if "SEARCH" in detail and ("USING INDEX" in detail or "COVERING INDEX" in detail):
                            search_detected = True
                
                if scan_detected:
                    cost_modifier -= 0.1
                elif search_detected:
                    cost_modifier += 0.1
                    
                return cost_modifier
        except Exception as e:
            logger.debug(f"Failed to generate query plan cost: {e}")
            return 0.0

    def _safety_filter(self, sql: str) -> Tuple[bool, str]:
        """Check if a SQL query is safe to execute (read-only).

        Blocks DDL and DML statements. Only SELECT, WITH, and EXPLAIN
        are allowed. SQL comments are permitted since agents may include them.

        Args:
            sql: The raw SQL query string.

        Returns:
            Tuple of (is_blocked, reason).
        """
        sql_clean = sql.strip().upper()

        # Block dangerous starting keywords
        dangerous_starts = [
            "DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT",
            "ALTER", "CREATE", "REPLACE", "ATTACH",
        ]
        for word in dangerous_starts:
            if sql_clean.startswith(word):
                return True, f"{word} not allowed"

        # Block dangerous patterns anywhere
        dangerous_patterns = [
            "DROP TABLE", "DROP DATABASE", "DELETE FROM", "TRUNCATE TABLE",
        ]
        for pattern in dangerous_patterns:
            if pattern in sql_clean:
                return True, f"Pattern '{pattern}' not allowed"

        # Only allow SELECT, WITH, EXPLAIN
        allowed_starts = ["SELECT", "WITH", "EXPLAIN"]
        if not any(sql_clean.startswith(w) for w in allowed_starts):
            return True, "Only SELECT queries are allowed"

        return False, ""

    # =========================================================================
    # Correctness & Reward Computation
    # =========================================================================

    def _get_correctness(
        self, result: Optional[List[Dict]], expected: List[Dict]
    ) -> float:
        """Compute correctness score by comparing result to expected output.

        Returns 1.0 for exact match, partial credit for partial matches,
        and 0.0 for errors or empty results.

        Args:
            result: The actual query result rows.
            expected: The expected correct result rows.

        Returns:
            Correctness score in [0.0, 1.0].
        """
        if result is None:
            return 0.0
        if not expected:
            return 1.0 if not result else 0.0
        if not result:
            return 0.0

        result_normalized = [
            tuple(sorted((k, str(v)) for k, v in row.items())) for row in result
        ]
        expected_normalized = [
            tuple(sorted((k, str(v)) for k, v in row.items())) for row in expected
        ]

        # Full credit — exact order match
        if result_normalized == expected_normalized:
            return 1.0

        # Partial credit — right rows wrong order (max 0.7)
        matches = sum(1 for row in result_normalized if row in expected_normalized)
        return round(min(0.7, (matches / len(expected_normalized)) * 0.7), 4)

    def _calculate_reward(
        self, result: Optional[List[Dict]], error: Optional[str], correctness: float, cost_modifier: float = 0.0
    ) -> float:
        """Calculate step reward based on execution result, correctness, and query cost.

        Reward signals:
        - Error penalty: -0.05 for SQL errors
        - Valid result: +0.05 for any non-error result
        - Correctness bonuses: +0.20 (≥50%), +0.40 (≥90%), +0.20 (=100%)
        - Efficiency penalty: -0.05 per step after step 5
        - Algorithmic Query Cost: Penalyze full table SCANS (-0.1), Reward Index SEARCH (+0.1)

        Args:
            result: Query result rows (None if error).
            error: Error message (None if success).
            correctness: Correctness score from _get_correctness.
            cost_modifier: Efficiency modifier from _get_query_plan_cost.

        Returns:
            Reward value for this step capped strictly at 1.0 mechanism.
        """
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

        # Apply algorithmic efficiency hooks while maintaining strict upper bound of 1.0
        reward += cost_modifier
        reward = max(-1.0, min(1.0, reward))

        return round(reward, 4)

    # =========================================================================
    # Agentic Feedback — Hints via EXPLAIN QUERY PLAN
    # =========================================================================

    def _generate_hint(
        self, error: str, sql: str, task: TaskInfo
    ) -> Optional[str]:
        """Generate an intelligent hint when the agent makes an error.

        Uses EXPLAIN QUERY PLAN on the correct query to show the agent
        what a proper execution plan looks like, providing richer feedback
        than a raw error message alone.

        Args:
            error: The error message from failed query execution.
            sql: The agent's failed SQL query.
            task: The current task definition.

        Returns:
            Hint string or None if hint generation fails.
        """
        try:
            if not os.path.exists(task.db_path):
                return None

            hints = []

            # Provide specific guidance based on error type
            if "no such column" in error.lower():
                hints.append("Check column names against the schema. Use exact names.")
            elif "no such table" in error.lower():
                hints.append("Check table names against the schema.")
            elif "syntax error" in error.lower() or "near" in error.lower():
                hints.append("Check SQL syntax: keywords, commas, parentheses.")
            elif "ambiguous" in error.lower():
                hints.append("Use table aliases to disambiguate column references.")

            # Show EXPLAIN QUERY PLAN for the broken query's correct version
            db_uri = f"file:{task.db_path}?mode=ro"
            with sqlite3.connect(db_uri, uri=True, timeout=2) as conn:
                # Get table names for reference
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = [row[0] for row in cursor.fetchall()]
                hints.append(f"Available tables: {', '.join(tables)}")

            return " | ".join(hints) if hints else None

        except Exception:
            return None

    # =========================================================================
    # Task Loading
    # =========================================================================

    def _load_task(self, task_id: str, scenario: Optional[str] = None) -> TaskInfo:
        """Load a task definition by difficulty level.

        Args:
            task_id: One of 'easy', 'medium', 'hard', or 'security'.
            scenario: Optional specific scenario name.

        Returns:
            TaskInfo with the broken query, expected output, and db path.

        Raises:
            ValueError: If task_id is not recognized.
        """
        valid = ["easy", "medium", "hard", "security"]
        if task_id not in valid:
            raise ValueError(f"Unknown task '{task_id}'. Valid: {valid}")

        if task_id == "easy":
            from tasks.task_easy import get_task
        elif task_id == "medium":
            from tasks.task_medium import get_task
        elif task_id == "hard":
            from tasks.task_hard import get_task
        elif task_id == "security":
            from tasks.task_security import get_task
        else:
            raise ValueError(f"Unhandled task_id: {task_id}")

        return get_task(scenario)

    # =========================================================================
    # Trajectory Persistence
    # =========================================================================

    def _save_trajectory(self) -> None:
        """Save the episode trajectory as a JSON file for replay and analysis.

        Each trajectory file contains the complete history of actions,
        observations, and rewards for debugging and evaluating agents.
        """
        try:
            trajectory = {
                "episode_id": self._episode_id,
                "task_id": self.current_task.task_id if self.current_task else None,
                "total_steps": self.step_count,
                "cumulative_reward": self.cumulative_reward,
                "history": self.history,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            filename = f"trajectory_{self._episode_id}.json"
            filepath = os.path.join(TRAJECTORY_DIR, filename)
            with open(filepath, "w") as f:
                json.dump(trajectory, f, indent=2, default=str)
            logger.info(f"Trajectory saved: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to save trajectory: {e}")

    def close(self) -> None:
        """Clean up environment resources."""
        self.current_task = None
        self.history = []
