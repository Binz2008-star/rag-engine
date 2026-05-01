import json
from collections import Counter
from pathlib import Path

# Read the latest eval report
data = json.load(open('reports/eval_1777076263.json'))

# Failing queries
failures = [r for r in data['results'] if not r['passed']]
print(f'FAILING QUERIES ({len(failures)} total):')
for f in failures[:20]:  # Show top 20
    print(f"{f['test_id']}: {f['question']} - {f.get('failure_type', 'N/A')}")

print('\nFAILURE TYPE DISTRIBUTION:')
ft_counts = Counter([r.get('failure_type') for r in data['results'] if r.get('failure_type')])
for k, v in sorted(ft_counts.items()):
    print(f'{k}: {v}')

print('\nMETRICS SUMMARY:')
metrics = data['metrics']
print(f"Total queries: {metrics['total']}")
print(f"Passed: {metrics['passed']}")
print(f"Failed: {metrics['failed']}")
print(f"Pass rate: {metrics['pass_rate']:.1%}")
if 'grounding_failure_rate' in metrics:
    print(f"Grounding failure rate: {metrics['grounding_failure_rate']:.1%}")
if 'domain_accuracy' in metrics:
    print(f"Domain accuracy: {metrics['domain_accuracy']:.1%}")
if 'refusal_accuracy' in metrics:
    print(f"Refusal accuracy: {metrics['refusal_accuracy']:.1%}")
print(f"Avg latency: {metrics.get('avg_elapsed_s', 0):.2f}s")
