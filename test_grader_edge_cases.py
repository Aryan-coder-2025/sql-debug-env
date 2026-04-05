import httpx

base = "http://localhost:7860"

print("DAY 5 P2 - GRADER EDGE CASE TESTS")
print("=" * 50)

all_passed = True

# Test 1 - Empty SQL
print("\nTest 1: Empty SQL submission...")
r = httpx.post(f"{base}/reset", json={"task_id": "easy", "scenario": "typo_from"})
session_id = r.json().get("session_id")
r = httpx.post(
    f"{base}/step",
    params={"session_id": session_id},
    json={"type": "run_sql", "sql": "", "reasoning": "empty"},
)
result = r.json()
error = result["observation"]["error_message"]
reward = result["reward"]["step_reward"]
empty_pass = error is not None and reward < 0
print(f"  Error message: {error}")
print(f"  Step reward: {reward}")
print(f'  Result: {"PASS" if empty_pass else "FAIL"}')
if not empty_pass:
    all_passed = False

# Test 2 - Right rows wrong order
print("\nTest 2: Right rows but wrong ORDER BY...")
r = httpx.post(f"{base}/reset", json={"task_id": "easy", "scenario": "typo_from"})
session_id = r.json().get("session_id")
r = httpx.post(
    f"{base}/step",
    params={"session_id": session_id},
    json={
        "type": "run_sql",
        "sql": "SELECT name, salary FROM employees WHERE department = 'Engineering' ORDER BY salary DESC",
        "reasoning": "wrong order",
    },
)
result = r.json()
correctness = result["reward"]["correctness"]
wrong_order_pass = 0.0 < correctness < 1.0
print(f"  Correctness: {correctness}")
print(f'  Result: {"PASS - partial credit given" if wrong_order_pass else "FAIL"}')
if not wrong_order_pass:
    all_passed = False

# Test 3 - Correct answer
print("\nTest 3: Correct answer gets full score...")
r = httpx.post(f"{base}/reset", json={"task_id": "easy", "scenario": "typo_from"})
session_id = r.json().get("session_id")
r = httpx.post(
    f"{base}/step",
    params={"session_id": session_id},
    json={
        "type": "run_sql",
        "sql": "SELECT name, salary FROM employees WHERE department = 'Engineering' ORDER BY name",
        "reasoning": "correct",
    },
)
result = r.json()
correctness = result["reward"]["correctness"]
correct_pass = correctness == 1.0
print(f"  Correctness: {correctness}")
print(f'  Result: {"PASS" if correct_pass else "FAIL"}')
if not correct_pass:
    all_passed = False

# Test 4 - NULL SQL
print("\nTest 4: NULL/None SQL...")
r = httpx.post(f"{base}/reset", json={"task_id": "easy", "scenario": "typo_from"})
session_id = r.json().get("session_id")
r = httpx.post(
    f"{base}/step",
    params={"session_id": session_id},
    json={"type": "run_sql", "sql": "", "reasoning": "null test"},
)
result = r.json()
null_pass = result["observation"]["error_message"] is not None
print(f'  Error caught: {result["observation"]["error_message"]}')
print(f'  Result: {"PASS" if null_pass else "FAIL"}')
if not null_pass:
    all_passed = False

# Test 5 - Grader endpoint
print("\nTest 5: /grader endpoint after episode...")
r = httpx.post(f"{base}/reset", json={"task_id": "easy", "scenario": "typo_from"})
session_id = r.json().get("session_id")
httpx.post(
    f"{base}/step",
    params={"session_id": session_id},
    json={
        "type": "run_sql",
        "sql": "SELECT name, salary FROM employees WHERE department = 'Engineering' ORDER BY name",
        "reasoning": "correct",
    },
)
r = httpx.get(f"{base}/grader", params={"session_id": session_id})
grader = r.json()
grader_pass = "score" in grader and grader["score"] > 0
print(f'  Score: {grader.get("score")}')
print(f'  Result: {"PASS" if grader_pass else "FAIL"}')
if not grader_pass:
    all_passed = False

print("\n" + "=" * 50)
if all_passed:
    print("ALL EDGE CASE TESTS PASSED - DAY 5 P2 COMPLETE")
else:
    print("SOME TESTS FAILED - CHECK ABOVE")
