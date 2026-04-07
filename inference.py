"""
inference.py — SQL Debug Environment
OpenEnv Hackathon by Meta x Hugging Face x Scalar

STDOUT FORMAT (strictly followed):
    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
"""

import os
import json
import time
from typing import List, Optional
import httpx
from openai import OpenAI

# ── Environment variables (required by Meta spec) ────────────────────────────
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or os.getenv("GROQ_API_KEY", "")
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"

# ── Environment server ────────────────────────────────────────────────────────
SERVER_URL = os.getenv("SERVER_URL") or "https://aryan-coder-25-openenv.hf.space"

# ── Episode config ────────────────────────────────────────────────────────────
BENCHMARK = "sql-debug-env"
MAX_STEPS = 10
TEMPERATURE = 0.1
MAX_TOKENS = 512
SUCCESS_SCORE_THRESHOLD = 0.8


# ── Structured log helpers (exact Meta format) ────────────────────────────────


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(
    step: int, action: str, reward: float, done: bool, error: Optional[str]
) -> None:
    error_val = error if error else "null"
    done_val = "true" if done else "false"
    action_str = action.replace("\n", " ").replace("\r", " ")
    print(
        f"[STEP] step={step} action={action_str} "
        f"reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    success_val = "true" if success else "false"
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={success_val} steps={steps} "
        f"score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


# ── OpenAI client ─────────────────────────────────────────────────────────────


def make_client() -> OpenAI:
    return OpenAI(api_key=API_KEY, base_url=API_BASE_URL)


# ── LLM call ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a SQL expert. You will receive a broken SQL query and a database schema. "
    "Fix the query so it produces the correct result. "
    "Always respond ONLY with a JSON object — no markdown, no explanation outside JSON. "
    'Format: {"type": "run_sql", "sql": "YOUR FIXED QUERY HERE", "reasoning": "brief explanation"}'
)


def get_action(client: OpenAI, obs: dict, history: List[dict]) -> dict:
    """Ask the LLM to fix the broken SQL query. Returns a parsed action dict."""

    history_lines = ""
    for h in history[-3:]:  # last 3 steps for context
        history_lines += (
            f"\nStep {h['step']}: submitted {h['sql']!r} "
            f"→ correctness {h['correctness']:.2f}, error: {h['error']}"
        )

    user_content = (
        f"Schema:\n{obs.get('db_schema', '')}\n\n"
        f"Broken query:\n{obs.get('broken_query', '')}\n\n"
        f"Previous attempts:{history_lines if history_lines else ' none'}\n\n"
        "Fix the broken query. Return JSON only."
    )

    for attempt in range(3):
        try:
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                stream=False,
            )
            text = (completion.choices[0].message.content or "").strip()
            action = json.loads(text)
            if action.get("type") not in ["run_sql", "fix_query", "analyze"]:
                action["type"] = "run_sql"
            return action
        except json.JSONDecodeError:
            return {"type": "run_sql", "sql": text, "reasoning": "raw LLM output"}
        except Exception as exc:
            if "rate_limit" in str(exc).lower() and attempt < 2:
                time.sleep(30 * (attempt + 1))
            else:
                return {"type": "run_sql", "sql": "", "reasoning": f"LLM error: {exc}"}

    return {"type": "run_sql", "sql": "", "reasoning": "max retries exceeded"}


# ── Single task runner ────────────────────────────────────────────────────────


def run_task(task_id: str) -> float:
    client = make_client()
    rewards: List[float] = []
    history: List[dict] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    try:
        # reset
        r = httpx.post(f"{SERVER_URL}/reset", json={"task_id": task_id}, timeout=30)
        if r.status_code != 200:
            log_end(success=False, steps=0, score=0.01, rewards=[])
            return 0.01

        obs = r.json()
        done = False

        for step in range(1, MAX_STEPS + 1):
            if done:
                break

            action = get_action(client, obs, history)
            action_str = json.dumps(action, separators=(",", ":"))

            step_r = httpx.post(f"{SERVER_URL}/step", json=action, timeout=60)

            reward = 0.0
            error_msg = None
            correctness = 0.0

            if step_r.status_code == 200:
                result = step_r.json()
                obs_data = result.get("observation", result)
                obs = obs_data if isinstance(obs_data, dict) else {}
                reward_data = result.get("reward", {})
                reward = float(reward_data.get("step_reward", 0.0))
                correctness = float(reward_data.get("correctness", 0.0))
                done = bool(result.get("done", False))
                error_msg = obs.get("error_message")
            else:
                error_msg = f"HTTP {step_r.status_code}"
                done = True

            rewards.append(reward)
            steps_taken = step

            log_step(
                step=step,
                action=action_str,
                reward=reward,
                done=done,
                error=error_msg,
            )

            history.append(
                {
                    "step": step,
                    "sql": action.get("sql", ""),
                    "correctness": correctness,
                    "error": error_msg,
                }
            )

            if correctness >= 1.0:
                done = True

        # get final grader score
        grader_r = httpx.get(f"{SERVER_URL}/grader", timeout=30)
        if grader_r.status_code == 200:
            score = float(grader_r.json().get("score", 0.01))
        else:
            score = max(rewards) if rewards else 0.01

        score = min(max(score, 0.01), 0.99)
        success = score >= SUCCESS_SCORE_THRESHOLD

    except Exception as exc:
        print(f"[DEBUG] Task {task_id} error: {exc}", flush=True)
        score = 0.01
        success = False

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


# ── Run all three tasks ───────────────────────────────────────────────────────


def main() -> None:
    print(f"[DEBUG] model={MODEL_NAME} server={SERVER_URL}", flush=True)

    results = {}
    for task_id in ["easy", "medium", "hard"]:
        print(f"\n[DEBUG] Starting task: {task_id}", flush=True)
        results[task_id] = run_task(task_id)

    print("\n[DEBUG] === Final Scores ===", flush=True)
    for task_id, score in results.items():
        bar = "█" * int(score * 20)
        print(f"[DEBUG]   {task_id:<10} {score:.4f}  {bar}", flush=True)


if __name__ == "__main__":
    main()
