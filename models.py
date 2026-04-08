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
    session_id: Optional[str] = None


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


