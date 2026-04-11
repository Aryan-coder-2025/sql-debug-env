import os
from fastapi import APIRouter, HTTPException, Request
from routers.state import get_env, get_multi_env, sessions, multi_sessions
from models import SQLAction
from environment import SQLDebugEnv
from multi_step_env import MultiStepSQLEnv
from grader import grade_episode
from tasks.task_easy import EASY_SCENARIOS
from tasks.task_medium import MEDIUM_SCENARIOS
from tasks.task_hard import HARD_SCENARIOS
from tasks.task_security import SECURITY_SCENARIOS

try:
    from dynamic_schema import DynamicSQLEnv
    HAS_DYNAMIC = True
except ImportError:
    HAS_DYNAMIC = False

router = APIRouter()

@router.post("/reset")
async def reset_env(request: Request):
    """Reset the environment and start a new episode."""
    try:
        try:
            import json
            body = await request.json()
            task_id = body.get("task_id", "easy")
            session_id = body.get("session_id")
            use_dynamic = body.get("dynamic", False)
            seed = body.get("seed", None)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        except Exception:
            task_id = "easy"
            session_id = None
            use_dynamic = False
            seed = None

        if use_dynamic:
            if not HAS_DYNAMIC:
                raise HTTPException(status_code=501, detail="Dynamic schema module not available")
            dynamic_env = DynamicSQLEnv(seed=seed)
            obs = dynamic_env.reset(task_id=task_id)
            sid = session_id or "default"
            sessions[sid] = dynamic_env
            multi_sessions[sid] = MultiStepSQLEnv(dynamic_env)
            multi_sessions[sid].reset(task_id=task_id)
            result = obs.model_dump()
            result["mode"] = "dynamic"
            result["note"] = "This scenario was randomly generated. Use seed for reproducibility."
            return result

        if task_id not in ["easy", "medium", "hard", "security"]:
            raise HTTPException(status_code=400, detail="INVALID TASK_ID")

        env = get_env(session_id)
        obs = env.reset(task_id=task_id)

        multi = get_multi_env(session_id)
        multi.reset(task_id=task_id)

        return obs.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/step")
async def step_env(request: Request):
    """Submit a SQL action to the environment."""
    try:
        import json
        try:
            body = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        session_id = body.get("session_id")
        command = body.get("command", "").strip()
        sql = body.get("sql", "").strip()

        if command:
            multi = get_multi_env(session_id)
            if not multi.base_env.current_task:
                multi.reset(task_id="easy")
            result = multi.step(command)
            if len(result) == 5:
                obs, reward, done, truncated, info = result
            else:
                obs, reward, done, info = result

            base_env = multi.base_env
            cum_reward = round(multi.cumulative_reward, 4)

            return {
                "observation": {
                    "task_id": base_env.current_task.task_id if base_env.current_task else None,
                    "broken_query": obs.get("query", ""),
                    "db_schema": obs.get("schema_hint", ""),
                    "query_result": None,
                    "error_message": None,
                    "step_count": info.get("step_count", multi.current_step),
                    "done": done,
                },
                "reward": {
                    "step_reward": round(reward, 4),
                    "cumulative_reward": cum_reward,
                    "correctness": info.get("correctness", 0.0),
                    "performance": 0.0,
                },
                "done": done,
                "info": {
                    "feedback": info.get("feedback", ""),
                    "action": info.get("action", command),
                    "mode": "multi_step",
                    "available_commands": ["SHOW_TABLES", "DESCRIBE <table>", "EXPLAIN <sql>", "SUBMIT_QUERY <sql>", "GIVE_UP"],
                },
            }

        if "command" in body and not command:
            return {
                "observation": {"error_message": "Empty command. Use SHOW_TABLES..."},
                "reward": {"step_reward": 0.0, "cumulative_reward": 0.0, "correctness": 0.0, "performance": 0.0},
                "done": False,
                "info": {"error": "empty_command", "mode": "multi_step"},
            }

        env = get_env(session_id)
        if not env.current_task:
            env.reset(task_id="easy")

        action = SQLAction(**{k: v for k, v in body.items() if k not in ("session_id", "command")})

        if not action.sql or not action.sql.strip():
            return {
                "observation": {"error_message": "Empty SQL query submitted"},
                "reward": {"step_reward": -0.05, "cumulative_reward": round(env.cumulative_reward - 0.05, 4), "correctness": 0.0, "performance": 0.0},
                "done": False,
                "info": {"error": "empty_sql", "mode": "legacy"},
            }

        obs = env.step(action)
        obs_dict = obs.model_dump()
        return {
            "observation": obs_dict,
            "reward": {
                "step_reward": obs_dict.get("reward", 0.0),
                "cumulative_reward": obs_dict.get("metadata", {}).get("cumulative_reward", 0.0),
                "correctness": obs_dict.get("metadata", {}).get("correctness", 0.0),
                "performance": obs_dict.get("metadata", {}).get("performance_ms", 0.0),
            },
            "done": obs_dict.get("done", False),
            "info": {"mode": "legacy"},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/state")
def get_state(session_id: str = None):
    try:
        return get_env(session_id).state.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks")
def list_tasks():
    return {
        "tasks": [
            {"id": "easy", "name": "Syntax repair", "difficulty": "easy", "scenarios": len(EASY_SCENARIOS), "scenario_names": [s["name"] for s in EASY_SCENARIOS]},
            {"id": "medium", "name": "Join logic fix", "difficulty": "medium", "scenarios": len(MEDIUM_SCENARIOS), "scenario_names": [s["name"] for s in MEDIUM_SCENARIOS]},
            {"id": "hard", "name": "Performance", "difficulty": "hard", "scenarios": len(HARD_SCENARIOS), "scenario_names": [s["name"] for s in HARD_SCENARIOS]},
            {"id": "security", "name": "Security fix", "difficulty": "hard", "scenarios": len(SECURITY_SCENARIOS), "scenario_names": [s["name"] for s in SECURITY_SCENARIOS]},
        ]
    }

@router.get("/grader")
def grader(session_id: str = None):
    try:
        env = get_env(session_id)
        return grade_episode(env.history, env.current_task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/baseline")
async def baseline():
    try:
        hf_space_host = os.environ.get("SPACE_HOST", "")
        if hf_space_host:
            os.environ["SERVER_URL"] = f"https://{hf_space_host}"
        from baseline.run_baseline import run_all_tasks
        return await run_all_tasks()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
