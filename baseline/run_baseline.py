import os
import json
import httpx
from openai import OpenAI

SERVER_URL = "http://localhost:7860"
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "your-key-here"))


def run_task(task_id: str) -> float:

    # Reset the environment for this task
    r = httpx.post(f"{SERVER_URL}/reset", params={"task_id": task_id})
    obs = r.json()

    # Build the conversation for GPT-4o
    messages = [
        {
            "role": "system",
            "content": (
                "You are a SQL expert. You fix broken SQL queries. "
                "Always respond in JSON format exactly like this: "
                '{"type": "run_sql", "sql": "YOUR FIXED SQL HERE", '
                '"reasoning": "why you made this fix"}'
            ),
        },
        {
            "role": "user",
            "content": (
                f"Database schema:\n{obs['db_schema']}\n\n"
                f"Broken query:\n{obs['broken_query']}\n\n"
                "Fix this query and return your answer as JSON."
            ),
        },
    ]

    done = False
    total_reward = 0.0

    # Agent keeps trying until done or max steps reached
    while not done:

        # Ask GPT-4o to fix the query
        response = client.chat.completions.create(
            model="gpt-4o", messages=messages, response_format={"type": "json_object"}
        )

        action_json = response.choices[0].message.content
        action = json.loads(action_json)

        # Send the attempted fix to our environment
        result = httpx.post(f"{SERVER_URL}/step", json=action).json()

        obs = result["observation"]
        reward = result["reward"]
        done = result["done"]
        total_reward = reward["cumulative_reward"]

        # Add feedback to conversation so agent learns from it
        messages.append({"role": "assistant", "content": action_json})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Result rows: {obs['query_result']}\n"
                    f"Error: {obs['error_message']}\n"
                    f"Step reward: {reward['step_reward']}\n"
                    f"Correctness: {reward['correctness']}\n"
                    "If not fully correct, try again with a better fix."
                ),
            }
        )

    # Get final graded score
    final = httpx.get(f"{SERVER_URL}/grader").json()
    return final["score"]


def run_all_tasks() -> dict:
    results = {}

    for task_id in ["easy", "medium", "hard"]:
        print(f"\nRunning task: {task_id} ...")
        try:
            score = run_task(task_id)
            results[task_id] = round(score, 4)
            print(f"  Score: {score:.4f}")
        except Exception as e:
            results[task_id] = 0.0
            print(f"  Error on {task_id}: {e}")

    return results


if __name__ == "__main__":
    print("Starting baseline agent ...")
    print("=" * 35)

    scores = run_all_tasks()

    print("\nFinal Baseline Scores")
    print("=" * 35)
    for task, score in scores.items():
        bar = "█" * int(score * 20)
        print(f"  {task:<10} : {score:.4f}  {bar}")
    print("=" * 35)
