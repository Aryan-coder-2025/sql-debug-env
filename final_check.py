import httpx
import json

LOCAL = 'http://localhost:7860'
LIVE = 'https://aryan-coder-25-openenv.hf.space'

results = {}

print('=' * 60)
print('FINAL SUBMISSION CHECK')
print('=' * 60)
print()

print('--- LOCAL SERVER TESTS ---')
print()

try:
    r = httpx.get(f'{LOCAL}/health')
    results['local_health'] = r.json().get('status') in ['ok', 'healthy']
    print(f"local /health:          {'PASS' if results['local_health'] else 'FAIL'}")
except Exception as e:
    results['local_health'] = False
    print(f'local /health:          FAIL - {e}')

try:
    r = httpx.get(f'{LOCAL}/')
    results['local_root'] = 'name' in r.json()
    print(f"local /:                {'PASS' if results['local_root'] else 'FAIL'}")
except Exception as e:
    results['local_root'] = False
    print(f'local /:                FAIL')

try:
    r = httpx.get(f'{LOCAL}/tasks')
    results['local_tasks'] = len(r.json().get('tasks', [])) >= 3
    print(f"local /tasks (>=3):     {'PASS' if results['local_tasks'] else 'FAIL'}")
except Exception as e:
    results['local_tasks'] = False
    print(f'local /tasks:           FAIL')

try:
    r = httpx.get(f'{LOCAL}/validate')
    results['local_validate'] = r.json().get('valid', False)
    print(f"local /validate:        {'PASS' if results['local_validate'] else 'FAIL'}")
except Exception as e:
    results['local_validate'] = False
    print(f'local /validate:        FAIL')

try:
    r = httpx.post(f'{LOCAL}/reset', json={'task_id': 'easy'})
    obs = r.json()
    session_id = obs.get('session_id')
    results['local_reset_easy'] = obs.get('task_id') == 'easy'
    print(f"local /reset easy:      {'PASS' if results['local_reset_easy'] else 'FAIL'} session={session_id[:8] if session_id else None}")
except Exception as e:
    results['local_reset_easy'] = False
    session_id = None
    print(f'local /reset easy:      FAIL')

try:
    r = httpx.post(f'{LOCAL}/step', json={
        'type': 'run_sql',
        'sql': "SELECT name, salary FROM employees WHERE department = 'Engineering' ORDER BY name",
        'reasoning': 'fixed',
        'session_id': session_id
    })
    correctness = r.json()['reward']['correctness']
    results['local_step_easy'] = correctness == 1.0
    print(f"local /step easy=1.0:   {'PASS' if results['local_step_easy'] else 'FAIL'} - got {correctness}")
except Exception as e:
    results['local_step_easy'] = False
    print(f'local /step easy:       FAIL - {e}')

try:
    r = httpx.get(f'{LOCAL}/grader', params={'session_id': session_id})
    score = r.json().get('score', 0)
    results['local_grader'] = score > 0.9
    print(f"local /grader > 0.9:    {'PASS' if results['local_grader'] else 'FAIL'} - got {score}")
except Exception as e:
    results['local_grader'] = False
    print(f'local /grader:          FAIL')

try:
    r = httpx.post(f'{LOCAL}/reset', json={'task_id': 'medium'})
    results['local_reset_medium'] = r.json().get('task_id') == 'medium'
    print(f"local /reset medium:    {'PASS' if results['local_reset_medium'] else 'FAIL'}")
except Exception as e:
    results['local_reset_medium'] = False
    print(f'local /reset medium:    FAIL')

try:
    r = httpx.post(f'{LOCAL}/reset', json={'task_id': 'hard'})
    results['local_reset_hard'] = r.json().get('task_id') == 'hard'
    print(f"local /reset hard:      {'PASS' if results['local_reset_hard'] else 'FAIL'}")
except Exception as e:
    results['local_reset_hard'] = False
    print(f'local /reset hard:      FAIL')

