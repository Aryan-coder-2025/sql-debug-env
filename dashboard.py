"""
dashboard.py — Live Interactive Debugging Dashboard (Performance Optimized)

Streamlit web interface for visualizing the HybridAgent's debugging process
in real-time over the MultiStepSQLEnv.

=== PERFORMANCE OPTIMIZATIONS ===
1. @st.cache_resource  — caches the HybridAgent (LLM client + validator) across
                          all sessions so the model is never reloaded on rerun.
2. st.session_state    — persists environment, observations, history, and UI
                          flags across Streamlit reruns without recomputation.
3. st.form             — groups the sidebar inputs (file uploader + start button)
                          so that interacting with the file picker does NOT
                          trigger a full script rerun. Only the submit button
                          triggers initialization.
4. Modular functions   — data loading, agent stepping, and UI rendering are
                          separated into isolated functions for clarity.
=====================================================================

Requirements to run:
    pip install streamlit pandas plotly
    streamlit run dashboard.py
"""

import streamlit as st
import time
import pandas as pd
import plotly.express as px

# Import backend components — these files are NOT modified.
from dynamic_schema import DynamicSQLEnv
from multi_step_env import MultiStepSQLEnv
from hybrid_agent import HybridAgent


# ─────────────────────────────────────────────────────────────────────────────
# 1. CACHED RESOURCES
# ─────────────────────────────────────────────────────────────────────────────
# WHY cache_resource (not cache_data)?
# → HybridAgent holds an OpenAI client connection and a SymbolicValidator.
#   These are *mutable connection-like objects* that must persist across
#   reruns and sessions. cache_data would try to serialize/hash them and fail.
#   cache_resource stores the object by reference — perfect for ML models,
#   DB connections, and API clients.
# TTL is omitted intentionally: the agent has no stale-data risk; it's a
#   stateless policy that can be reused indefinitely.
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Loading HybridAgent (LLM + Symbolic Validator)...")
def load_agent() -> HybridAgent:
    """
    Initialize and cache the HybridAgent across all Streamlit sessions.

    This avoids re-instantiating the OpenAI client, re-importing sqlglot,
    and re-resolving API keys on every single widget interaction.
    """
    return HybridAgent(model_name="gpt-4o-mini", use_rl_finetune=False)


# ─────────────────────────────────────────────────────────────────────────────
# 2. SESSION STATE INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────
# HOW session_state is managed:
# → Every key is guarded with `if key not in st.session_state` so that
#   values survive Streamlit's full-script rerun cycle.  On explicit user
#   reset (clicking "Start Debugging") we overwrite only the session-specific
#   keys, leaving the cached agent untouched.
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_STATE = {
    "env":              None,   # MultiStepSQLEnv instance (stateful, per-session)
    "obs":              None,   # Current observation dict from the environment
    "done":             True,   # Whether the current episode is finished
    "reward_history":   [],     # List[float] — per-step rewards
    "action_history":   [],     # List[dict]  — per-step action records
    "original_query":   "",     # The initial buggy SQL from the environment
    "current_proposal": "",     # The agent's latest proposed fix
    "feedback":         "",     # Latest environment feedback string
    "auto_started":     False,  # Guard flag so auto-run fires only once
}


def _init_state():
    """Populate missing session-state keys with defaults (idempotent)."""
    for key, default in _DEFAULT_STATE.items():
        if key not in st.session_state:
            # Use list() for mutable defaults to avoid shared-reference bugs
            st.session_state[key] = list(default) if isinstance(default, list) else default


_init_state()

# Load the cached agent once — subsequent reruns hit the cache instantly.
agent = load_agent()


# ─────────────────────────────────────────────────────────────────────────────
# 3. CORE LOGIC FUNCTIONS  (pure logic, no UI calls)
# ─────────────────────────────────────────────────────────────────────────────

def initialize_session():
    """
    Reset the environment and all session-specific state for a fresh episode.

    The HybridAgent is NOT re-created here — it lives in st.cache_resource.
    Only the per-episode env / history / flags are reset.
    """
    base_env = DynamicSQLEnv()
    st.session_state.env = MultiStepSQLEnv(base_env, max_steps=15)

    obs = st.session_state.env.reset()
    if isinstance(obs, tuple):
        obs = obs[0]

    st.session_state.obs = obs
    st.session_state.original_query = obs.get("query", "")
    st.session_state.current_proposal = ""
    st.session_state.done = False
    st.session_state.reward_history = []
    st.session_state.action_history = []
    st.session_state.feedback = "Session started. Ready for the agent."


def run_agent_loop(max_iterations: int = 15):
    """
    Auto-run the agent for up to *max_iterations* steps or until done.

    Uses the globally cached `agent` — no re-instantiation cost.
    """
    if not st.session_state.env:
        return

    for _ in range(max_iterations):
        if st.session_state.done:
            break
        _execute_one_step()


