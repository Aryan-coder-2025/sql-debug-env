"""
test_environment.py — Automated Test Suite for SQL Debug Environment

Tests cover:
- Environment reset and observation structure
- Step execution and reward calculation
- Safety filter (blocks destructive SQL)
- Correctness scoring (exact match, partial match, no match)
- Multi-difficulty task loading
- Grader scoring logic
- Session isolation
- Dynamic schema generation
"""

import sys
import os
import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from environment import SQLDebugEnv
from models import SQLAction, SQLObservation, TaskInfo, Reward
from grader import grade_episode
from dynamic_schema import DynamicSQLEnv, generate_random_schema


# =============================================================================
# Environment Reset Tests
# =============================================================================


class TestEnvironmentReset:
    """Tests for environment initialization and reset behavior."""

    def test_reset_returns_observation(self):
        env = SQLDebugEnv()
        obs = env.reset(task_id="easy")
        assert isinstance(obs, SQLObservation)
        assert obs.task_id == "easy"
        assert obs.broken_query != ""
        assert obs.db_schema != ""

    def test_reset_sets_step_count_zero(self):
        env = SQLDebugEnv()
        env.reset(task_id="easy")
        assert env.step_count == 0
        assert env.cumulative_reward == 0.0

    def test_reset_clears_history(self):
        env = SQLDebugEnv()
        env.reset(task_id="easy")
        env.step(SQLAction(type="run_sql", sql="SELECT 1"))
        assert len(env.history) == 1
        env.reset(task_id="easy")
        assert len(env.history) == 0

    @pytest.mark.parametrize("task_id", ["easy", "medium", "hard", "security"])
    def test_reset_all_difficulties(self, task_id):
        env = SQLDebugEnv()
        obs = env.reset(task_id=task_id)
        assert obs.task_id == task_id

    def test_reset_invalid_task_raises(self):
        env = SQLDebugEnv()
        with pytest.raises(ValueError):
            env.reset(task_id="impossible")


# =============================================================================
# Step Execution Tests
# =============================================================================


class TestStepExecution:
    """Tests for the environment step logic."""

    def test_step_requires_reset(self):
        env = SQLDebugEnv()
        with pytest.raises(ValueError, match="reset"):
            env.step(SQLAction(type="run_sql", sql="SELECT 1"))

    def test_step_increments_counter(self):
        env = SQLDebugEnv()
        env.reset(task_id="easy")
        env.step(SQLAction(type="run_sql", sql="SELECT 1"))
        assert env.step_count == 1

    def test_step_returns_observation(self):
        env = SQLDebugEnv()
        env.reset(task_id="easy")
        obs = env.step(SQLAction(type="run_sql", sql="SELECT 1"))
        assert isinstance(obs, SQLObservation)

    def test_correct_fix_gives_full_correctness(self):
        env = SQLDebugEnv()
        env.reset(task_id="easy", scenario="typo_from")
        obs = env.step(SQLAction(
            type="run_sql",
            sql="SELECT name, salary FROM employees WHERE department = 'Engineering' ORDER BY name"
        ))
        assert obs.metadata["correctness"] == 1.0

    def test_wrong_query_gives_low_correctness(self):
        env = SQLDebugEnv()
        env.reset(task_id="easy")
        obs = env.step(SQLAction(type="run_sql", sql="SELECT 1 AS dummy"))
        assert obs.metadata["correctness"] < 1.0

    def test_empty_sql_returns_error(self):
        env = SQLDebugEnv()
        env.reset(task_id="easy")
        obs = env.step(SQLAction(type="run_sql", sql=""))
        assert obs.error_message is not None

    def test_episode_done_on_max_steps(self):
        env = SQLDebugEnv()
        env.reset(task_id="easy")
        for _ in range(10):
            obs = env.step(SQLAction(type="run_sql", sql="SELECT 1"))
        assert obs.done is True


# =============================================================================
# Safety Filter Tests
# =============================================================================


