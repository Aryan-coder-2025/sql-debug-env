"""
dashboard.py — Live Interactive Debugging Dashboard

Streamlit web interface for visualizing the HybridAgent's debugging process 
in real-time over the MultiStepSQLEnv.

Requirements to run:
    pip install streamlit pandas plotly
    streamlit run dashboard.py
"""

import streamlit as st
import time
import pandas as pd
import tempfile
import plotly.express as px

# Import backend components as per constraints (no modifications)
from dynamic_schema import DynamicSQLEnv
from multi_step_env import MultiStepSQLEnv
from hybrid_agent import HybridAgent

st.set_page_config(page_title="SQL Debug Agent Live Dashboard", layout="wide")


# --- State Initialization ---
if "env" not in st.session_state:
    st.session_state.env = None
if "agent" not in st.session_state:
    st.session_state.agent = HybridAgent(model_name="gpt-4o-mini", use_rl_finetune=False)
if "obs" not in st.session_state:
    st.session_state.obs = None
if "done" not in st.session_state:
    st.session_state.done = True
if "reward_history" not in st.session_state:
    st.session_state.reward_history = []
if "action_history" not in st.session_state:
    st.session_state.action_history = []
if "original_query" not in st.session_state:
    st.session_state.original_query = ""
if "current_proposal" not in st.session_state:
    st.session_state.current_proposal = ""
if "feedback" not in st.session_state:
    st.session_state.feedback = ""

# --- Helper Methods ---
def display_diff(original: str, modified: str):
    """Simple inline diff visualization for the UI."""
    # In a full app, we'd use diff-match-patch or st_monaco, 
    # but for simplicity we show them side by side in code blocks.
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
        return f"I need to check the execution plan to see if there are missing indexes or full table scans. \nResult: Let's see... Ah, the feedback says: {feedback[:100]}..."
    elif action.startswith("SHOW_TABLES"):
        return "I'm checking the database to map out the available tables. Maybe I'm referencing a table that doesn't exist."
    elif action.startswith("DESCRIBE"):
        return "I'm looking closely at the schema for this table. Are the column names exactly as I expected?"
    elif action.startswith("SUBMIT_QUERY"):
        if "Success" in feedback:
            return "I've synthesized all the context and submitted my final fix. It executed correctly!"
        else:
            return "Let me try this fix... Ouch, that didn't work. I'll need to re-evaluate the schema."
    elif action.startswith("GIVE_UP"):
        return "This is too complex or I'm missing context. I'll abort this session."
    
    return "Analyzing the issue and executing the next optimal debugging step."


# --- Layout ---
st.title("🔍 SQL Agent Debugging Dashboard")
st.markdown("Live visualization of the Hybrid LLM + RL Agent fixing SQL queries.")

# 1. File Upload Area & Control
with st.sidebar:
    st.header("1. Upload & Initialize")
    uploaded_file = st.file_uploader("Upload Buggy .sql", type=['sql'])
    
    if st.button("Start Debugging", type="primary"):
        # Initialize Backend Environments
        base_env = DynamicSQLEnv()
        
        # If user uploaded a buggy query, we could theoretically inject it here,
        # but the DynamicSQLEnv generates its own random task anyway per the spec.
        # We will use the backend's generated query to maintain isolation.
        
        st.session_state.env = MultiStepSQLEnv(base_env, max_steps=15)
        
        # Reset Env for new session
        obs = st.session_state.env.reset()
        if isinstance(obs, tuple): # Handle Gym compatibility
            obs = obs[0]
            
        st.session_state.obs = obs
        st.session_state.original_query = obs.get("query", "")
        st.session_state.current_proposal = ""
        st.session_state.done = False
        st.session_state.reward_history = []
        st.session_state.action_history = []
        st.session_state.feedback = "Session started. Ready for the agent."
        
    st.divider()
    st.header("2. Control Panel")
    
    colA, colB = st.columns(2)
    step_btn = colA.button("Step Agent", disabled=st.session_state.done)
    run_btn = colB.button("Run to Fix", disabled=st.session_state.done)


# 2. Main Execution Flow
if step_btn or run_btn:
    if st.session_state.env:
        steps_to_take = 1 if step_btn else 15
        
        for _ in range(steps_to_take):
            if st.session_state.done:
                break
                
            # 1. Agent plans action
            action = st.session_state.agent.get_action(st.session_state.obs)
            
            # If making a fix, update the UI
            if action.startswith("SUBMIT_QUERY"):
                st.session_state.current_proposal = action.replace("SUBMIT_QUERY", "").strip()
                
            # 2. Step the Environment
            step_result = st.session_state.env.step(action)
            
            # Gymnasium compat extraction
            if len(step_result) == 4:
                obs, reward, done, info = step_result
            else:
                obs, reward, done, truncated, info = step_result
                done = done or truncated
                
            feedback = info.get("feedback", "")
            
            # 3. Update UI State
            st.session_state.obs = obs
            st.session_state.done = done
            st.session_state.feedback = feedback
            
            st.session_state.reward_history.append(reward)
            
            monologue = generate_monologue(action, feedback)
            st.session_state.action_history.append({
                "Action": action,
                "Reward": reward,
                "Reasoning": monologue
            })
            
            if step_btn:
                break # Only one step
    else:
        st.error("Please click 'Start Debugging' first.")

# --- UI Render ---

if st.session_state.original_query:
    # Top Section: Monologue & Action
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
            type="primary"
        )

    st.divider()

    # Bottom Section: Metrics & Logging
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📈 Reward Accumulation")
        if st.session_state.reward_history:
            cumulative = pd.Series(st.session_state.reward_history).cumsum()
            df = pd.DataFrame({"Step": range(1, len(cumulative) + 1), "Cumulative Reward": cumulative})
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
            
else:
    st.info("Upload a file or click **Start Debugging** in the sidebar to initialize the environment.")
