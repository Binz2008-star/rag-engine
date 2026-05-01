import json
from pathlib import Path

path = Path("tests/eval_queries.json")
cases = json.loads(path.read_text(encoding="utf-8"))

# Flip ECO contact from refusal to grounded
for case in cases:
    if case.get("query") == "What is the contact information for ECO?":
        case.pop("expected_refusal", None)
        case.pop("expected_failure_type", None)
        case["expected_contains"] = ["+971 52 223 3989", "robinedwan@gmail.com"]

# Add new founder/operator case
founder_case = {
    "query": "Who operates ECO?",
    "expected_intent": "eco",
    "expected_method": "rule",
    "expected_contains": ["Founder", "General Manager"],
    "suite": "baseline_en"
}
if not any(c.get("query") == "Who operates ECO?" for c in cases):
    cases.append(founder_case)

path.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("Done")

# Verify
for c in cases:
    if c.get("query") in ["What is the contact information for ECO?", "Who operates ECO?"]:
        print(json.dumps(c, indent=2))
