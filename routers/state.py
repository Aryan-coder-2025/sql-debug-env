from typing import Dict, Any

# In-memory maps for sessions
sessions: Dict[str, Any] = {}
multi_sessions: Dict[str, Any] = {}

def get_env(session_id: str):
    from environment import SQLDebugEnv
    sid = session_id or "default"
    if sid not in sessions:
        sessions[sid] = SQLDebugEnv()
    return sessions[sid]

def get_multi_env(session_id: str):
    from multi_step_env import MultiStepSQLEnv
    sid = session_id or "default"
    if sid not in multi_sessions:
        multi_sessions[sid] = MultiStepSQLEnv(get_env(session_id))
    return multi_sessions[sid]
