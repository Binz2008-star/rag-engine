"""Run shadow evaluation on repo datasets.

This script evaluates shadow router quality using existing repo datasets
without affecting production behavior or CI gates.
"""

import json
import sys
from pathlib import Path

from evaluation.shadow_evaluator import ShadowEvaluator
from router.intent_router import IntentRouter


def main():
    """Run shadow evaluation and save report."""
    # Initialize router with active model
    router = IntentRouter.from_active_model()
    evaluator = ShadowEvaluator(router)
    
    # Load datasets
    train_path = Path("data/intent_dataset.jsonl")
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
    
    # Combine datasets
    all_rows = train_rows + eval_rows
    
    if not all_rows:
        print("Error: No data found for evaluation")
        sys.exit(1)
    
    # Run evaluation
    report = evaluator.evaluate_dataset(all_rows)
    
    # Convert report to dict for JSON serialization
    report_dict = {
        "total_rows": report.total_rows,
        "evaluated_rows": report.evaluated_rows,
        "skipped_hard_rule_rows": report.skipped_hard_rule_rows,
        "overall_accuracy": report.overall_accuracy,
        "per_intent_accuracy": report.per_intent_accuracy,
        "uncertain_rate": report.uncertain_rate,
        "fallback_rate": report.fallback_rate,
        "public_disagreement_rate": report.public_disagreement_rate,
        "confidence_band_counts": report.confidence_band_counts,
        "shadow_intent_counts": report.shadow_intent_counts,
        "shadow_reason_counts": report.shadow_reason_counts,
        "rows": report.rows,
    }
    
    # Save report
    output_path = Path("reports/shadow_eval.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
    
    # Print summary
    print("\n=== Shadow Evaluation Report ===")
    print(f"Total rows: {report.total_rows}")
    print(f"Evaluated rows: {report.evaluated_rows}")
    print(f"Skipped hard-rule rows: {report.skipped_hard_rule_rows}")
    print(f"Overall accuracy: {report.overall_accuracy:.3f}")
    print(f"\nPer-intent accuracy:")
    for intent, acc in report.per_intent_accuracy.items():
        print(f"  {intent}: {acc:.3f}")
    print(f"\nUncertain rate: {report.uncertain_rate:.3f}")
    print(f"Fallback rate: {report.fallback_rate:.3f}")
    print(f"Public disagreement rate: {report.public_disagreement_rate:.3f}")
    print(f"\nConfidence band counts:")
    for band, count in report.confidence_band_counts.items():
        print(f"  {band}: {count}")
    print(f"\nShadow intent counts:")
    for intent, count in report.shadow_intent_counts.items():
        print(f"  {intent}: {count}")
    print(f"\nShadow reason counts:")
    for reason, count in report.shadow_reason_counts.items():
        print(f"  {reason}: {count}")
    print("=" * 30)
    
    print(f"\nReport saved to: {output_path}")
    
    # Exit with success
    sys.exit(0)


if __name__ == "__main__":
    main()
