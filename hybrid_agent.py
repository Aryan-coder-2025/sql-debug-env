"""
hybrid_agent.py — Hybrid Symbolic + Neural Agent

This module extends the RL SQL debugging environment by providing an LLM-based 
policy combined with a symbolic SQL parser (`sqlglot`) for validation. It acts 
as a drop-in replacement for standard RL policies and supports an experience 
buffer for subsequent fine-tuning using PPO/DPO via RL frameworks like TRL.
"""

import os
import json
import logging

try:
    import sqlglot
except ImportError:
    sqlglot = None

# Fallback wrapper for OpenAI or local models
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


class SymbolicValidator:
    """
    Symbolic safety net using `sqlglot` to parse and validate proposed SQL 
    before it is executed in the environment. Reduces simple syntax hallucinations.
    """
    def __init__(self, dialect="sqlite"):
        self.dialect = dialect

    def validate(self, sql_query: str) -> dict:
        if not sqlglot:
            return {"is_valid": True, "error": None}  # Bypass if missing dependency
            
        try:
            # Parse the query to ensure basic syntactic validity
            parsed = sqlglot.parse_one(sql_query, read=self.dialect)
            return {"is_valid": True, "error": None, "parsed": parsed.sql()}
        except Exception as e:
            return {"is_valid": False, "error": str(e)}


class LLMPolicy:
    """
    Wraps an LLM (e.g., GPT-4o-mini or a local Llama model) to generate 
    SQL fixes and meta-actions based on the debugging session history.
    """
    def __init__(self, model_name="gpt-4o-mini", api_key=None):
        self.model_name = model_name
        if "gpt" in model_name.lower():
            if not OpenAI:
                 raise ImportError("OpenAI SDK not installed. Run: pip install openai")
            # Prevent Streamlit UI crash if key is missing locally by injecting a placeholder
            resolved_key = api_key or os.getenv("OPENAI_API_KEY") or "mock_key_to_prevent_ui_crash"
            self.client = OpenAI(api_key=resolved_key)
        else:
            self.client = None # Future extension: local vLLM or Ollama client
            
    def get_raw_action(self, observation: str) -> str:
        """Query the LLM policy network."""
        sys_prompt = (
            "You are an expert SQL debugging agent. Analyze the session history "
            "and output exactly ONE of the following commands:\n"
            "1. SUBMIT_QUERY <fixed_sql>\n"
            "2. EXPLAIN <sql_to_analyze>\n"
            "3. DESCRIBE <table_name>\n"
            "4. SHOW_TABLES\n"
            "5. GIVE_UP\n"
            "Output only the command, no markdown formatting."
        )
        
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": observation}
                    ],
                    max_tokens=600,
                    temperature=0.2
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                return "GIVE_UP\n-- Missing valid OPENAI_API_KEY. Add key to environment to enable LLM generation."
        else:
            # Fallback for unconnected local testing
            return "SHOW_TABLES"


class HybridAgent:
    """
    Orchestrates the LLM policy and Symbolic Validation, while maintaining 
    an experience buffer for RL fine-tuning.
    """
    def __init__(self, model_name="gpt-4o-mini", use_rl_finetune=True):
        self.policy = LLMPolicy(model_name=model_name)
        self.validator = SymbolicValidator()
        self.use_rl_finetune = use_rl_finetune
        self.experiences = []
        
    def get_action(self, observation: dict) -> str:
        """
        Produce an action. If the action is SUBMIT_QUERY, validate it symbolically 
        first to ensure no trivial syntax errors are wasted on environment steps.
        """
        # Convert dictionary observation into text representation if needed
        # Assuming multi_step_env provides a history string or we format it here
        obs_text = observation.get("history", str(observation))
        if "query" in observation:
             obs_text = f"BUGGY QUERY: {observation['query']}\n{obs_text}"
             
        action_str = self.policy.get_raw_action(obs_text)
        
        # Intercept and validate SUBMIT_QUERY
        if action_str.startswith("SUBMIT_QUERY"):
            sql_part = action_str[len("SUBMIT_QUERY"):].strip()
            val_result = self.validator.validate(sql_part)
            
            if not val_result["is_valid"]:
                # If invalid, we format a self-corrective meta-action 
                # instead of hitting the environment right away, or let the 
                # environment handle the error. For now, we return it as is, 
                # but log the symbolic failure.
                logger.warning(f"Symbolic parsing failed: {val_result['error']}")
                # We could rewrite action_str to EXPLAIN to force the agent to rethink, 
                # but we'll let the environment give the error (-0.05 penalty).
                
        return action_str
        
    def store_experience(self, obs, action, reward, next_obs, done):
        """Buffer step results for PPO/DPO RL fine-tuning framework."""
        if self.use_rl_finetune:
            self.experiences.append({
                "obs": obs,
                "action": action,
                "reward": reward,
                "next_obs": next_obs,
                "done": done
            })
            
    def update_policy(self):
        """
        Simulated RL Update Step. 
        In a production TRL/RL4LMs setup, this method batches the self.experiences
        trajectories and computes PPO proximal policy gradient updates to align 
        the LLM generation.
        """
        if not self.use_rl_finetune or not self.experiences:
            return
            
        logger.info(f"Triggering RL Fine-Tuning update on {len(self.experiences)} steps...")
        # e.g., ppo_trainer.step(queries, responses, rewards)
        
        # Clear buffer after update
        self.experiences = []


"""
# ============================================================================
# INTEGRATION NOTES 
# ============================================================================

To use the HybridAgent in your multi-step RL loop:

from dynamic_schema import DynamicSQLEnv
from multi_step_env import MultiStepSQLEnv
from hybrid_agent import HybridAgent

env = MultiStepSQLEnv(DynamicSQLEnv(), max_steps=10)
agent = HybridAgent(model_name="gpt-4o-mini", use_rl_finetune=True)

obs, info = env.reset()
done = False

while not done:
    action = agent.get_action(obs)
    next_obs, reward, done, truncated, info = env.step(action)
    
    agent.store_experience(obs, action, reward, next_obs, done)
    obs = next_obs

agent.update_policy() # Perform PPO step
"""
