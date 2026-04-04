import httpx
base = 'https://aryan-coder-25-openenv.hf.space'

print('Testing LIVE HF Space...')
print()

r = httpx.get(f'{base}/health')
print('health:', r.json())

r = httpx.get(f'{base}/tasks')
print('tasks:', len(r.json()['tasks']), 'tasks found')

r = httpx.post(f'{base}/reset', json={'task_id': 'easy'})
obs = r.json()
print('reset easy task_id:', obs.get('task_id'))
print('broken query:', obs.get('broken_query', '')[:50])

r = httpx.post(f'{base}/step', json={
    'type': 'run_sql',
    'sql': "SELECT name, salary FROM employees WHERE department = 'Engineering' ORDER BY name",
    'reasoning': 'fixed FORM to FROM'
})
result = r.json()
print('correctness:', result['reward']['correctness'])
print('done:', result['done'])

r = httpx.get(f'{base}/grader')
print('grader score:', r.json()['score'])

print()
print('HF SPACE IS FULLY WORKING')