def _execute_one_step():
    """Execute exactly one agent step and update session state."""
    action = agent.get_action(st.session_state.obs)

    if action.startswith("SUBMIT_QUERY"):
        st.session_state.current_proposal = action.replace("SUBMIT_QUERY", "").strip()

    step_result = st.session_state.env.step(action)

    # Gymnasium compat extraction (4-tuple vs 5-tuple)
    if len(step_result) == 4:
        obs, reward, done, info = step_result
    else:
        obs, reward, done, truncated, info = step_result
        done = done or truncated

    feedback = info.get("feedback", "")

    st.session_state.obs = obs
    st.session_state.done = done
    st.session_state.feedback = feedback
    st.session_state.reward_history.append(reward)

    monologue = generate_monologue(action, feedback)
    st.session_state.action_history.append({
        "Action": action,
        "Reward": reward,
        "Reasoning": monologue,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 4. UI HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def display_diff(original: str, modified: str):
    """Simple inline diff visualization for the UI."""
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Original Buggy Query**")
        st.code(original, language="sql")
    with col2:
        st.markdown("**Current Proposed Fix**")
        if modified.startswith("SUBMIT_QUERY"):
            modified = modified.replace("SUBMIT_QUERY", "").strip()
        st.code(modified if modified else "-- No fix proposed yet --", language="sql")


def generate_monologue(action_str: str, feedback: str) -> str:
    """Heuristic proxy for agent reasoning generation."""
    action = action_str.upper()
    if action.startswith("EXPLAIN"):
        return (f"I need to check the execution plan to see if there are missing indexes "
                f"or full table scans. \nResult: Let's see... Ah, the feedback says: "
                f"{feedback[:100]}...")
    elif action.startswith("SHOW_TABLES"):
        return ("I'm checking the database to map out the available tables. "
                "Maybe I'm referencing a table that doesn't exist.")
    elif action.startswith("DESCRIBE"):
        return ("I'm looking closely at the schema for this table. "
                "Are the column names exactly as I expected?")
    elif action.startswith("SUBMIT_QUERY"):
        if "Success" in feedback:
            return "I've synthesized all the context and submitted my final fix. It executed correctly!"
        else:
            return "Let me try this fix... Ouch, that didn't work. I'll need to re-evaluate the schema."
    elif action.startswith("GIVE_UP"):
        return "This is too complex or I'm missing context. I'll abort this session."

    return "Analyzing the issue and executing the next optimal debugging step."


def render_agent_reasoning():
    """Render the 'Agent Internal Reasoning' container."""
    action_box = st.container(border=True)
    with action_box:
        st.subheader("🤖 Agent Internal Reasoning")
        if st.session_state.action_history:
            last_action = st.session_state.action_history[-1]
            st.info(last_action["Reasoning"], icon="🧠")
            st.caption(f"**Executing Action:** `{last_action['Action']}`")
            st.caption(f"**Environment Feedback:** {st.session_state.feedback}")
        else:
            st.write("Waiting to take the first step...")


def render_metrics():
    """Render the reward chart and session history table."""
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📈 Reward Accumulation")
        if st.session_state.reward_history:
            cumulative = pd.Series(st.session_state.reward_history).cumsum()
            df = pd.DataFrame({
                "Step": range(1, len(cumulative) + 1),
                "Cumulative Reward": cumulative,
            })
            fig = px.line(df, x="Step", y="Cumulative Reward", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No rewards accumulated yet.")

    with col2:
        st.subheader("📜 Session History Log")
        if st.session_state.action_history:
            history_df = pd.DataFrame(st.session_state.action_history)[["Action", "Reward"]]
            st.dataframe(history_df, use_container_width=True)
        else:
            st.write("No steps taken.")


# ─────────────────────────────────────────────────────────────────────────────
# 5. PAGE CONFIG & LAYOUT
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="SQL Debug Agent Live Dashboard", layout="wide")

st.title("🔍 SQL Agent Debugging Dashboard")
st.markdown("Live visualization of the Hybrid LLM + RL Agent fixing SQL queries.")


# ── SIDEBAR ──────────────────────────────────────────────────────────────────

with st.sidebar:
    # -----------------------------------------------------------------------
    # HOW forms improve performance:
    # → Without st.form, every interaction with the file uploader or any
    #   future input widget would trigger a FULL Streamlit script rerun,
    #   re-executing all top-level code.  By wrapping them in a form, the
    #   script only reruns when the user explicitly clicks "Start Debugging".
    #   This eliminates the most common source of unnecessary reloads.
    # -----------------------------------------------------------------------
    st.header("1. Upload & Initialize")

    with st.form("init_form", clear_on_submit=False):
        uploaded_file = st.file_uploader("Upload Buggy .sql", type=["sql"])
        start_submitted = st.form_submit_button("Start Debugging", type="primary")

    if start_submitted:
        initialize_session()
        st.rerun()

    st.divider()
    st.header("2. Control Panel")

    colA, colB = st.columns(2)
    step_btn = colA.button("Step Agent", disabled=st.session_state.done)
    run_btn = colB.button("Run to Fix", disabled=st.session_state.done)


# ── AUTO-START (first load only) ─────────────────────────────────────────────
# Guarded by `auto_started` flag — fires exactly once per browser session.
if not st.session_state.auto_started:
    st.session_state.auto_started = True
    initialize_session()


# ── MAIN EXECUTION FLOW (button handlers) ────────────────────────────────────
if step_btn or run_btn:
    if st.session_state.env:
        steps_to_take = 1 if step_btn else 15
        for _ in range(steps_to_take):
            if st.session_state.done:
                break
            _execute_one_step()
            if step_btn:
                break  # Only one step
    else:
        st.error("Please click 'Start Debugging' first.")


# ── UI RENDER ────────────────────────────────────────────────────────────────
if st.session_state.original_query:
    # Top Section: Monologue & Action
    render_agent_reasoning()

    # Middle Section: Diff Viewer
    st.subheader("📝 Query Evolution")
    display_diff(st.session_state.original_query, st.session_state.current_proposal)

    # Download Button if Done
    if st.session_state.done and st.session_state.current_proposal:
        st.success("Session Complete!")
        st.download_button(
            label="Download Fixed Query",
            data=st.session_state.current_proposal,
            file_name="fixed_query.sql",
            mime="text/sql",
            type="primary",
        )

    st.divider()

    # Bottom Section: Metrics & Logging
    render_metrics()

else:
    st.info("Upload a file or click **Start Debugging** in the sidebar to initialize the environment.")
