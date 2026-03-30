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
            {
                "id": "easy",
                "name": "Syntax repair",
                "difficulty": "easy",
                "action_schema": Action.model_json_schema(),
            },
            {
                "id": "medium",
                "name": "Join logic fix",
                "difficulty": "medium",
                "action_schema": Action.model_json_schema(),
            },
            {
                "id": "hard",
                "name": "Performance optimization",
                "difficulty": "hard",
                "action_schema": Action.model_json_schema(),
            },
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
@app.get("/baseline")
def baseline():
    try:
        results = {}
        for task_id in ["easy", "medium", "hard"]:
            obs = env.reset(task_id)
            done = False
            total_reward = 0.0
            steps = 0
            while not done and steps < 10:
                from tasks.task_easy import get_task
                task = env.current_task
                if task_id == "easy":
                    from tasks.task_easy import get_task as gt
                elif task_id == "medium":
                    from tasks.task_medium import get_task as gt
                else:
                    from tasks.task_hard import get_task as gt
                t = gt()
                action = Action(type="fix_query", sql=t.broken_query)
                obs, reward, done, info = env.step(action)
                total_reward = reward.cumulative_reward
                steps += 1
            results[task_id] = round(total_reward, 3)
        return {"status": "ok", "scores": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))