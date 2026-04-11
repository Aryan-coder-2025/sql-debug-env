"""
multi_step_env.py — Multi-Step Debugging Session & State Tracking

This module wraps the base `SQLDebugEnv` (or `DynamicSQLEnv`) to add 
multi-turn interactive sessions. It tracks interaction history, computes 
sparse progressive rewards for investigation actions (EXPLAIN, DESCRIBE), 
and provides a unified, tokenizable state representation suitable for RL 
Transformer or LSTM policies.
"""

import time
import sqlite3
from typing import Dict, Any, List, Tuple

# Try importing gymnasium first, fallback to older gym
try:
    import gymnasium as gym
    from gymnasium import spaces
    MODERN_GYM = True
except ImportError:
    try:
        import gym
        from gym import spaces
        MODERN_GYM = False
    except ImportError:
        # Provide stubs if no gym is installed
        class _GymStub:
            class Env: pass
        gym = _GymStub()
        class _SpacesStub:
            def Text(self, *args, **kwargs): return None
            def Dict(self, *args, **kwargs): return None
        spaces = _SpacesStub()
        MODERN_GYM = False

from models import SQLAction

class MultiStepSQLEnv(gym.Env):
    """
    A Gym-compatible RL environment wrapper that forces the agent to explore 
    and identify SQL issues interactively over multiple steps in a single session.
    """
    
    def __init__(self, base_env, max_steps: int = 10):
        super().__init__()
        self.base_env = base_env
        self.max_steps = max_steps
        
        self.session_state = {}
        self.history = []
        self.current_step = 0
        self.cumulative_reward = 0.0
        
        # Action space: string commands from the agent.
        self.action_space = spaces.Text(max_length=2000)
        
        # Observation space: structured dict with history context.
        self.observation_space = spaces.Dict({
            "query": spaces.Text(max_length=2000),
            "schema_hint": spaces.Text(max_length=5000),
            "history": spaces.Text(max_length=15000)
        })

    def reset(self, **kwargs) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Initializes a new session. Resets the base environment and clears history.
        """
        # We drop the direct dict return from base_env.reset() and extract the state.
        self.base_env.reset(**kwargs)
        task = self.base_env.current_task
        
        self.current_step = 0
        self.history = []
        self.cumulative_reward = 0.0
        self.session_state = {
            "session_id": getattr(self.base_env, "_episode_id", f"session_{time.time()}"),
            "buggy_query": getattr(task, "broken_query", ""),
            "action_history": self.history,
            "step_count": 0
        }
        
        obs = self._get_observation()
        info = {"session_id": self.session_state["session_id"]}
        
        if MODERN_GYM:
            return obs, info
        return obs

    def step(self, action_str: str):
        """
        Accepts sequential commands:
          - SUBMIT_QUERY <sql>
          - EXPLAIN <sql>
          - DESCRIBE <table_name>
          - SHOW_TABLES
          - GIVE_UP
        """
        if not action_str or not isinstance(action_str, str):
            action_str = "GIVE_UP"  # Default fallback for invalid formats
            
        self.current_step += 1
        reward = 0.0
        done = False
        feedback = ""
        info = {}
        
        # Parse the action command
        parts = action_str.strip().split(" ", 1)
        command = parts[0].upper()
        arg = parts[1].strip() if len(parts) > 1 else ""
        
        # Determine internal DB path for introspective commands
        task = self.base_env.current_task
        db_path = getattr(task, "db_path", None)
        conn = None
        if db_path:
            try:
                # Open read-only to prevent unexpected mutations during reasoning
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            except Exception:
                pass

        # Execute Actions
        try:
            if command == "SHOW_TABLES":
                if conn:
                    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [row[0] for row in cur.fetchall()]
                    feedback = f"Tables: {', '.join(tables)}"
                    reward += 0.1
                else:
                    feedback = "Error: Database connection unavailable."
                    reward -= 0.05
                    
            elif command == "DESCRIBE":
                table_name = arg.strip(";'\"")
                if conn and table_name:
                    try:
                        cur = conn.execute(f"PRAGMA table_info({table_name})")
                        cols = cur.fetchall()
                        if cols:
                            schema_str = ", ".join([f"{c[1]} ({c[2]})" for c in cols])
                            feedback = f"Schema for '{table_name}': {schema_str}"
                            reward += 0.2
                        else:
                            feedback = f"Error: Table '{table_name}' does not exist."
                            reward -= 0.05
                    except Exception as e:
                        feedback = f"DESCRIBE Error: {str(e)}"
                        reward -= 0.05
                else:
                    feedback = "Error: Invalid DESCRIBE usage. Expected: DESCRIBE <table_name>"
                    reward -= 0.05
                    
            elif command == "EXPLAIN":
                if conn and arg:
                    try:
                        cur = conn.execute(f"EXPLAIN QUERY PLAN {arg}")
                        plan = cur.fetchall()
                        plan_str = "\n".join([str(p) for p in plan])
                        feedback = f"Query Plan:\n{plan_str}"
                        reward += 0.1
                    except Exception as e:
                        feedback = f"EXPLAIN Error: {str(e)}"
                        reward -= 0.05
                else:
                    feedback = "Error: Invalid EXPLAIN usage. Expected: EXPLAIN <sql_query>"
                    reward -= 0.05
                    
            elif command == "SUBMIT_QUERY":
                if not arg:
                    feedback = "Error: Empty query submission."
                    reward -= 0.05
                else:
                    # Relay to base environment logic
                    action_obj = SQLAction(type="run_sql", sql=arg)
                    base_obs = self.base_env.step(action_obj)
                    
                    # Extract grading markers from the OpenEnv observation format
                    err = getattr(base_obs, 'error_message', None)
                    metadata = getattr(base_obs, 'metadata', {})
                    correctness = metadata.get("correctness", 0.0) if metadata else 0.0
                    
                    if correctness >= 1.0:
                        # --- Nuanced reward: never exactly 0.0 or 1.0 ---
                        # Base correctness component (max 0.60)
                        correctness_reward = 0.60
                        
                        # Exploration bonus (max 0.20): reward agents that investigated first
                        exploration_actions = sum(
                            1 for act, _, _ in self.history
                            if act.strip().upper().startswith(("EXPLAIN", "DESCRIBE", "SHOW_TABLES"))
                        )
                        exploration_bonus = min(0.20, exploration_actions * 0.05)
                        
                        # Efficiency bonus (max 0.15): reward solving in fewer steps
                        steps_used = self.current_step
                        efficiency_bonus = max(0.0, (self.max_steps - steps_used) / self.max_steps) * 0.15
                        
                        # Final reward: fractional, clamped to [0.05, 0.95]
                        reward += round(min(0.95, max(0.05, correctness_reward + exploration_bonus + efficiency_bonus)), 4)
                        done = True
                        feedback = (f"Success! The query produces the correct result set. "
                                    f"(Reward breakdown: correctness={correctness_reward}, "
                                    f"exploration={round(exploration_bonus, 4)}, "
                                    f"efficiency={round(efficiency_bonus, 4)})")
                    else:
                        if err:
                            feedback = f"SQL Error: {err}"
                            reward -= 0.05
                        else:
                            # Partial credit for close attempts
                            partial = round(correctness * 0.4, 4)
                            reward += partial
                            feedback = ("Query executed successfully but results are incorrect. "
                                        f"Correctness score: {correctness}, partial reward: +{partial}")
                            
            elif command == "GIVE_UP":
                feedback = "Session aborted by agent."
                reward -= 0.5
                done = True
                
            else:
                feedback = f"Error: Unknown action command '{command}'."
                reward -= 0.05
                
        finally:
            if conn:
                conn.close()
                

        # Track history & check bounds
        timestamp = time.time()
        self.history.append((action_str, feedback, timestamp))
        self.session_state["step_count"] = self.current_step
        
        # Max steps timeout
        if not done and self.current_step >= self.max_steps:
            done = True
            reward -= 1.0
            feedback += "\n[Timeout: Maximum steps reached without a successful fix]"

        obs = self._get_observation()
        
        info["step_count"] = self.current_step
        info["action"] = action_str
        info["reward"] = reward
        info["feedback"] = feedback
        self.cumulative_reward = round(self.cumulative_reward + reward, 4)

        if MODERN_GYM:
            truncated = (self.current_step >= self.max_steps and not done)
            if truncated: done = True
            return obs, reward, done, truncated, info
        
        return obs, reward, done, info

    def _get_observation(self) -> Dict[str, Any]:
        """Compile internal state into the standardized observation dictionary."""
        task = self.base_env.current_task
        
        # Build text string of the chronological history
        hist_blocks = []
        for act, fdbk, t in self.history:
            formatted_t = time.strftime('%H:%M:%S', time.gmtime(t))
            hist_blocks.append(f"[{formatted_t}] ACTION: {act}\nFEEDBACK: {fdbk}")
            
        return {
            "query": task.broken_query if task else "",
            "schema_hint": task.schema_sql if task else "",
            "history": "\n\n".join(hist_blocks),
            "history_structured": self.history
        }

    def get_observation_vector(self) -> str:
        """
        Formatting interface compatible with Transformer or LSTM policies 
        which consume raw tokenized blocks.
        """
        obs = self._get_observation()
        
        text_vector = (
            f"=== DEBUGGING SESSION ===\n"
            f"INITIAL BUGGY QUERY:\n{obs['query']}\n\n"
            f"SCHEMA CONTEXT:\n{obs['schema_hint']}\n\n"
            f"SESSION HISTORY:\n{obs['history']}\n"
            f"========================="
        )
        return text_vector


"""
# ============================================================================
# INTEGRATION NOTES 
# ============================================================================

To add multi-turn session tracking in your existing RL training loop:

1. Import the wrapper into your training or evaluation script:
   `from multi_step_env import MultiStepSQLEnv`

2. Wrap your base environment before passing it to your agent:
   
   # OLD
   # from dynamic_schema import DynamicSQLEnv
   # env = DynamicSQLEnv()
   
   # NEW
   from dynamic_schema import DynamicSQLEnv
   from multi_step_env import MultiStepSQLEnv
   
   base_env = DynamicSQLEnv()
   env = MultiStepSQLEnv(base_env, max_steps=15)

3. Update your agent's input generation to use the tokenizable history representation:
   obs = env.reset()
   
   # You can now feed this giant text block (or just obs['history']) into your LLM or RL policy:
   context_str = env.get_observation_vector()

4. Make sure your agent outputs action strings corresponding to the API grammar:
   `env.step("EXPLAIN SELECT * FROM users")`
   `env.step("DESCRIBE users_a1b2")`
   `env.step("SUBMIT_QUERY SELECT ...")`
"""
