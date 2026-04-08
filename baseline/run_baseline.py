import os
import json
import time
import asyncio
import httpx
from openai import AsyncOpenAI

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

if GROQ_API_KEY:
    client = AsyncOpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
    MODEL = "llama-3.3-70b-versatile"
elif OPENAI_API_KEY:
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    MODEL = "gpt-4o"
else:
    client = None
    MODEL = None

SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:7860")


async def run_task(task_id: str) -> float:
    if client is None:
        return {
            "score": 0.01,
            "error": "No API key set. Set GROQ_API_KEY or OPENAI_API_KEY.",
            "task_id": task_id,
        }

    try:
        async with httpx.AsyncClient() as http_client:
            r = await http_client.post(f"{SERVER_URL}/reset", json={"task_id": task_id}, timeout=30)
            if r.status_code != 200:
                print(f"Reset failed: {r.status_code}")
                return 0.01

            obs = r.json()
            if not obs.get("task_id"):
                return 0.01

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a SQL expert. Fix broken SQL queries. "
                        "Always respond ONLY in JSON like this: "
                        '{"type": "run_sql", "sql": "FIXED SQL HERE", "reasoning": "explanation"}'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Schema:\n{obs.get('db_schema', '')}\n\n"
                        f"Broken query:\n{obs.get('broken_query', '')}\n\n"
                        "Fix this query. Return JSON only."
                    ),
                },
            ]

            done = False
            steps = 0
            max_steps = 10

            session_id = obs.get("session_id")

            while not done and steps < max_steps:
                steps += 1

                for attempt in range(3):
                    try:
                        response = await client.chat.completions.create(
                            model=MODEL,
                            messages=messages,
                            response_format={"type": "json_object"},
                            temperature=0.1,
                        )
                        break
                    except Exception as e:
                        if "rate_limit" in str(e).lower() and attempt < 2:
                            wait_time = 30 * (attempt + 1)
                            print(f"Rate limit hit, waiting {wait_time}s...")
                            await asyncio.sleep(wait_time)
                        else:
                            raise e

                action_json = response.choices[0].message.content
                action = json.loads(action_json)

                if action.get("type") not in ["run_sql", "fix_query", "analyze"]:
                    action["type"] = "run_sql"

                if session_id:
                    action["session_id"] = session_id

                step_r = await http_client.post(f"{SERVER_URL}/step", json=action, timeout=60)

                if step_r.status_code != 200:
                    print(f"Step failed: {step_r.status_code}")
                    break

                result = step_r.json()

                obs_data = result.get("observation", result)
                obs = obs_data if isinstance(obs_data, dict) else dict(obs_data)

                reward_data = result.get("reward", {})
                reward = reward_data if isinstance(reward_data, dict) else dict(reward_data)

                done = result.get("done", False)
                correctness = reward.get("correctness", 0.0)
                step_reward = reward.get("step_reward", 0.0)

                messages.append({"role": "assistant", "content": action_json})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Result: {obs.get('query_result', [])}\n"
                            f"Error: {obs.get('error_message', None)}\n"
                            f"Step reward: {step_reward}\n"
                            f"Correctness: {correctness}\n"
                            "If correctness < 1.0, try again with a better fix."
                        ),
                    }
                )

                if correctness >= 1.0:
                    break

            grader_params = {"session_id": session_id} if session_id else {}
            grader_r = await http_client.get(f"{SERVER_URL}/grader", params=grader_params, timeout=30)
            if grader_r.status_code == 200:
                return round(max(0.01, min(0.99, float(grader_r.json().get("score", 0.01)))), 4)
            return 0.01

    except Exception as e:
        print(f"Error on task {task_id}: {e}")
        return 0.01


async def run_all_tasks() -> dict:
    results = {}
    for task_id in ["easy", "medium", "hard"]:
        print(f"Running task: {task_id}...")
        score = await run_task(task_id)
        if isinstance(score, dict):
            results[task_id] = score
        else:
            results[task_id] = round(float(score), 4)
        print(f"  Score: {results[task_id]}")
    return results


if __name__ == "__main__":
    print("Starting baseline agent...")
    print(f"Model: {MODEL}")
    print(f"Server: {SERVER_URL}")
    print("=" * 40)

    scores = asyncio.run(run_all_tasks())

    print()
    print("Final Baseline Scores")
    print("=" * 40)
    for task, score in scores.items():
        if isinstance(score, dict):
            print(f"  {task:<10} : ERROR - {score.get('error')}")
        else:
            bar = "█" * int(score * 20)
            print(f"  {task:<10} : {score:.4f}  {bar}")
    print("=" * 40)
