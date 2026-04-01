import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models import Action
from environment import SQLDebugEnv
from grader import grade_episode

app = FastAPI(
    title="SQL Debug Environment",
    description="OpenEnv environment for SQL debugging tasks",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

env = SQLDebugEnv()


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/reset")
def reset(task_id: str = "easy"):
    try:
        obs = env.reset(task_id)
        return obs
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/step")
def step(action: Action):
    try:
        if not env.current_task:
            raise HTTPException(
                status_code=400,
                detail="Call /reset first before /step"
            )
        obs, reward, done, info = env.step(action)
        return {
            "observation": obs,
            "reward": reward,
            "done": done,
            "info": info
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/state")
def state():
    try:
        return env.state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks")
def list_tasks():
    return {
        "tasks": [
            {
                "id": "easy",
                "name": "Syntax repair",
                "difficulty": "easy",
                "description": "Fix a syntax error in a SQL query",
                "action_schema": Action.model_json_schema()
            },
            {
                "id": "medium",
                "name": "Join logic fix",
                "difficulty": "medium",
                "description": "Fix wrong JOIN type causing missing rows",
                "action_schema": Action.model_json_schema()
            },
            {
                "id": "hard",
                "name": "Performance optimization",
                "difficulty": "hard",
                "description": "Fix logic error and optimize slow query",
                "action_schema": Action.model_json_schema()
            },
        ]
    }


@app.get("/grader")
def grader():
    try:
        return grade_episode(env.history, env.current_task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/baseline")
def baseline():
    try:
        from baseline.run_baseline import run_all_tasks
        return run_all_tasks()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))