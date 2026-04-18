import json
import sys
from pathlib import Path


def main():
    report_path = Path("reports/post_train.json")
    
    if not report_path.exists():
        print(f"FAIL: report not found at {report_path}")
        sys.exit(1)
    
    with open(report_path, encoding='utf-8') as f:
        report = json.load(f)

    metrics = report.get("metrics", {})
    passed = metrics.get("passed", 0)
    total = metrics.get("total", 0)

    if passed == 61 and total == 61:
        print("PASS: eval gate satisfied (61/61)")
        sys.exit(0)

    print(f"FAIL: eval gate failed ({passed}/{total})")
    sys.exit(1)


if __name__ == "__main__":
    main()
