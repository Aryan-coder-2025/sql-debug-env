"""
client.py — SQL Debug Environment Client
OpenEnv Hackathon by Meta × Hugging Face × Scaler School of Technology

Provides an EnvClient subclass for interacting with the SQL Debug
Environment over WebSocket. Other developers can install and use this:

    from client import SQLDebugAction, SQLDebugEnv
    async with SQLDebugEnv(base_url="https://aryan-coder-25-openenv.hf.space") as env:
        result = await env.reset(task_id="easy")
        print(result.observation.broken_query)
        result = await env.step(SQLDebugAction(type="run_sql", sql="SELECT ..."))
        print(result.observation.query_result)
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from openenv.core.env_client import EnvClient
from openenv.core.client_types import StepResult


@dataclass
class SQLDebugObservation:
    """Parsed observation from the SQL Debug Environment.

    Attributes:
        task_id: Current task identifier.
        broken_query: The broken SQL query to fix.
        db_schema: Database schema as CREATE TABLE statements.
        query_result: Result rows from the last executed query.
        error_message: Error message if the last query failed.
        hint: Optional debugging hint from the environment.
        step_count: Steps taken so far.
        done: Whether the episode has ended.
        reward: Reward for the last action.
    """

    task_id: str = ""
    broken_query: str = ""
    db_schema: str = ""
    query_result: Optional[list] = None
    error_message: Optional[str] = None
    hint: Optional[str] = None
    step_count: int = 0
    done: bool = False
    reward: float = 0.0
    metadata: Optional[dict] = None


@dataclass
class SQLDebugAction:
    """Action to send to the SQL Debug Environment.

    Attributes:
        type: Action type — 'run_sql', 'fix_query', or 'analyze'.
        sql: The SQL query to execute.
        reasoning: Optional explanation of why this query should work.
    """

    type: str = "run_sql"
    sql: str = ""
    reasoning: str = ""


@dataclass
class SQLDebugState:
    """State from the SQL Debug Environment.

    Attributes:
        episode_id: Unique episode identifier.
        step_count: Steps taken in current episode.
        task_id: Active task identifier.
        max_steps: Maximum allowed steps.
        cumulative_reward: Total reward accumulated.
    """

    episode_id: Optional[str] = None
    step_count: int = 0
    task_id: Optional[str] = None
    max_steps: int = 10
    cumulative_reward: float = 0.0
    history_length: int = 0


class SQLDebugEnv(EnvClient[SQLDebugAction, SQLDebugObservation, SQLDebugState]):
    """WebSocket client for the SQL Debug Environment.

    Usage (async):
        async with SQLDebugEnv(base_url="http://localhost:7860") as env:
            result = await env.reset(task_id="easy")
            while not result.done:
                action = SQLDebugAction(type="run_sql", sql="SELECT ...")
                result = await env.step(action)
            print(f"Final reward: {result.reward}")

    Usage (sync):
        with SQLDebugEnv(base_url="http://localhost:7860").sync() as env:
            result = env.reset(task_id="easy")
            result = env.step(SQLDebugAction(type="run_sql", sql="SELECT ..."))
    """

    def _step_payload(self, action: SQLDebugAction) -> Dict[str, Any]:
        """Convert a SQLDebugAction to the JSON payload for the server."""
        payload = {"type": action.type}
        if action.sql:
            payload["sql"] = action.sql
        if action.reasoning:
            payload["reasoning"] = action.reasoning
        return payload

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[SQLDebugObservation]:
        """Parse the server response into a StepResult with typed observation."""
        obs_data = payload.get("observation", payload)
        if isinstance(obs_data, dict):
            observation = SQLDebugObservation(
                task_id=obs_data.get("task_id", ""),
                broken_query=obs_data.get("broken_query", ""),
                db_schema=obs_data.get("db_schema", ""),
                query_result=obs_data.get("query_result"),
                error_message=obs_data.get("error_message"),
                hint=obs_data.get("hint"),
                step_count=obs_data.get("step_count", 0),
                done=obs_data.get("done", False),
                reward=obs_data.get("reward", 0.0),
                metadata=obs_data.get("metadata"),
            )
        else:
            observation = SQLDebugObservation()

        return StepResult(
            observation=observation,
            reward=payload.get("reward", observation.reward),
            done=payload.get("done", observation.done),
        )

    def _parse_state(self, payload: Dict[str, Any]) -> SQLDebugState:
        """Parse the server state response into a typed SQLDebugState."""
        return SQLDebugState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            task_id=payload.get("task_id"),
            max_steps=payload.get("max_steps", 10),
            cumulative_reward=payload.get("cumulative_reward", 0.0),
            history_length=payload.get("history_length", 0),
        )