try:
    r = httpx.post(f'{LOCAL}/reset', json={'task_id': 'easy'})
    safety_session = r.json().get('session_id')
    r = httpx.post(f'{LOCAL}/step', json={
        'type': 'run_sql',
        'sql': 'DROP TABLE employees',
        'reasoning': 'test safety'
    }, params={'session_id': safety_session})
    error = r.json()['observation']['error_message']
    results['local_safety'] = error is not None and len(str(error)) > 0
    print(f"local safety filter:    {'PASS' if results['local_safety'] else 'FAIL'}")
except Exception as e:
    results['local_safety'] = False
    print(f'local safety:           FAIL')

print()
print('--- LIVE HF SPACE TESTS ---')
print()

try:
    r = httpx.get(f'{LIVE}/health', timeout=30)
    results['live_health'] = r.json().get('status') in ['ok', 'healthy']
    print(f"live /health:           {'PASS' if results['live_health'] else 'FAIL'}")
except Exception as e:
    results['live_health'] = False
    print(f'live /health:           FAIL')

try:
    r = httpx.get(f'{LIVE}/', timeout=30)
    results['live_root'] = 'name' in r.json()
    print(f"live /:                 {'PASS' if results['live_root'] else 'FAIL'}")
except Exception as e:
    results['live_root'] = False
    print(f'live /:                 FAIL')

try:
    r = httpx.get(f'{LIVE}/tasks', timeout=30)
    results['live_tasks'] = len(r.json().get('tasks', [])) == 3
    print(f"live /tasks (3):        {'PASS' if results['live_tasks'] else 'FAIL'}")
except Exception as e:
    results['live_tasks'] = False
    print(f'live /tasks:            FAIL')

try:
    r = httpx.post(f'{LIVE}/reset', json={'task_id': 'easy'}, timeout=30)
    live_obs = r.json()
    live_session = live_obs.get('session_id')
    results['live_reset'] = live_obs.get('task_id') == 'easy'
    print(f"live /reset easy:       {'PASS' if results['live_reset'] else 'FAIL'}")
except Exception as e:
    results['live_reset'] = False
    live_session = None
    print(f'live /reset:            FAIL')

try:
    r = httpx.post(f'{LIVE}/step', json={
        'type': 'run_sql',
        'sql': "SELECT name, salary FROM employees WHERE department = 'Engineering' ORDER BY name",
        'reasoning': 'fixed'
    }, params={'session_id': live_session}, timeout=30)
    correctness = r.json()['reward']['correctness']
    results['live_step'] = correctness == 1.0
    print(f"live /step easy=1.0:    {'PASS' if results['live_step'] else 'FAIL'} - got {correctness}")
except Exception as e:
    results['live_step'] = False
    print(f'live /step:             FAIL')

try:
    r = httpx.get(f'{LIVE}/grader', params={'session_id': live_session}, timeout=30)
    score = r.json().get('score', 0)
    results['live_grader'] = score > 0.9
    print(f"live /grader > 0.9:     {'PASS' if results['live_grader'] else 'FAIL'} - got {score}")
except Exception as e:
    results['live_grader'] = False
    print(f'live /grader:           FAIL')

try:
    r = httpx.get(f'{LIVE}/validate', timeout=30)
    results['live_validate'] = r.json().get('valid', False)
    print(f"live /validate:         {'PASS' if results['live_validate'] else 'FAIL'}")
except Exception as e:
    results['live_validate'] = False
    print(f'live /validate:         FAIL')

print()
print('=' * 60)
total = len(results)
passed = sum(1 for v in results.values() if v)
print(f'RESULTS: {passed}/{total} tests passed')
print()

failed = [k for k, v in results.items() if not v]
if not failed:
    print('ALL TESTS PASSED')
    print('READY TO SUBMIT')
    print()
    print('SUBMISSION URL:')
    print('https://aryan-coder-25-openenv.hf.space')
else:
    print('FAILED TESTS:')
    for f in failed:
        print(f'  - {f}')
print('=' * 60)
