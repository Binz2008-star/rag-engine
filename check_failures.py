import json
from pathlib import Path

p = Path(r'D:\AI\assistant\reports\agent_eval_proper.json')
data = json.loads(p.read_text(encoding='utf-8'))
fails = [r for r in data["results"] if not r["passed"]]
print(f"FAIL COUNT: {len(fails)}")
for r in fails:
    print("\n---")
    print("test_id:", r["test_id"])
    print("question:", r["question"])
    print("reasons:", r["reasons"])
    print("sources:", r["sources"])
    print("answer:", r["answer"])