class TestSafetyFilter:
    """Tests for the SQL safety filter — must block destructive operations."""

    @pytest.mark.parametrize("dangerous_sql", [
        "DROP TABLE employees",
        "DELETE FROM employees",
        "TRUNCATE TABLE employees",
        "UPDATE employees SET salary = 0",
        "INSERT INTO employees VALUES (1, 'hack', 0)",
        "ALTER TABLE employees ADD COLUMN hack TEXT",
        "CREATE TABLE evil (id INTEGER)",
        "ATTACH DATABASE ':memory:' AS hack",
    ])
    def test_blocks_destructive_sql(self, dangerous_sql):
        env = SQLDebugEnv()
        env.reset(task_id="easy")
        obs = env.step(SQLAction(type="run_sql", sql=dangerous_sql))
        assert obs.error_message is not None
        assert "Blocked" in obs.error_message or "not allowed" in obs.error_message

    def test_allows_select_queries(self):
        env = SQLDebugEnv()
        env.reset(task_id="easy")
        obs = env.step(SQLAction(type="run_sql", sql="SELECT name FROM employees"))
        assert obs.error_message is None or "Blocked" not in (obs.error_message or "")

    def test_allows_explain_queries(self):
        env = SQLDebugEnv()
        env.reset(task_id="easy")
        obs = env.step(SQLAction(
            type="run_sql",
            sql="EXPLAIN QUERY PLAN SELECT name FROM employees"
        ))
        assert obs.error_message is None or "Blocked" not in (obs.error_message or "")


# =============================================================================
# Correctness Scoring Tests
# =============================================================================


class TestCorrectnessScoring:
    """Tests for the correctness comparison logic."""

    def test_exact_match_gives_1(self):
        env = SQLDebugEnv()
        result = [{"a": 1}, {"a": 2}]
        expected = [{"a": 1}, {"a": 2}]
        assert env._get_correctness(result, expected) == 1.0

    def test_no_result_gives_0(self):
        env = SQLDebugEnv()
        assert env._get_correctness(None, [{"a": 1}]) == 0.0

    def test_empty_result_gives_0(self):
        env = SQLDebugEnv()
        assert env._get_correctness([], [{"a": 1}]) == 0.0

    def test_partial_match_gives_partial_credit(self):
        env = SQLDebugEnv()
        result = [{"a": 1}, {"a": 99}]
        expected = [{"a": 1}, {"a": 2}]
        score = env._get_correctness(result, expected)
        assert 0.0 < score < 1.0


# =============================================================================
# Grader Tests
# =============================================================================


class TestGrader:
    """Tests for the episode grading logic."""

    def test_empty_history_gives_min_score(self):
        result = grade_episode([], None)
        assert result["score"] == 0.01

    def test_perfect_episode(self):
        history = [
            {"action": {"sql": "SELECT 1"}, "reward": {"correctness": 1.0}},
        ]
        result = grade_episode(history)
        assert result["score"] > 0.9

    def test_failed_episode(self):
        history = [
            {"action": {"sql": ""}, "reward": {"correctness": 0.0}},
        ] * 10
        result = grade_episode(history)
        assert result["score"] < 0.3

    def test_score_clamped_to_range(self):
        history = [
            {"action": {"sql": "SELECT 1"}, "reward": {"correctness": 1.0}},
        ]
        result = grade_episode(history)
        assert 0.01 <= result["score"] <= 0.99


# =============================================================================
# Dynamic Schema Generation Tests
# =============================================================================


class TestDynamicSchema:
    """Tests for the Faker-powered dynamic schema generation."""

    def test_generates_database_file(self):
        db_path, schema_str, tables = generate_random_schema(num_tables=(2, 3))
        assert os.path.exists(db_path)
        assert len(tables) >= 2
        # Cleanup
        os.remove(db_path)

    def test_schema_contains_create_table(self):
        db_path, schema_str, tables = generate_random_schema(num_tables=(2, 2))
        assert "CREATE TABLE" in schema_str
        os.remove(db_path)

    def test_dynamic_env_reset(self):
        env = DynamicSQLEnv()
        obs = env.reset(task_id="easy")
        assert isinstance(obs, SQLObservation)
        assert obs.broken_query != ""
        assert obs.task_id in ["easy", "medium", "hard"]

    def test_dynamic_env_varied_difficulty(self):
        """Run multiple resets and verify we get varying difficulties."""
        env = DynamicSQLEnv()
        difficulties = set()
        for _ in range(20):
            obs = env.reset(task_id="easy")
            difficulties.add(obs.task_id)
        # With 30/40/30 weights over 20 trials, we should see at least 2 different difficulties
        assert len(difficulties) >= 2, f"Only saw difficulties: {difficulties}"


# =============================================================================
# Session Isolation Tests
# =============================================================================


class TestSessionIsolation:
    """Tests for concurrent session isolation."""

    def test_separate_envs_dont_interfere(self):
        env1 = SQLDebugEnv()
        env2 = SQLDebugEnv()

        env1.reset(task_id="easy")
        env2.reset(task_id="medium")

        assert env1.current_task.task_id == "easy"
        assert env2.current_task.task_id == "medium"

        env1.step(SQLAction(type="run_sql", sql="SELECT 1"))
        assert env1.step_count == 1
        assert env2.step_count == 0
