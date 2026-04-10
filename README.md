---
title: Openenv
emoji: 🛠️
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# 🛠️ SQL Debug Environment

An OpenEnv-compatible reinforcement learning environment for training AI agents to debug SQL queries — built for the **OpenEnv Hackathon by Meta × Hugging Face × Scaler School of Technology**.

![Live Demo](https://img.shields.io/badge/Live-Demo-blue) ![Python](https://img.shields.io/badge/Python-3.12-green) ![FastAPI](https://img.shields.io/badge/FastAPI-0.135-green) ![OpenEnv](https://img.shields.io/badge/OpenEnv-0.2.3-purple) ![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B)

---

## 🏗️ Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#1e1e2e', 'primaryTextColor': '#cdd6f4', 'primaryBorderColor': '#89b4fa', 'lineColor': '#f38ba8', 'secondaryColor': '#ffb86c', 'tertiaryColor': '#a6e3a1'}}}%%
graph TD
    classDef ui fill:#ff7eb3,stroke:#fff,stroke-width:2px,color:#fff,rx:10px
    classDef agent fill:#7367f0,stroke:#fff,stroke-width:2px,color:#fff,rx:10px
    classDef env fill:#28c76f,stroke:#fff,stroke-width:2px,color:#fff,rx:10px
    classDef db fill:#00cfe8,stroke:#fff,stroke-width:2px,color:#fff,rx:10px
    classDef loop fill:#ea5455,stroke:#fff,stroke-width:2px,color:#fff,rx:10px

    subgraph Frontend["🖥️ Interactive Interfaces"]
        DASH["📊 Live Debug Dashboard<br>(Streamlit UI)"]
    end

    subgraph Agents["🧠 Intelligence Layer"]
        subgraph Hybrid["Hybrid Agent System"]
            LLM["🤖 LLM Policy<br>(GPT/Llama)"]
            SYM["✅ Symbolic Validator<br>(sqlglot)"]
            RL["♻️ RLAIF Fine-Tuning<br>(PPO/DPO)"]
            
            LLM -->|<font color='white'>Propose</font>| SYM
            SYM -->|<font color='white'>Self-Correct</font>| LLM
            RL -.->|<font color='white'>Update</font>| LLM
        end
        
        ADV["👾 Adversarial Mutator<br>(Genetic Algorithm)"]
    end

    subgraph Backend["⚙️ OpenEnv Multi-Step Server"]
        WS(["/ws WebSocket<br>OpenEnv Protocol"])
        HTTP(["REST & MCP API"])
        
        subgraph Environment["RL Sandbox"]
            MSE["🔄 Multi-Step Session<br>(Command History)"]
            SDE["🛡️ SQLDebugEnv<br>(Core Logic)"]
            GRADER["⚖️ Grader<br>(Efficiency + Precision)"]
            
            MSE --> SDE
            SDE --> GRADER
        end
        
        subgraph SchemaData["Dynamic Resources"]
            DS["🎲 Dynamic Schema Gen<br>(Faker Noise)"]
            DB[(SQLite Databases<br>100k+ Rows)]
            
            DS --> DB
        end
    end

    DASH -->|<font color='white'>Visualize</font>| Hybrid
    Hybrid -->|<font color='white'>Actions</font>| WS
    ADV -->|<font color='white'>Inject Bugs</font>| MSE
    WS --> MSE
    HTTP --> SDE
    SDE --> DB
    
    %% Assign Classes
    class DASH ui
    class LLM,SYM,RL agent
    class ADV loop
    class MSE,SDE,GRADER env
    class DS,DB db

    %% Colors and Styling
    style Frontend fill:#191b28,stroke:#ff7eb3,stroke-width:2px,color:#fff
    style Agents fill:#191b28,stroke:#7367f0,stroke-width:2px,color:#fff
    style Backend fill:#191b28,stroke:#28c76f,stroke-width:2px,color:#fff
    style Environment fill:#1e1e2e,stroke:#28c76f,stroke-dasharray: 5 5,color:#fff
    style SchemaData fill:#1e1e2e,stroke:#00cfe8,stroke-dasharray: 5 5,color:#fff
```

---

## 🧠 What This Environment Does

An agent receives a broken SQL query and a database schema. It must fix the query interactively over **multiple steps** via a conversational debug session (`EXPLAIN`, `DESCRIBE`, `SUBMIT_QUERY`), earning rewards based on:

- ✅ **Correctness** — does the output match the expected result?
- ⚡ **Efficiency** — fewer meta-actions = higher reward
- 🎯 **Exploration** — partial credit for utilizing `EXPLAIN` or introspecting the schema
- 🤖 **Self-Correction** — symbolic validation catches hallucinatory queries before they drop reward

The environment supports **4 difficulty levels** + **dynamic schemas** continuously evolved by our genetic Adversarial Generator.

---

## 🚀 Quick Start

### 1. Run the Backend OpenEnv Server Locally

```bash
git clone https://github.com/Aryan-coder-2025/sql-debug-env
cd sql-debug-env
pip install -r requirements.txt
python main.py
```

### 2. View the Live Streamlit Dashboard

In a new terminal to visualize the Hybrid Agent dynamically fixing queries:
```bash
pip install streamlit pandas plotly sqlglot openai faker
streamlit run dashboard.py
```

#### 🖥️ Understanding the Dashboard UI
Once the dashboard opens at `http://localhost:8501`, here is how to use it:
1. **Start Debugging (Upload & Initialize)**: Clicking this generates a brand new randomized SQLite database and creates a synthetic "Buggy Query" for the agent to fix. The loading time is instantaneous.
2. **Agent Internal Reasoning**: Shows the raw thoughts of the LLM before it executes a command.
3. **Session History Log**: Shows the step-by-step history of commands the agent executed (e.g. `EXPLAIN SELECT...` or `DESCRIBE users`) and the exact feedback the environment returned.
4. **Reward Accumulation**: Tracks the agent's reinforcement learning score. The agent gets `+0.1` for analyzing the db, `+1.0` for a correct fix, `-0.05` for syntax errors, and `+/- 0.1` for algorithmic query efficiency (penalized for Table Scans, rewarded for Indexes).
5. **Control Panel**:
    - **Step Agent**: Forces the LLM Agent to take exactly *one* debugging action so you can watch its thought process manually.
    - **Run to Fix**: The LLM Agent will repeatedly take steps automatically in a loop until it finds the correct answer and submits it.

### 3. Run the Genetic Adversarial Generator

Watch a self-improving loop of mutated SQL bugs compete against the LLM Agent:
```bash
python adversarial_generator.py
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `WS` | `/ws` | WebSocket (OpenEnv protocol) |
| `POST` | `/mcp` | Model Context Protocol (JSON-RPC 2.0) |
| `POST` | `/reset` | Start a new episode (`task_id`, `session_id`) |
| `POST` | `/step` | Submit SQL action (`type`, `sql`, `reasoning`) |
| `GET` | `/schema` | Action/Observation JSON schemas |
| `GET` | `/metrics` | Live telemetry (sessions, success rate) |
| `GET` | `/trajectories` | List trajectory replay files |

---

## 🎯 Task Generation

We use two distinct methods to challenge the agents:
1. **Static Task Registry**: 34 handmade scenarios across 3 distinct real-world databases spanning syntax, JOIN logic, subqueries, and strict Security (SQL injections).
2. **Dynamic Generation (`dynamic_schema.py`)**: Uses `Faker` to inject noisy schemas (NULLs, dirty strings in INT fields, duplicates).
3. **Adversarial Muation (`adversarial_generator.py`)**: A Genetic Algorithm rips apart correct queries (dropping conditionals, breaking `ON` statements) explicitly optimizing to defeat the LLM agent.

---

## 📊 Reward Structure

| Action / Signal | Value | Description |
|--------|-------|-------------|
| Final Correct Query | +1.00 | Exact output state match |
| Use `DESCRIBE <table>` | +0.20 | Positive reward for inspecting schemas involved |
| Use `EXPLAIN <sql>` | +0.10 | Positive reward for investigating query plans |
| SQL Execution Error | -0.05 | Query failed or was hallucinated |
| Late steps | -1.00 | Penalty after hitting max steps (Timeout) |

---

## 🔌 OpenEnv Framework Integration

This environment fully integrates with the [OpenEnv](https://github.com/meta-pytorch/OpenEnv) framework:

- ✅ `Environment` base class from `openenv-core`
- ✅ `HTTPEnvServer` for WebSocket + MCP transport
- ✅ Typed `Action`, `Observation`, `State` models
- ✅ Concurrent session support (50 max)

---

## 📁 Project Structure

```text
sql-debug-env/
├── backend_core/
│   ├── main.py                # FastAPI Server + REST + WS Endpoints
│   ├── environment.py         # SQLDebugEnv (Environment base)
│   ├── models.py              # OpenEnv Pydantic types
│   ├── grader.py              # Evaluation (Correctness vs Efficiency)
│   ├── openenv.yaml           # OpenEnv manifest
│   └── client.py              # EnvClient SDK
│
├── frontend_ui/
│   └── dashboard.py           # 📊 Live Streamlit Debugging UI
│
├── agent_intelligence/
│   ├── hybrid_agent.py        # 🤖 LLM Policy + Symbolic Validator (sqlglot)
│   ├── adversarial_generator.py # 👾 Genetic Mutator to craft difficult SQL bugs
│   ├── multi_step_env.py      # 🔄 Gym wrapper tracking session history & sparse rewards
│   └── dynamic_schema.py      # 🎲 Noisy Data / Schema Generator (Faker)
│
├── tasks/
│   └── task_{level}.py        # Baseline static tasks (Easy, Med, Hard, Security)
└── outputs/
    └── trajectories/          # Auto-saved chronological replay logs (JSON)
```

---

## 👥 Team

- **Aarush** — Core environment & API
- **Chetanya** — Task design & grading
- **Aryan** — Deployment & baseline agent

Built for the **OpenEnv Hackathon** by Meta × Hugging Face × Scaler School of Technology.

---

## 📜 License

MIT License
