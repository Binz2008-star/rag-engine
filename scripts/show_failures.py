"""Temporary helper to inspect failing eval cases."""
from __future__ import annotations

import json
from pathlib import Path

REPORT = Path(__file__).resolve().parents[1] / "reports" / "agent_eval_proper.json"


def main() -> None:
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    failures = [r for r in data["results"] if not r["passed"]]
    print(f"Failures: {len(failures)}\n")
    for r in failures:
        print(f"Q{r['test_id']}: {r['question'][:80]}")
        print(f"  Answer: {r['answer'][:160]}")
        print(f"  Reasons: {r['reasons']}")
        print(f"  Expected source: {r.get('expected_source', '')}")
        print(f"  Got sources: {r.get('sources', [])}")
        print()


if __name__ == "__main__":
    main()
