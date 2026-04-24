"""Shadow report generation script.

This script generates shadow evaluation reports without affecting CI gates.
"""

import json
from pathlib import Path

from evaluation.shadow_evaluator import ShadowEvaluator, ShadowEvalReport
from router.intent_router import IntentRouter


def generate_report_from_shadow_stats(
    router: IntentRouter,
    output_path: Path,
) -> ShadowEvalReport:
    """Generate report from router shadow stats and save to JSON.
    
    Args:
        router: IntentRouter with shadow stats
        output_path: Path to save JSON report
        
    Returns:
        ShadowEvalReport
    """
    evaluator = ShadowEvaluator(router)
    report = evaluator.evaluate_from_shadow_stats()
    
    # Convert to dict for JSON serialization
    report_dict = {
        "overall_accuracy": report.overall_accuracy,
        "per_intent_accuracy": report.per_intent_accuracy,
        "uncertain_rate": report.uncertain_rate,
        "fallback_rate": report.fallback_rate,
        "public_disagreement_rate": report.public_disagreement_rate,
        "confidence_band_counts": report.confidence_band_counts,
        "total_queries": report.total_queries,
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
    
    return report


def print_report(report: ShadowEvalReport) -> None:
    """Print shadow evaluation report to console."""
    print("\n=== Shadow Evaluation Report ===")
    print(f"Total queries: {report.total_queries}")
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
    print("=" * 30)


if __name__ == "__main__":
    # Example usage
    from router.intent_router import IntentRouter
    
    # Create router (with or without model)
    router = IntentRouter.from_active_model()
    
    # Run some queries to populate shadow stats
    queries = [
        "What is the GDP of Japan?",
        "Tell me about ECO services",
        "CV skills for engineers",
        "Quantum physics basics",
    ]
    
    for query in queries:
        router.route(query)
    
    # Generate report
    report_path = Path("reports/shadow_eval_report.json")
    report = generate_report_from_shadow_stats(router, report_path)
    print_report(report)
    
    print(f"\nReport saved to: {report_path}")
