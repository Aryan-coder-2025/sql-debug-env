from tasks.task_easy import get_task, EASY_SCENARIOS
from tasks.task_medium import get_task as get_medium, MEDIUM_SCENARIOS
from tasks.task_hard import get_task as get_hard, HARD_SCENARIOS

print('Testing all easy scenarios:')
print()
for s in EASY_SCENARIOS:
    t = get_task(s['name'])
    print(f"Scenario: {s['name']}")
    print(f"Broken:   {t.broken_query[:60]}")
    print(f"Expected: {len(t.expected_output)} rows")
print()

print('Testing all medium scenarios:')
print()
for s in MEDIUM_SCENARIOS:
    t = get_medium(s['name'])
    print(f"Scenario: {s['name']}")
    print(f"Broken:   {t.broken_query[:60]}")
    print(f"Expected: {len(t.expected_output)} rows")
print()

print('Testing all hard scenarios:')
print()
for s in HARD_SCENARIOS:
    t = get_hard(s['name'])
    print(f"Scenario: {s['name']}")
    print(f"Broken:   {t.broken_query[:60]}")
    print(f"Expected: {len(t.expected_output)} rows")
print()

print('ALL SCENARIOS TESTED')
