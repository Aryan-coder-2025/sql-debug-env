from fastapi import FastAPI, HTTPException
from models import Action
from environment import SQLDebugEnv
from grader import grade_episode

app = FastAPI(title="SQL Debug Environment")

env = SQLDebugEnv()


@app.post("/reset")
def reset(task_id: str = "easy"):
    try:
        obs = env.reset(task_id)
        return obs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/step")
def step(action: Action):
    try:
        obs, reward, done, info = env.step(action)
        return {"observation": obs, "reward": reward, "done": done, "info": info}
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
            {"id": "easy", "name": "Syntax repair", "difficulty": "easy"},
            {"id": "medium", "name": "Join logic fix", "difficulty": "medium"},
            {"id": "hard", "name": "Performance optimization", "difficulty": "hard"},
        ]
    }


@app.get("/grader")
def grader():
    try:
        return grade_episode(env.history, env.current_task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}
