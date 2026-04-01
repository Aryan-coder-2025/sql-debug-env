def grade_episode(history, task):
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

        # Edge case: empty SQL submitted
        empty_submissions = sum(
            1 for step in history
            if not step.get("action", {}).get("sql", "").strip()
        )

        # Get best correctness across ALL steps (not just last)
        all_correctness = []
        for step in history:
            reward_data = step.get("reward", {})
            c = float(reward_data.get("correctness", 0.0))
            all_correctness.append(c)

        best_correctness = max(all_correctness) if all_correctness else 0.0
        last_correctness = all_correctness[-1] if all_correctness else 0.0

        # Use best correctness (fair to agent)
        correctness = max(0.0, min(1.0, best_correctness))

        # Wrong order penalty — partial credit not full
        # If last step correctness < best, agent regressed
        regression_penalty = 0.0
        if last_correctness < best_correctness:
            regression_penalty = round((best_correctness - last_correctness) * 0.1, 4)

        # Efficiency bonus — reward solving in fewer steps
        efficiency_bonus = max(0.0, (max_steps - total_steps) / max_steps) * 0.1
        efficiency_bonus = round(efficiency_bonus, 4)

        # Empty query penalty
        empty_penalty = round(min(0.1, empty_submissions * 0.02), 4)

        # Final score
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