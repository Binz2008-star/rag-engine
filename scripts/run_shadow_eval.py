"""Run shadow evaluation on repo datasets.

This script evaluates shadow router quality using existing repo datasets
without affecting production behavior or CI gates.
"""

import json
import sys
from pathlib import Path

# Add repo root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.shadow_evaluator import ShadowEvaluator
from router.intent_router import IntentRouter


def main():
    """Run shadow evaluation and save report."""
    # Initialize router with active model
    router = IntentRouter.from_active_model()
    evaluator = ShadowEvaluator(router)

    # Load datasets
    train_path = Path("data/train.jsonl")
    eval_path = Path("tests/eval_queries.json")

    if train_path.exists():
        train_rows = evaluator.load_train_jsonl(train_path)
    else:
        print(f"Warning: {train_path} not found, skipping training data")
        train_rows = []

    if eval_path.exists():
        eval_rows = evaluator.load_eval_queries_json(eval_path)
    else:
        print(f"Warning: {eval_path} not found, skipping eval data")
        eval_rows = []

    # Evaluate datasets separately
    train_report = evaluator.evaluate_dataset(train_rows) if train_rows else None
    eval_report = evaluator.evaluate_dataset(eval_rows) if eval_rows else None

    # Build structured report
    report_dict = {
        "metadata": {
            "total_train_rows": len(train_rows),
            "total_eval_rows": len(eval_rows),
            "total_rows": len(train_rows) + len(eval_rows),
        },
        "train_labeled": {
            "total_rows": train_report.total_rows if train_report else 0,
            "evaluated_rows": train_report.evaluated_rows if train_report else 0,
            "skipped_hard_rule_rows": train_report.skipped_hard_rule_rows if train_report else 0,
            "overall_accuracy": train_report.overall_accuracy if train_report else 0.0,
            "per_intent_accuracy": train_report.per_intent_accuracy if train_report else {},
            "uncertain_rate": train_report.uncertain_rate if train_report else 0.0,
            "fallback_rate": train_report.fallback_rate if train_report else 0.0,
            "public_disagreement_rate": train_report.public_disagreement_rate if train_report else 0.0,
            "confidence_band_counts": train_report.confidence_band_counts if train_report else {},
            "shadow_intent_counts": train_report.shadow_intent_counts if train_report else {},
            "shadow_reason_counts": train_report.shadow_reason_counts if train_report else {},
            "rows": train_report.rows if train_report else [],
        },
        "curated_queries": {
            "total_rows": eval_report.total_rows if eval_report else 0,
            "evaluated_rows": eval_report.evaluated_rows if eval_report else 0,
            "skipped_hard_rule_rows": eval_report.skipped_hard_rule_rows if eval_report else 0,
            "overall_accuracy": eval_report.overall_accuracy if eval_report else 0.0,
            "per_intent_accuracy": eval_report.per_intent_accuracy if eval_report else {},
            "uncertain_rate": eval_report.uncertain_rate if eval_report else 0.0,
            "fallback_rate": eval_report.fallback_rate if eval_report else 0.0,
            "public_disagreement_rate": eval_report.public_disagreement_rate if eval_report else 0.0,
            "confidence_band_counts": eval_report.confidence_band_counts if eval_report else {},
            "shadow_intent_counts": eval_report.shadow_intent_counts if eval_report else {},
            "shadow_reason_counts": eval_report.shadow_reason_counts if eval_report else {},
            "rows": eval_report.rows if eval_report else [],
        },
        "suite_breakdown": {},
    }

    # Add suite breakdown for curated queries
    if eval_report and eval_report.rows:
        suite_breakdown = {}
        for row in eval_report.rows:
            suite = row.get("suite", "unknown")
            if suite not in suite_breakdown:
                suite_breakdown[suite] = {
                    "total_rows": 0,
                    "correct": 0,
                    "uncertain": 0,
                }
            suite_breakdown[suite]["total_rows"] += 1
            if row["shadow_intent"] == row["expected_intent"] and row["shadow_intent"] != "uncertain":
                suite_breakdown[suite]["correct"] += 1
            if row["shadow_intent"] == "uncertain":
                suite_breakdown[suite]["uncertain"] += 1

        # Calculate accuracy per suite
        for suite, metrics in suite_breakdown.items():
            if metrics["total_rows"] > 0:
                metrics["accuracy"] = metrics["correct"] / metrics["total_rows"]
            else:
                metrics["accuracy"] = 0.0

        report_dict["suite_breakdown"] = suite_breakdown

    # Save report
    output_path = Path("reports/shadow_eval.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")

    # Print summary
    print("\n=== Shadow Evaluation Report ===")
    print(f"Total train rows: {report_dict['metadata']['total_train_rows']}")
    print(f"Total eval rows: {report_dict['metadata']['total_eval_rows']}")
    print(f"Total rows: {report_dict['metadata']['total_rows']}")

    if train_report:
        print(f"\n=== Train Labeled ===")
        print(f"Evaluated rows: {train_report.evaluated_rows}")
        print(f"Skipped hard-rule rows: {train_report.skipped_hard_rule_rows}")
        print(f"Overall accuracy: {train_report.overall_accuracy:.3f}")

    if eval_report:
        print(f"\n=== Curated Queries ===")
        print(f"Evaluated rows: {eval_report.evaluated_rows}")
        print(f"Skipped hard-rule rows: {eval_report.skipped_hard_rule_rows}")
        print(f"Overall accuracy: {eval_report.overall_accuracy:.3f}")
        print(f"\nSuite breakdown:")
        for suite, metrics in report_dict["suite_breakdown"].items():
            print(f"  {suite}: {metrics['accuracy']:.3f} ({metrics['correct']}/{metrics['total_rows']})")

    print("=" * 30)

    print(f"\nReport saved to: {output_path}")

    # Exit with success
    sys.exit(0)


if __name__ == "__main__":
    main()
