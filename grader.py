"""
grader.py — SQL Debug Environment Episode Grader
OpenEnv Hackathon by Meta × Hugging Face × Scaler School of Technology

Grades a completed episode based on:
- Best correctness achieved across all steps (forgiving grading)
- Efficiency bonus for solving in fewer steps
- Regression penalty if the agent's last attempt is worse than its best
- Empty submission penalty

The final score is normalized to [0.0, 1.0].
"""

from typing import Any, Dict, List, Optional


def grade_episode(
    history: List[Dict[str, Any]],
    task: Optional[Any] = None,
) -> Dict[str, Any]:
    """Grade a completed episode and return a detailed score breakdown.

    The grading algorithm rewards correctness first, then efficiency:
    - score = best_correctness + efficiency_bonus - regression_penalty - empty_penalty
    - Clamped to [0.0, 1.0]

    Args:
        history: List of step records, each containing 'action' and 'reward' dicts.
        task: Optional TaskInfo for context (currently unused, reserved for LLM grading).

    Returns:
        Dictionary with score breakdown including:
        - score: Final normalized score in [0.0, 1.0]
        - correctness: Best correctness achieved
        - total_steps: Number of steps taken
        - efficiency_bonus: Bonus for solving quickly
        - regression_penalty: Penalty for regressing
        - empty_penalty: Penalty for empty submissions
    """
    # Edge case: no history
    if not history:
        return {
            "score": 0.0,
            "correctness": 0.0,
            "total_steps": 0,
            "efficiency_bonus": 0.0,
            "reason": "No steps taken",
        }

    try:
        total_steps = len(history)
        max_steps = 10

        # Count empty SQL submissions
        empty_submissions = sum(
            1 for step in history
            if not step.get("action", {}).get("sql", "").strip()
        )

        # Extract correctness from each step's reward data
        all_correctness = []
        for step in history:
            reward_data = step.get("reward", {})
            c = float(reward_data.get("correctness", 0.0))
            all_correctness.append(c)

        best_correctness = max(all_correctness) if all_correctness else 0.0
        last_correctness = all_correctness[-1] if all_correctness else 0.0

        # Use best correctness (fair — agent shouldn't be punished for exploring)
        correctness = max(0.0, min(1.0, best_correctness))

        # Regression penalty: if agent's last attempt is worse than its best
        regression_penalty = 0.0
        if last_correctness < best_correctness:
            regression_penalty = round((best_correctness - last_correctness) * 0.1, 4)

        # Efficiency bonus: reward solving in fewer steps (max 10%)
        efficiency_bonus = max(0.0, (max_steps - total_steps) / max_steps) * 0.1
        efficiency_bonus = round(efficiency_bonus, 4)

        # Empty query penalty: penalize wasted steps
        empty_penalty = round(min(0.1, empty_submissions * 0.02), 4)

        # Final score = correctness + efficiency - penalties, clamped to [0, 1]
        final_score = correctness + efficiency_bonus - regression_penalty - empty_penalty
        final_score = round(max(0.0, min(1.0, final_score)), 4)

        return {
            "score": final_score,
            "correctness": round(correctness, 4),
            "best_correctness": round(best_correctness, 4),
            "last_correctness": round(last_correctness, 4),
            "total_steps": total_steps,
            "efficiency_bonus": efficiency_bonus,
            "regression_penalty": regression_penalty,
            "empty_penalty": empty_penalty,
            "empty_submissions": empty_submissions,
            "reason": "graded ok",
        }

    except Exception as e:
        return {
            "score": 0.0,
            "correctness": 0.0,
            "total_steps": len(history),
            "efficiency_bonus": 0.0,
            "reason": f"grader error: {str(e)}",
        }