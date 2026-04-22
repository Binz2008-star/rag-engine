import json

old = json.load(open('eval_old.json', encoding='utf-8'))
new = json.load(open('tests/eval_queries.json', encoding='utf-8'))

# Get failing IDs from the report
report = json.load(open('reports/eval_det_1.json', encoding='utf-8'))
failing_ids = {q['test_id'] for q in report['results'] if not q.get('passed', False)}

print('Failing test IDs:', sorted(failing_ids))
print()

# Check which of these existed in the old test set
for i, test in enumerate(old, 1):
    if i in failing_ids:
        print(f'Test {i} (existed at 754f26c): {test["query"][:60]}...')
