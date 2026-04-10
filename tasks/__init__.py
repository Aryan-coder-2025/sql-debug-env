"""
tasks/ — SQL Debug Environment Task Definitions
OpenEnv Hackathon by Meta × Hugging Face × Scaler School of Technology

Contains task generators for four difficulty levels:
- easy: Syntax errors (11 scenarios)
- medium: JOIN logic bugs (9 scenarios)
- hard: CTE/subquery optimization (9 scenarios)
- security: SQL injection / data leak fixes (5 scenarios)
"""

from tasks.task_easy import get_task as get_easy
from tasks.task_medium import get_task as get_medium
from tasks.task_hard import get_task as get_hard
from tasks.task_security import get_task as get_security

__all__ = ["get_easy", "get_medium", "get_hard", "get_security"]
