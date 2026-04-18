import json, sys
from pathlib import Path

with open('reports/ci_eval_strict.json', encoding='utf-8') as f:
    report = json.load(f)
metrics = report['metrics']

# Strict mode: require real_pass_rate >= 0.95
real_pass_rate = metrics.get('real_pass_rate', 0)
if real_pass_rate < 0.95:
    print(f'FAIL: Real pass rate {real_pass_rate*100:.1f}% < 95% threshold')
    print(f'Corpus missing: {metrics.get("corpus_missing_count", 0)}')
    print(f'Generic answers: {metrics.get("generic_answer_count", 0)}')
    sys.exit(1)

print(f'PASS: Real pass rate {real_pass_rate*100:.1f}% >= 95% threshold')
