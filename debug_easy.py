import httpx
import json
import os
from openai import OpenAI

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
client = OpenAI(api_key=GROQ_API_KEY, base_url='https://api.groq.com/openai/v1')
MODEL = 'llama-3.3-70b-versatile'
base = 'http://localhost:7860'

print('Step 1: Reset easy task')
r = httpx.post(f'{base}/reset', json={'task_id': 'easy'}, timeout=30)
print('Status:', r.status_code)
obs = r.json()
print('task_id:', obs.get('task_id'))
print('broken_query:', obs.get('broken_query'))
print()

print('Step 2: Ask model to fix it')
messages = [
    {'role': 'system', 'content': 'You are a SQL expert. Fix broken SQL queries. Respond ONLY in JSON: {"type": "run_sql", "sql": "FIXED SQL", "reasoning": "why"}'},
    {'role': 'user', 'content': f"Schema:\n{obs.get('db_schema')}\n\nBroken query:\n{obs.get('broken_query')}\n\nFix this."}
]

response = client.chat.completions.create(
    model=MODEL,
    messages=messages,
    response_format={'type': 'json_object'},
    temperature=0.1
)
action_json = response.choices[0].message.content
action = json.loads(action_json)
print('Model response:', action)
print()

print('Step 3: Send to environment')
r = httpx.post(f'{base}/step', json=action, timeout=30)
print('Status:', r.status_code)
if r.status_code == 200:
    result = r.json()
    print('correctness:', result['reward']['correctness'])
    print('done:', result['done'])
    print('error:', result['observation']['error_message'])
else:
    print('Error:', r.text)
