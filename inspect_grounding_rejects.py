import json

# Read the latest eval report
with open('reports/eval_1777073636.json', 'r') as f:
    data = json.load(f)

# Get all grounding_reject examples
grounding_rejects = [r for r in data['results'] if r.get('failure_type') == 'grounding_reject']

print(f'Total grounding_reject failures: {len(grounding_rejects)}')
print(f'Total queries: {data["metrics"]["total"]}')
print(f'Grounding failure rate: {data["metrics"]["grounding_failure_rate"]:.1%}')
print()

# Show first 20 grounding_reject examples
print('First 20 grounding_reject examples:')
for i, r in enumerate(grounding_rejects[:20]):
    print(f"{i+1}. Query: {r['question']}")
    print(f"   Answer: {r['answer'][:100]}...")
    print(f"   Sources: {r['sources'][:3]}")
    print()
