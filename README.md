# SQL Debug Environment

A reinforcement learning environment for training agents to debug SQL queries, built on the OpenEnv standard.

## What This Environment Does

The agent receives a broken SQL query and a database schema. It must fix the query through a series of actions. The environment rewards correctness, efficiency, and speed.

## Action Space

Each action is a JSON object with these fields:

- `type` (required): one of `run_sql`, `fix_query`, `analyze`
- `sql` (optional): the SQL query string
- `reasoning` (optional): agent's reasoning text

## Observation Space

Each observation returns:

- `task_id`: current task identifier
- `broken_query`: the SQL query to fix
- `db_schema`: the database schema
- `query_result`: result of last executed SQL
- `error_message`: error if query failed
- `step_count`: steps taken so far
- `done`: whether episode is complete

## Tasks

| Task | Difficulty | Description |
|------|------------|-------------|
| easy | Easy | Syntax repair — fix a broken SELECT query |
| medium | Medium | Join logic fix — fix incorrect table joins |
| hard | Hard | Performance optimization — fix slow queries |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/reset` | Start a new episode |
| POST | `/step` | Take an action |
| GET | `/state` | Get current state |
| GET | `/tasks` | List all tasks |
| GET | `/grader` | Get episode score |
| GET | `/health` | Health check |
| GET | `/baseline` | Run baseline agent |

## Setup Instructions

### Requirements
- Python 3.12
- Docker

### Run Locally
```bash
git clone https://github.com/Aryan-coder-2025/sql-debug-env
cd sql-debug-env
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 7860
```

### Run with Docker
```bash
docker build -t sql-debug-env .
docker run -p 7860:7860 sql-debug-env
```

### Live API
https://aryan-coder-25-openenv.hf.space

## Baseline Scores

| Task | GPT-4o-mini Score |
|------|-------------------|
| Easy | ~0.90 |
| Medium | ~0.60 |
| Hard | ~0.30 |

