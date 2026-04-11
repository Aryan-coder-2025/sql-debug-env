import os
from fastapi import APIRouter, HTTPException, Request
from routers.state import sessions, multi_sessions
from environment import get_metrics
from multi_step_env import MultiStepSQLEnv

try:
    from dynamic_schema import DynamicSQLEnv
    HAS_DYNAMIC = True
except ImportError:
    HAS_DYNAMIC = False

try:
    from adversarial_generator import GeneticAdversary, AdversarialSQLEnv
    HAS_ADVERSARIAL = True
except ImportError:
    HAS_ADVERSARIAL = False

router = APIRouter()

@router.get("/metrics")
def metrics():
    return get_metrics()

@router.get("/trajectories")
def trajectories():
    import glob
    traj_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "trajectories"
    )
    if not os.path.exists(traj_dir):
        return {"trajectories": [], "count": 0}
    files = glob.glob(os.path.join(traj_dir, "trajectory_*.json"))
    return {
        "trajectories": [os.path.basename(f) for f in sorted(files)[-50:]],
        "count": len(files),
        "directory": traj_dir,
    }

@router.get("/trajectory/{episode_id}")
def get_trajectory(episode_id: str):
    import json as _json
    traj_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "trajectories"
    )
    filepath = os.path.join(traj_dir, f"trajectory_{episode_id}.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Trajectory not found: {episode_id}")
    try:
        with open(filepath, "r") as f:
            return _json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/challenge")
async def generate_adversarial_challenge(request: Request):
    if not HAS_ADVERSARIAL or not HAS_DYNAMIC:
        raise HTTPException(status_code=501, detail="Adversarial or dynamic modules not available")
    try:
        try:
            body = await request.json()
            session_id = body.get("session_id")
        except Exception:
            session_id = None
        sid = session_id or "default"
        
        from hybrid_agent import HybridAgent
        dummy_agent = HybridAgent("mock", use_rl_finetune=False)
        generator = GeneticAdversary(agent=dummy_agent, population_size=1)
        mutant_tasks = generator.generate_seed_population()
        mutant_task = mutant_tasks[0]

        adv_env = AdversarialSQLEnv(malicious_task=mutant_task)
        obs = adv_env.reset(task_id="adversarial_seed")

        sessions[sid] = adv_env
        multi_sessions[sid] = MultiStepSQLEnv(adv_env)
        multi_sessions[sid].reset(task_id="adversarial_seed")

        result = obs.model_dump()
        result["mode"] = "adversarial"
        result["note"] = "This is an adversarially mutated query designed to trick debugging agents."
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/leaderboard")
def leaderboard():
    import glob
    import json as _json
    traj_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "trajectories"
    )
    if not os.path.exists(traj_dir):
        return {"entries": [], "summary": {"total_episodes": 0}}
    files = glob.glob(os.path.join(traj_dir, "trajectory_*.json"))
    task_stats = {}
    for fpath in files:
        try:
            with open(fpath, "r") as f:
                data = _json.load(f)
            tid = data.get("task_id", "unknown")
            if tid not in task_stats:
                task_stats[tid] = {"scores": [], "steps": [], "count": 0, "successes": 0}
            stats = task_stats[tid]
            stats["count"] += 1
            stats["steps"].append(data.get("total_steps", 0))
            best_c = 0.0
            for step in data.get("history", []):
                c = float(step.get("reward", {}).get("correctness", 0.0))
                if c > best_c:
                    best_c = c
            stats["scores"].append(best_c)
            if best_c >= 1.0:
                stats["successes"] += 1
        except Exception:
            continue
    entries = []
    for tid, stats in sorted(task_stats.items()):
        avg_score = sum(stats["scores"]) / max(1, len(stats["scores"]))
        avg_steps = sum(stats["steps"]) / max(1, len(stats["steps"]))
        entries.append({
            "task_id": tid,
            "episodes": stats["count"],
            "successes": stats["successes"],
            "success_rate": round(stats["successes"] / max(1, stats["count"]), 4),
            "avg_correctness": round(avg_score, 4),
            "avg_steps": round(avg_steps, 2),
        })
    total_eps = sum(e["episodes"] for e in entries)
    total_success = sum(e["successes"] for e in entries)
    return {
        "entries": entries,
        "summary": {
            "total_episodes": total_eps,
            "total_successes": total_success,
            "overall_success_rate": round(total_success / max(1, total_eps), 4) if total_eps > 0 else 0,
        },
    }
