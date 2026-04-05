"""
stress_test.py  —  SQL Debug Env full stress test
Run: python stress_test.py
Requires: pip install httpx rich psutil
Server must be running at http://localhost:7860
"""

import httpx
import asyncio
import time
import os
import sys
from rich.console import Console
from rich.table import Table

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

BASE = "http://localhost:7860"
CONCURRENCY = 10
RAPID_FIRE_ROUNDS = 50

console = Console()

# ─── Helpers ────────────────────────────────────────────────────────────────


def section(title: str):
    console.rule(f"[bold cyan]{title}[/bold cyan]")


def ok(msg):
    console.print(f"  [green]✓[/green] {msg}")


def fail(msg):
    console.print(f"  [red]✗[/red] {msg}")


def warn(msg):
    console.print(f"  [yellow]⚠[/yellow] {msg}")


results = {"passed": 0, "failed": 0, "warned": 0}


def check(condition: bool, label: str, detail: str = ""):
    if condition:
        ok(label)
        results["passed"] += 1
    else:
        fail(f"{label}  {detail}")
        results["failed"] += 1


def reset(task_id: str) -> httpx.Response:
    """Reset with up to 3 retries on db-locked 500."""
    for wait in [0, 2, 4]:
        if wait:
            time.sleep(wait)
        r = httpx.post(f"{BASE}/reset", json={"task_id": task_id}, timeout=30)
        if r.status_code != 500 or "locked" not in r.text:
            return r
    return r


def step(sql: str, action_type: str = "fix_query") -> httpx.Response:
    return httpx.post(
        f"{BASE}/step",
        json={
            "type": action_type,
            "sql": sql,
        },
        timeout=30,
    )


def get_correctness(r: httpx.Response) -> float:
    body = r.json()
    reward = body.get("reward", {})
    if isinstance(reward, dict):
        return float(reward.get("correctness", -1))
    return float(reward)


def _extract_broken_query(d: dict) -> str:
    candidates = ("broken_query", "query", "sql", "broken_sql")
    for k in candidates:
        v = d.get(k)
        if v and isinstance(v, str):
            return v
    for wrapper in ("state", "observation", "data", "task"):
        sub = d.get(wrapper)
        if isinstance(sub, dict):
            for k in candidates:
                v = sub.get(k)
                if v and isinstance(v, str):
                    return v
    return ""


