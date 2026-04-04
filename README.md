# 🛠️ SQL Debug Environment

> An OpenEnv-compatible reinforcement learning environment for training AI agents to debug SQL queries — built for the **OpenEnv Hackathon by Meta × Hugging Face × Scalar School of Technology**.

[![Live Demo](https://img.shields.io/badge/🤗%20HF%20Space-Live-blue)](https://aryan-coder-25-openenv.hf.space)
[![Python](https://img.shields.io/badge/Python-3.12-green)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-orange)](https://fastapi.tiangolo.com)

---

## 🧠 What This Environment Does

An agent receives a **broken SQL query** and a **database schema**. It must fix the query step-by-step, earning rewards based on:

- ✅ **Correctness** — does the output match the expected result?
- ⚡ **Efficiency** — fewer steps = higher reward
- 🎯 **Precision** — partial credit for partially correct results

The environment supports 3 difficulty levels across real SQLite databases with 100k+ rows.

---

## 🚀 Quick Start

### Run Locally

```bash
git clone https://github.com/Aryan-coder-2025/sql-debug-env
cd sql-debug-env
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 7860
```

### Run with Docker

```bash
docker build -t sql-debug-env .
docker run -p 7860:7860 sql-debug-env
```

### Live API

```
https://aryan-coder-25-openenv.hf.space
```

---

## 🎮 Tasks

| Task     | Difficulty | Database     | Description                                          |
| -------- | ---------- | ------------ | ---------------------------------------------------- |
| `easy`   | 🟢 Easy    | employees.db | Fix a syntax error in a broken SELECT query          |
| `medium` | 🟡 Medium  | ecommerce.db | Fix wrong JOIN type causing missing rows             |
| `hard`   | 🔴 Hard    | analytics.db | Fix correlated subquery logic + optimize performance |

---

## 📡 API Endpoints

| Method | Endpoint    | Description                     |
| ------ | ----------- | ------------------------------- |
| `GET`  | `/`         | Environment info and status     |
| `GET`  | `/health`   | Health check                    |
| `GET`  | `/tasks`    | List all tasks with schemas     |
| `GET`  | `/state`    | Current environment state       |
| `GET`  | `/grader`   | Get episode score               |
| `GET`  | `/metadata` | Full environment metadata       |
| `POST` | `/reset`    | Start a new episode             |
| `POST` | `/step`     | Submit a SQL fix action         |
| `POST` | `/mcp`      | MCP-compatible tool interface   |
| `GET`  | `/baseline` | Run baseline agent on all tasks |

---

## 🔄 Agent Loop

```python
import httpx

BASE = "https://aryan-coder-25-openenv.hf.space"

# 1. Reset the environment
obs = httpx.post(f"{BASE}/reset", json={"task_id": "easy"}).json()
print(obs["broken_query"])   # The broken SQL to fix
print(obs["db_schema"])      # The database schema

# 2. Submit a fix
result = httpx.post(f"{BASE}/step", json={
    "type": "run_sql",
    "sql": "SELECT * FROM employees WHERE department = 'HR'",
    "reasoning": "Fixed missing quotes around string value"
}).json()

print(result["reward"]["correctness"])  # 0.0 to 1.0
print(result["done"])                   # True if episode complete

# 3. Get final score
score = httpx.get(f"{BASE}/grader").json()
print(score["score"])  # Final episode score
```

---

## 📐 Action Space

Each action is a JSON object:

```json
{
  "type": "run_sql",
  "sql": "SELECT id, name FROM employees WHERE active = 1",
  "reasoning": "Fixed column name and added WHERE clause"
}
```

| Field       | Type   | Required | Options                           |
| ----------- | ------ | -------- | --------------------------------- |
| `type`      | string | ✅       | `run_sql`, `fix_query`, `analyze` |
| `sql`       | string | ✅       | Any valid SELECT query            |
| `reasoning` | string | ❌       | Agent's explanation               |

---

## 👁️ Observation Space

Each step returns an observation:

```json
{
  "task_id": "easy",
  "broken_query": "SELEC * FORM employees",
  "db_schema": "CREATE TABLE employees ...",
  "query_result": [{ "id": 1, "name": "Alice" }],
  "error_message": null,
  "step_count": 1,
  "done": false
}
```

---

## 🏆 Reward Structure

| Condition                      | Value               |
| ------------------------------ | ------------------- |
| Correctness (0–100%)           | `0.0 – 1.0`         |
| Efficiency bonus (fewer steps) | `up to +0.10`       |
| Regression penalty (got worse) | `up to -0.10`       |
| Empty query penalty            | `up to -0.10`       |
| **Max possible score**         | **`1.00`** (capped) |

---

## 📊 Baseline Scores

Tested with `llama-3.3-70b-versatile` via Groq API:

| Task   | Score       | Status                |
| ------ | ----------- | --------------------- |
| Easy   | 1.00        | ✅ Perfect            |
| Medium | 0.54 – 1.00 | ✅ Varies by scenario |
| Hard   | 1.00        | ✅ Perfect            |

> Run your own baseline: `python baseline/run_baseline.py`

---

## 🗂️ Project Structure

```
sql-debug-env/
├── main.py                  # FastAPI app + all endpoints
├── environment.py           # Core RL environment logic
├── grader.py                # Episode scoring
├── models.py                # Pydantic models
├── baseline/
│   └── run_baseline.py      # Baseline agent (LLM-powered)
├── tasks/
│   ├── task_easy.py
│   ├── task_medium.py
│   └── task_hard.py
├── databases/
│   ├── employees.db
│   ├── ecommerce.db
│   └── analytics.db
├── Dockerfile
├── requirements.txt
└── openenv.yaml
```

---

## 🔧 Environment Variables

| Variable         | Description                     | Default                 |
| ---------------- | ------------------------------- | ----------------------- |
| `GROQ_API_KEY`   | Groq API key for baseline agent | —                       |
| `OPENAI_API_KEY` | OpenAI API key (fallback)       | —                       |
| `SERVER_URL`     | Environment server URL          | `http://localhost:7860` |

---

## 👥 Authors

Built by **Aarush, Chetanya & Aryan** for the OpenEnv Hackathon by Meta × Hugging Face × Scalar School of Technology.
