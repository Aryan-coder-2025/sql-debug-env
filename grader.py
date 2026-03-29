def grade_episode(history, task):
    if not history:
        return {
            "score": 0.0,
            "correctness": 0.0,
            "total_steps": 0,
            "efficiency_bonus": 0.0,
            "reason": "No steps taken",
        }

    try:
        last_step = history[-1]
        reward_data = last_step.get("reward", {})

        correctness = float(reward_data.get("correctness", 0.0))
        correctness = max(0.0, min(1.0, correctness))

        total_steps = len(history)

        max_steps = 10
        efficiency_bonus = max(0.0, (max_steps - total_steps) / max_steps) * 0.1

        final_score = correctness + efficiency_bonus
        final_score = round(min(1.0, final_score), 4)

        return {
            "score": final_score,
            "correctness": round(correctness, 4),
            "total_steps": total_steps,
            "efficiency_bonus": round(efficiency_bonus, 4),
        }

    except Exception as e:
        return {
            "score": 0.0,
            "correctness": 0.0,
            "total_steps": len(history),
            "efficiency_bonus": 0.0,
            "error": str(e),
        }
