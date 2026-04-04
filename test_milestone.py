import httpx
base = 'http://localhost:7860'
results = {}

print('=' * 60)
print('FULL MILESTONE CHECK - DAY 1 to DAY 4')
print('=' * 60)
print()

try:
    r = httpx.get(f'{base}/health')
    data = r.json()
    results['health'] = data.get('status') in ['ok', 'healthy']
    print(f"health endpoint:        {'PASS' if results['health'] else 'FAIL'} - {data.get('status')}")
except Exception as e:
    results['health'] = False
    print(f'health endpoint:        FAIL - {e}')

try:
    r = httpx.get(f'{base}/tasks')
    tasks = r.json().get('tasks', [])
    results['tasks_count'] = len(tasks) == 3
    print(f"tasks endpoint (3):     {'PASS' if results['tasks_count'] else 'FAIL'} - found {len(tasks)}")
except Exception as e:
    results['tasks_count'] = False
    print(f'tasks endpoint:         FAIL - {e}')

try:
    r = httpx.post(f'{base}/reset', json={'task_id': 'easy'})
    obs = r.json()
    results['reset_easy'] = obs.get('task_id') == 'easy' and obs.get('step_count') == 0
    print(f"reset easy:             {'PASS' if results['reset_easy'] else 'FAIL'} - status {r.status_code}")
except Exception as e:
    results['reset_easy'] = False
    print(f'reset easy:             FAIL - {e}')

try:
    r = httpx.post(f'{base}/step', json={
        'type': 'run_sql',
        'sql': "SELECT name, salary FROM employees WHERE department = 'Engineering' ORDER BY name",
        'reasoning': 'fixed FORM to FROM'
    })
    result = r.json()
    correctness = result['reward']['correctness']
    results['easy_correctness'] = correctness == 1.0
    print(f"easy correctness=1.0:   {'PASS' if results['easy_correctness'] else 'FAIL'} - got {correctness}")
except Exception as e:
    results['easy_correctness'] = False
    print(f'easy step:              FAIL - {e}')

try:
    r = httpx.get(f'{base}/grader')
    score = r.json().get('score', 0)
    results['grader'] = score > 0.9
    print(f"grader score>0.9:       {'PASS' if results['grader'] else 'FAIL'} - got {score}")
except Exception as e:
    results['grader'] = False
    print(f'grader:                 FAIL - {e}')

try:
    r = httpx.post(f'{base}/reset', json={'task_id': 'medium'})
    obs = r.json()
    results['reset_medium'] = obs.get('task_id') == 'medium'
    print(f"reset medium:           {'PASS' if results['reset_medium'] else 'FAIL'}")
except Exception as e:
    results['reset_medium'] = False
    print(f'reset medium:           FAIL - {e}')

try:
    r = httpx.post(f'{base}/step', json={
        'type': 'run_sql',
        'sql': "SELECT c.name AS customer_name, COUNT(o.id) AS total_orders, COALESCE(SUM(oi.amount), 0) AS total_spent FROM customers c LEFT JOIN orders o ON c.id = o.customer_id LEFT JOIN order_items oi ON o.id = oi.order_id GROUP BY c.id, c.name ORDER BY c.name",
        'reasoning': 'fixed inner join to left join'
    })
    result = r.json()
    correctness = result['reward']['correctness']
    results['medium_correctness'] = correctness == 1.0
    print(f"medium correctness=1.0: {'PASS' if results['medium_correctness'] else 'FAIL'} - got {correctness}")
except Exception as e:
    results['medium_correctness'] = False
    print(f'medium step:            FAIL - {e}')

try:
    r = httpx.post(f'{base}/reset', json={'task_id': 'hard'})
    obs = r.json()
    results['reset_hard'] = obs.get('task_id') == 'hard'
    print(f"reset hard:             {'PASS' if results['reset_hard'] else 'FAIL'}")
except Exception as e:
    results['reset_hard'] = False
    print(f'reset hard:             FAIL - {e}')

try:
    r = httpx.post(f'{base}/step', json={
        'type': 'run_sql',
        'sql': "SELECT p.name, SUM(s.amount) AS total FROM products p JOIN sales s ON p.id = s.product_id GROUP BY p.id, p.name HAVING COUNT(s.id) > 5 ORDER BY p.name",
        'reasoning': 'replaced correlated subquery with join'
    })
    result = r.json()
    correctness = result['reward']['correctness']
    results['hard_correctness'] = correctness == 1.0
    print(f"hard correctness=1.0:   {'PASS' if results['hard_correctness'] else 'FAIL'} - got {correctness}")
except Exception as e:
    results['hard_correctness'] = False
    print(f'hard step:              FAIL - {e}')

try:
    r = httpx.get(f'{base}/state')
    state = r.json()
    results['state'] = 'task_id' in state
    print(f"state endpoint:         {'PASS' if results['state'] else 'FAIL'}")
except Exception as e:
    results['state'] = False
    print(f'state endpoint:         FAIL - {e}')

try:
    httpx.post(f'{base}/reset', json={'task_id': 'easy'})
    r = httpx.post(f'{base}/step', json={
        'type': 'run_sql',
        'sql': 'DROP TABLE employees',
        'reasoning': 'test safety'
    })
    result = r.json()
    error = result['observation']['error_message']
    results['safety'] = error is not None and len(str(error)) > 0
    print(f"safety filter:          {'PASS' if results['safety'] else 'FAIL'} - {error}")
except Exception as e:
    results['safety'] = False
    print(f'safety filter:          FAIL - {e}')

try:
    httpx.post(f'{base}/reset', json={'task_id': 'easy'})
    r = httpx.post(f'{base}/step', json={
        'type': 'run_sql',
        'sql': 'SELECT * FROM employees',
        'reasoning': 'wrong fix'
    })
    result = r.json()
    wrong_reward = result['reward']['step_reward']
    results['wrong_answer'] = wrong_reward < 0.5
    print(f"wrong answer low score: {'PASS' if results['wrong_answer'] else 'FAIL'} - reward={wrong_reward}")
except Exception as e:
    results['wrong_answer'] = False
    print(f'wrong answer test:      FAIL - {e}')

try:
    r = httpx.get(f'{base}/metadata')
    results['metadata'] = 'name' in r.json()
    print(f"metadata endpoint:      {'PASS' if results['metadata'] else 'FAIL'}")
except Exception as e:
    results['metadata'] = False
    print(f'metadata endpoint:      FAIL - {e}')

print()
print('=' * 60)
total = len(results)
passed = sum(1 for v in results.values() if v)
print(f'RESULTS: {passed}/{total} tests passed')
print()
if passed == total:
    print('ALL TESTS PASSED')
    print('DAY 1-4 MILESTONE 100% COMPLETE')
else:
    print('FAILED TESTS:')
    for k, v in results.items():
        if not v:
            print(f'  - {k}')
print('=' * 60)
