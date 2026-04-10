"""
models.py — SQL Debug Environment
OpenEnv Hackathon by Meta × Hugging Face × Scaler School of Technology

Defines the core data models for the SQL debugging RL environment.
All models follow the OpenEnv framework conventions with Pydantic validation.
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from openenv.core.env_server import (
    Action as OpenEnvAction,
    Observation as OpenEnvObservation,
    State as OpenEnvState,
)


# =============================================================================
# Action — What the agent sends to the environment
# =============================================================================


class SQLAction(OpenEnvAction):
    """An action submitted by the agent to debug a SQL query.

    The agent can run SQL queries, submit fixes, or analyze the schema.
    Each action includes an optional reasoning field for interpretability.
    """

    type: Literal["run_sql", "fix_query", "analyze"] = Field(
        description="The type of action: run_sql (execute), fix_query (submit fix), analyze (inspect schema)"
    )
    sql: Optional[str] = Field(
        default=None,
        max_length=10000,
        description="The SQL query to execute or the proposed fix",
    )
    reasoning: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Agent's reasoning about why this query should work",
    )


# =============================================================================
# Observation — What the environment returns to the agent
# =============================================================================


class SQLObservation(OpenEnvObservation):
    """An observation returned by the environment after a step or reset.

    Contains the task context (broken query, schema), the result of the
    agent's last query execution, and episode progress metadata.
    """

    task_id: str = Field(description="Current task identifier (easy/medium/hard)")
    broken_query: str = Field(description="The original broken SQL query to fix")
    db_schema: str = Field(description="The database schema as CREATE TABLE statements")
    query_result: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Result rows from the last executed query"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if the last query failed"
    )
    hint: Optional[str] = Field(
        default=None, description="Optional hint from the environment (e.g., EXPLAIN output)"
    )
    step_count: int = Field(default=0, description="Number of steps taken so far")
    # done and reward are inherited from OpenEnvObservation


# =============================================================================
# State — Internal episode state exposed via /state
# =============================================================================


class SQLState(OpenEnvState):
    """Internal state of the SQL debug environment session.

    Provides episode-level metadata for observability and debugging.
    Extends OpenEnv's base State with SQL-specific fields.
    """

    task_id: Optional[str] = Field(
        default=None, description="Active task identifier"
    )
    max_steps: int = Field(default=10, description="Maximum steps per episode")
    cumulative_reward: float = Field(
        default=0.0, description="Total reward accumulated this episode"
    )
    history_length: int = Field(
        default=0, description="Number of steps recorded in history"
    )


# =============================================================================
# Reward — Detailed reward breakdown (used internally, not an OpenEnv type)
# =============================================================================


class Reward(BaseModel):
    """Detailed reward breakdown for a single step.

    Provides fine-grained reward signals for training:
    - step_reward: immediate reward for this action
    - cumulative_reward: total reward across the episode
    - correctness: how close the result is to expected output (0.0 - 1.0)
    - performance: query execution time in milliseconds
    """

    model_config = ConfigDict(extra="forbid")
    step_reward: float = Field(description="Reward for this single step")
    cumulative_reward: float = Field(description="Total reward across all steps")
    correctness: float = Field(
        ..., ge=0.0, le=1.0, description="Result correctness score"
    )
    performance: Optional[float] = Field(
        default=None, description="Query execution time in milliseconds"
    )

    @field_validator("cumulative_reward")
    @classmethod
    def validate_reward(cls, v: float) -> float:
        """Ensure cumulative reward stays within reasonable bounds."""
        if not (-1000 <= v <= 1000):
            raise ValueError("cumulative_reward out of bounds")
        return v


# =============================================================================
# TaskInfo — Internal task definition (not exposed to agent)
# =============================================================================


class TaskInfo(BaseModel):
    """Internal task definition containing the ground truth.

    This model holds the broken query, expected output, and database path.
    It is NOT sent to the agent — only the observation fields are visible.
    """

    model_config = ConfigDict(extra="forbid")
    task_id: str = Field(description="Task identifier (easy/medium/hard)")
    broken_query: str = Field(description="The deliberately broken SQL query")
    schema_sql: str = Field(description="Database schema as CREATE TABLE statements")
    expected_output: List[Dict[str, Any]] = Field(
        description="Expected correct query result rows"
    )
    db_path: str = Field(description="Path to the SQLite database file")
