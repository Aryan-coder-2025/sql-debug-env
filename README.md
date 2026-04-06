---
title: Openenv
emoji: 🛠️
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# 🛠️ SQL Debug Environment

An OpenEnv-compatible reinforcement learning environment for training AI agents to debug SQL queries — built for the OpenEnv Hackathon by Meta × Hugging Face × Scalar School of Technology.

![Live Demo](https://img.shields.io/badge/Live-Demo-blue) ![Python](https://img.shields.io/badge/Python-3.12-green) ![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)

---

## 🧠 What This Environment Does

An agent receives a broken SQL query and a database schema. It must fix the query step-by-step, earning rewards based on:

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

| Task   | Difficulty | Database     | Description                                          |
| ------ | ---------- | ------------ | ---------------------------------------------------- |
| easy   | 🟢 Easy    | employees.db | Fix a syntax error in a broken SELECT query          |
| medium | 🟡 Medium  | ecommerce.db | Fix wrong JOIN type causing missing rows             |
| hard   | 🔴 Hard    | analytics.db | Fix correlated subquery logic + optimize performance |

---

## 📡 API Endpoints

| Method | Endpoint    | Description                     |
| ------ | ----------- | ------------------------------- |
| GET    | `/`         | Environment info and status     |
| GET    | `/health`   | Health check                    |
| GET    | `/tasks`    | List all tasks with schemas     |
| GET    | `/state`    | Current environment state       |
| GET    | `/grader`   | Get episode score               |
| GET    | `/metadata` | Full environment metadata       |
| GET    | `/validate` | OpenEnv spec self-validation    |
| GET    | `/schema`   | Action and observation schemas  |
| POST   | `/reset`    | Start a new episode             |
| POST   | `/step`     | Submit a SQL fix action         |
| POST   | `/mcp`      | MCP-compatible tool interface   |
| GET    | `/baseline` | Run baseline agent on all tasks |

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

| Field      | Type   | Required | Options                     |
| ---------- | ------ | -------- | --------------------------- |
| type       | string | ✅       | run_sql, fix_query, analyze |
| sql        | string | ✅       | Any valid SELECT query      |
| reasoning  | string | ❌       | Agent's explanation         |
| session_id | string | ❌       | Isolate concurrent sessions |

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
  "done": false,
  "session_id": "abc-123"
}
```

---

## 🏆 Reward Structure

| Condition                      | Value         |
| ------------------------------ | ------------- |
| Correctness (0–100%)           | 0.0 – 1.0     |
| Efficiency bonus (fewer steps) | up to +0.10   |
| Regression penalty (got worse) | up to -0.10   |
| Empty query penalty            | up to -0.10   |
| Max possible score             | 1.00 (capped) |

---

## 📊 Baseline Scores

Tested with `llama-3.3-70b-versatile` via Groq API:

| Task   | Score | Status     |
| ------ | ----- | ---------- |
| Easy   | 1.00  | ✅ Perfect |
| Medium | 1.00  | ✅ Perfect |
| Hard   | 1.00  | ✅ Perfect |

Run your own baseline:

```bash
# Using Groq (free)
GROQ_API_KEY=your_key python baseline/run_baseline.py

# Using OpenAI
OPENAI_API_KEY=your_key python baseline/run_baseline.py

# Using Meta eval format
HF_TOKEN=your_key API_BASE_URL=https://router.huggingface.co/v1 MODEL_NAME=Qwen/Qwen2.5-72B-Instruct python inference.py
```

---

## 🗂️ Project Structure

```
sql-debug-env/
├── main.py                  # FastAPI app + all endpoints
├── environment.py           # Core RL environment logic
├── grader.py                # Episode scoring
├── models.py                # Pydantic models
├── inference.py             # Meta eval inference script ([START]/[STEP]/[END])
├── pyproject.toml           # Project metadata + openenv spec
├── openenv.yaml             # OpenEnv environment manifest
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container definition
├── baseline/
│   └── run_baseline.py      # Baseline agent (LLM-powered)
├── tasks/
│   ├── task_easy.py         # Syntax error task (employees.db)
│   ├── task_medium.py       # JOIN logic task (ecommerce.db)
│   └── task_hard.py         # 9 randomised hard scenarios (analytics.db)
├── databases/
│   ├── employees.db         # 7 employee records
│   ├── ecommerce.db         # ecommerce schema
│   └── analytics.db         # 100k+ sales rows
└── server/
    └── app.py               # Server entry point
```

---

## 🔧 Environment Variables

| Variable         | Description                    | Used By                  |
| ---------------- | ------------------------------ | ------------------------ |
| `HF_TOKEN`       | Hugging Face / API key         | inference.py             |
| `API_BASE_URL`   | LLM API endpoint               | inference.py             |
| `MODEL_NAME`     | Model identifier for inference | inference.py             |
| `GROQ_API_KEY`   | Groq API key (free tier)       | baseline/run_baseline.py |
| `OPENAI_API_KEY` | OpenAI API key (fallback)      | baseline/run_baseline.py |
| `SERVER_URL`     | Environment server URL         | baseline/run_baseline.py |

---

## 🔌 MCP Support

This environment supports the **Model Context Protocol (MCP)** via the `/mcp` endpoint, allowing direct integration with MCP-compatible AI agent frameworks:

```json
POST /mcp
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "reset",
    "arguments": { "task_id": "hard", "session_id": "my-session" }
  }
}
```

---

## 👥 Authors

Built by **Aarush, Chetanya & Aryan** for the OpenEnv Hackathon by Meta × Hugging Face × Scalar School of Technology.