def _get_server_pid() -> int | None:
    """Find the PID of the process listening on port 7860. Works on Windows & Linux."""
    # Method 1: psutil net_connections (works on Linux/Mac)
    if HAS_PSUTIL:
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr.port == 7860 and conn.status == "LISTEN":
                    return conn.pid
        except Exception:
            pass

    # Method 2: netstat fallback (works on Windows)
    try:
        import subprocess

        out = subprocess.check_output(
            ["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            if ":7860" in line and "LISTENING" in line:
                pid = int(line.strip().split()[-1])
                return pid
    except Exception:
        pass

    return None


# ─── 1. GRADER / REWARD CORRECTNESS ─────────────────────────────────────────


def test_grader_correctness():
    section("1 · Grader / Reward Correctness")

    # Use pinned broken queries that are GUARANTEED to score < 1.0.
    # These are hardcoded so random scenario selection can never produce a false pass.
    PINNED_BROKEN = {
        "easy": (
            "easy",
            # FORM instead of FROM — always a syntax error, always scores 0
            "SELECT name, salary FORM employees WHERE department = 'Engineering' ORDER BY name",
        ),
        "medium": (
            "medium",
            # INNER JOIN — drops customers with no orders, always differs from LEFT JOIN result
            """SELECT
    c.name AS customer_name,
    COUNT(o.id) AS total_orders,
    COALESCE(SUM(oi.amount), 0) AS total_spent
FROM customers c
INNER JOIN orders o ON c.id = o.customer_id
INNER JOIN order_items oi ON o.id = oi.order_id
GROUP BY c.id, c.name
ORDER BY c.name""",
        ),
        "hard": (
            "hard",
            # WHERE instead of HAVING — SQL error, always scores 0
            """SELECT p.name, SUM(s.amount) AS total
FROM products p
JOIN sales s ON p.id = s.product_id
WHERE COUNT(s.id) > 5
GROUP BY p.id, p.name
ORDER BY p.name""",
        ),
    }

    for diff in ["easy", "medium", "hard"]:

        task_id, broken_query = PINNED_BROKEN[diff]

        r = reset(task_id)
        if r.status_code != 200:
            fail(f"[{diff}] /reset → {r.status_code}  {r.text[:200]}")
            results["failed"] += 1
            continue

        console.print(f"  [dim][{diff}] broken_query: {broken_query[:70]}[/dim]")
        correctness = -1.0

        # ── pinned broken query → correctness < 1.0 ──
        r2 = step(broken_query)
        if r2.status_code == 200:
            correctness = get_correctness(r2)
            check(
                correctness < 1.0,
                f"[{diff}] broken query → correctness < 1.0",
                f"got {correctness}",
            )
        else:
            fail(f"[{diff}] /step(broken) → {r2.status_code}  {r2.text[:200]}")
            results["failed"] += 1

        # ── SELECT 1 → correctness = 0.0 ──
        reset(diff)
        r3 = step("SELECT 1")
        if r3.status_code == 200:
            correctness = get_correctness(r3)
            check(
                correctness == 0.0,
                f"[{diff}] 'SELECT 1' → correctness=0.0",
                f"got {correctness}",
            )
        else:
            warn(f"[{diff}] /step(SELECT 1) → {r3.status_code}  {r3.text[:200]}")
            results["warned"] += 1

        # ── correctness always in [0, 1] ──
        if correctness >= 0:
            check(
                0.0 <= correctness <= 1.0,
                f"[{diff}] correctness in [0,1]",
                f"got {correctness}",
            )
        else:
            warn(f"[{diff}] correctness range check skipped")
            results["warned"] += 1


# ─── 2. EDGE CASES ───────────────────────────────────────────────────────────


def test_edge_cases():
    section("2 · Edge Cases")

    reset("easy")

    cases = [
        (
            "Empty body → 400/422",
            "POST",
            "/step",
            {"content": b"", "headers": {"Content-Type": "application/json"}},
            (400, 422),
        ),
        (
            "Missing required fields → 400/422",
            "POST",
            "/step",
            {"json": {}},
            (400, 422),
        ),
        (
            "Unknown action type handled gracefully",
            "POST",
            "/step",
            {"json": {"type": "teleport", "sql": "SELECT 1"}},
            (200, 400, 422),
        ),
        (
            "SQL injection doesn't crash server",
            "POST",
            "/step",
            {"json": {"type": "fix_query", "sql": "DROP TABLE employees; --"}},
            (200, 400, 422),
        ),
        (
            "Malformed JSON → 400/422",
            "POST",
            "/step",
            {
                "content": b"{bad json{{",
                "headers": {"Content-Type": "application/json"},
            },
            (400, 422),
        ),
        (
            "/reset with bad task_id handled gracefully",
            "POST",
            "/reset",
            {"json": {"task_id": "nonexistent_task"}},
            (200, 400, 404, 422),
        ),
        ("/state always responds", "GET", "/state", {}, (200, 400)),
        (
            "Empty SQL string handled",
            "POST",
            "/step",
            {"json": {"type": "fix_query", "sql": ""}},
            (200, 400, 422),
        ),
    ]

    for label, method, path, kwargs, expected in cases:
        kwargs.setdefault("timeout", 10)
        r = getattr(httpx, method.lower())(f"{BASE}{path}", **kwargs)
        check(r.status_code in expected, label, f"got {r.status_code}")

    long_sql = (
        "SELECT " + ", ".join([f"col_{i}" for i in range(1000)]) + " FROM employees"
    )
    r = httpx.post(
        f"{BASE}/step", json={"type": "fix_query", "sql": long_sql}, timeout=10
    )
    check(
        r.status_code in (200, 400, 422),
        "Very long query handled",
        f"got {r.status_code}",
    )
    check(r.status_code != 500, "No 500 on long query", f"got {r.status_code}")


# ─── 3. RAPID FIRE CONCURRENCY ───────────────────────────────────────────────


async def _single_request(client: httpx.AsyncClient, i: int) -> dict:
    t0 = time.perf_counter()
    try:
        url = f"{BASE}/health" if i % 2 == 0 else f"{BASE}/state"
        r = await client.get(url, timeout=30)
        latency = time.perf_counter() - t0
        return {"i": i, "status": r.status_code, "latency": latency, "error": None}
    except Exception as e:
        latency = time.perf_counter() - t0
        return {"i": i, "status": 0, "latency": latency, "error": str(e)}


async def test_concurrency_async():
    section(
        f"3 · Rapid Fire Concurrency  ({RAPID_FIRE_ROUNDS} reqs, {CONCURRENCY} parallel)"
    )

    async with httpx.AsyncClient() as client:
        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def bounded(i):
            async with semaphore:
                return await _single_request(client, i)

        t_start = time.perf_counter()
        responses = await asyncio.gather(
            *[bounded(i) for i in range(RAPID_FIRE_ROUNDS)]
        )
        total_time = time.perf_counter() - t_start

    statuses = [r["status"] for r in responses]
    latencies = [r["latency"] for r in responses]
    errors = [r for r in responses if r["error"]]
    successes = [s for s in statuses if s == 200]
    avg_lat = sum(latencies) / len(latencies)

    table = Table(
        title="Concurrency Results", show_header=True, header_style="bold magenta"
    )
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Total requests", str(RAPID_FIRE_ROUNDS))
    table.add_row("Successful (200)", str(len(successes)))
    table.add_row("Errors", str(len(errors)))
    table.add_row("Total time", f"{total_time:.2f}s")
    table.add_row("Avg latency", f"{avg_lat*1000:.1f} ms")
    table.add_row("Max latency", f"{max(latencies)*1000:.1f} ms")
    table.add_row("Min latency", f"{min(latencies)*1000:.1f} ms")
    table.add_row("Throughput", f"{RAPID_FIRE_ROUNDS/total_time:.1f} req/s")
    console.print(table)

    check(len(errors) == 0, "Zero network errors", f"{len(errors)} errors")
    check(
        len(successes) == RAPID_FIRE_ROUNDS,
        "All 50 requests → 200",
        f"{len(successes)}/50",
    )
    check(max(latencies) < 2.0, "Max latency < 2s", f"{max(latencies)*1000:.0f}ms")
    check(avg_lat < 0.5, "Avg latency < 500ms", f"{avg_lat*1000:.0f}ms")
    check(
        RAPID_FIRE_ROUNDS / total_time > 20,
        "Throughput > 20 req/s",
        f"{RAPID_FIRE_ROUNDS/total_time:.1f} req/s",
    )

    if errors:
        console.print("\n[red]Error details:[/red]")
        for e in errors[:5]:
            console.print(f"  req#{e['i']}: {e['error']}")


def test_concurrency():
    asyncio.run(test_concurrency_async())


# ─── 4. ENDPOINT SMOKE CHECK ─────────────────────────────────────────────────


def test_endpoints():
    section("4 · Endpoint Smoke Check")

    for path in [
        "/",
        "/health",
        "/metadata",
        "/schema",
        "/validate",
        "/state",
        "/tasks",
        "/docs",
    ]:
        r = httpx.get(f"{BASE}{path}", timeout=10)
        check(r.status_code == 200, f"GET {path} → 200", f"got {r.status_code}")

    r = httpx.get(f"{BASE}/tasks", timeout=10)
    if r.status_code == 200:
        body = r.json()
        raw = body if isinstance(body, list) else body.get("tasks", [])
        ids = [item["id"] if isinstance(item, dict) else item for item in raw]
        for t in ["easy", "medium", "hard"]:
            check(t in ids, f"/tasks includes '{t}'", f"ids={ids}")


# ─── 5. MEMORY STABILITY (30 resets) ─────────────────────────────────────────


def test_memory_stability():
    section("5 · Memory Stability  (30 resets in a row)")

    ROUNDS = 30
    tasks = ["easy", "medium", "hard"]

    if not HAS_PSUTIL:
        warn("psutil not installed — install with: pip install psutil")
        warn("Skipping memory tracking; still running 30 resets to check for crashes")
        results["warned"] += 2
        mem_before = mem_after = None
    else:
        pid = _get_server_pid()
        if pid:
            proc = psutil.Process(pid)
            mem_before = proc.memory_info().rss / 1024 / 1024  # MB
            console.print(
                f"  [dim]Server PID {pid} — RSS before: {mem_before:.1f} MB[/dim]"
            )
        else:
            warn(
                "Could not detect server PID on port 7860 — memory delta won't be measured"
            )
            results["warned"] += 1
            mem_before = mem_after = None
            proc = None

    failures = 0
    latencies = []

    for i in range(ROUNDS):
        task = tasks[i % 3]
        t0 = time.perf_counter()
        r = reset(task)
        latencies.append(time.perf_counter() - t0)

        if r.status_code != 200:
            failures += 1
            console.print(f"  [red]Reset #{i+1} ({task}) failed: {r.status_code}[/red]")
        else:
            # also fire one /step per reset to exercise the full cycle
            step("SELECT 1")

    avg_lat = sum(latencies) / len(latencies)

    # memory after
    if HAS_PSUTIL and mem_before is not None and proc is not None:
        try:
            mem_after = proc.memory_info().rss / 1024 / 1024
            mem_delta = mem_after - mem_before
            console.print(
                f"  [dim]RSS after:  {mem_after:.1f} MB  (Δ {mem_delta:+.1f} MB)[/dim]"
            )
            check(
                mem_delta < 50,
                "Memory growth < 50 MB over 30 resets",
                f"grew {mem_delta:.1f} MB",
            )
        except psutil.NoSuchProcess:
            warn("Server process ended during stability test")
            results["warned"] += 1

    check(failures == 0, f"All {ROUNDS} resets succeeded", f"{failures} failures")
    check(avg_lat < 5.0, "Avg reset latency < 5s", f"{avg_lat:.2f}s")
    check(
        max(latencies) < 8.0,
        "Max single reset < 8s",
        f"max {max(latencies)*1000:.0f}ms",
    )

    console.print(
        f"  [dim]Avg reset latency: {avg_lat*1000:.0f}ms  |  "
        f"Max: {max(latencies)*1000:.0f}ms[/dim]"
    )


# ─── FINAL SUMMARY ───────────────────────────────────────────────────────────


def summary():
    section("Summary")
    total = results["passed"] + results["failed"] + results["warned"]
    console.print(f"\n  Total checks : [bold]{total}[/bold]")
    console.print(f"  [green]Passed[/green]       : {results['passed']}")
    console.print(f"  [red]Failed[/red]       : {results['failed']}")
    console.print(f"  [yellow]Warned[/yellow]       : {results['warned']}")

    if results["failed"] == 0 and results["warned"] == 0:
        console.print("\n[bold green]🎉 Perfect score — ready for Day 7![/bold green]")
    elif results["failed"] == 0:
        console.print("\n[bold green]✅ No failures — ready for Day 7![/bold green]")
        console.print(
            f"[yellow]   ({results['warned']} warning(s) — cosmetic, not blocking)[/yellow]"
        )
    else:
        console.print(
            f"\n[bold red]⚠  {results['failed']} check(s) failed — review above.[/bold red]"
        )


# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    console.print("\n[bold white]SQL Debug Env — Stress Test[/bold white]")
    console.print(f"Target: [cyan]{BASE}[/cyan]\n")

    test_endpoints()
    test_grader_correctness()
    test_edge_cases()
    test_concurrency()
    test_memory_stability()
    summary()
