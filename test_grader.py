import httpx
base = 'http://localhost:7860'

correct_fixes = {
    'easy': "SELECT name, salary FROM employees WHERE department = 'Engineering' ORDER BY name",
    'medium': """SELECT
    c.name AS customer_name,
    COUNT(o.id) AS total_orders,
    COALESCE(SUM(oi.amount), 0) AS total_spent
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
LEFT JOIN order_items oi ON o.id = oi.order_id
GROUP BY c.id, c.name
ORDER BY c.name""",
    'hard': """SELECT p.name, SUM(s.amount) AS total
FROM products p
JOIN sales s ON p.id = s.product_id
GROUP BY p.id, p.name
HAVING COUNT(s.id) > 5
ORDER BY p.name"""
}

print('GRADER TEST - ALL TASKS')
print('=' * 50)

all_passed = True
for task_id, correct_sql in correct_fixes.items():
    r = httpx.post(f'{base}/reset', params={'task_id': task_id})
    obs = r.json()
    
    r = httpx.post(f'{base}/step', json={
        'type': 'run_sql',
        'sql': correct_sql,
        'reasoning': 'fixed'
    })
    result = r.json()
    correctness = result['reward']['correctness']
    
    r = httpx.get(f'{base}/grader')
    score = r.json()['score']
    
    status = 'PASS' if correctness == 1.0 else 'FAIL'
    if status == 'FAIL':
        all_passed = False
    print(f'{task_id:10} correctness={correctness} score={score} {status}')

print('=' * 50)

print()
print('Testing wrong answer...')
httpx.post(f'{base}/reset', params={'task_id': 'easy'})
r = httpx.post(f'{base}/step', json={
    'type': 'run_sql',
    'sql': 'SELECT * FROM employees',
    'reasoning': 'wrong'
})
result = r.json()
wrong_correctness = result['reward']['correctness']
wrong_reward = result['reward']['step_reward']
print(f'Wrong answer correctness: {wrong_correctness}')
print(f'Wrong answer reward: {wrong_reward}')
wrong_pass = wrong_correctness < 1.0
print(f'Wrong answer test: {"PASS" if wrong_pass else "FAIL"}')

print()
print('Testing empty query...')
r = httpx.post(f'{base}/step', json={
    'type': 'run_sql',
    'sql': '',
    'reasoning': 'empty'
})
result = r.json()
error = result['observation']['error_message']
empty_reward = result['reward']['step_reward']
print(f'Empty query error: {error}')
print(f'Empty query reward: {empty_reward}')
empty_pass = error is not None and empty_reward < 0
print(f'Empty query test: {"PASS" if empty_pass else "FAIL"}')

print()
if all_passed and wrong_pass and empty_pass:
    print('ALL TESTS PASSED - DAY 3 + DAY 4 COMPLETE')
else:
    print('SOME TESTS FAILED - CHECK ABOVE')
