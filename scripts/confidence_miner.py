"""Confidence-calibrated intent miner.

Pulls weak or risky examples from eval reports and decision logs,
deduplicates by normalized query, and emits review-ready JSONL.
Never auto-labels ambiguous cases.
"""

import json
import re
import argparse
from pathlib import Path
from typing import Set, Dict, List
from collections import defaultdict
from datetime import datetime, timezone

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.text_normalization import normalize_query


def weak_label(query: str):
    """Weak label based on query content using normalized text."""
    q = normalize_query(query)

    has_eco = bool(re.search(r"\beco\b", q)) or "ايكو" in q
    has_robin = bool(re.search(r"\brobin\b", q)) or "روبن" in q

    if has_eco and not has_robin:
        return True, "eco"
    if has_robin and not has_eco:
        return True, "cv"

    # Unknown queries are ambiguous, not general
    return False, None


def is_ambiguous_case(query: str, confidence: float, intent: str) -> bool:
    """Detect high-risk ambiguous cases that should never be auto-labeled.

    Cases to flag:
    - Queries with mixed intent signals (e.g., both "eco" and "cv" terms)
    - Very low confidence (< 0.5)
    - Queries with negation or complex phrasing
    - Short queries (< 3 words)
    """
    q = query.lower()

    # Very low confidence
    if confidence < 0.5:
        return True

    # Short queries
    if len(q.split()) < 3:
        return True

    # Mixed intent signals
    eco_terms = {'eco', 'environmental', 'company', 'services', 'technology'}
    cv_terms = {'robin', 'edwan', 'cv', 'resume', 'deliveroo', 'skills', 'education', 'certifications'}

    has_eco = any(term in q for term in eco_terms)
    has_cv = any(term in q for term in cv_terms)

    if has_eco and has_cv:
        return True

    # Negation or complex phrasing
    negation_words = {'not', 'never', 'except', 'without', 'only'}
    if any(word in q for word in negation_words):
        return True

    return False


def load_eval_report(report_path: Path) -> List[Dict]:
    """Load eval report and extract weak/risky examples."""
    with open(report_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = []
    for result in data.get('results', []):
        confidence = result.get('intent_confidence', 1.0)
        method = result.get('intent_method', '')
        answer = result.get('answer', '')
        sources = result.get('sources', [])

        # Weak or risky trigger
        should_mine = (
            confidence <= 0.65
            or result.get("risk_level", "low") != "low"
            or not sources
            or len(answer.strip()) < 40
            or (
                method == "ml" or method == "v2_model"
                and confidence < 0.75
            )
        )

        if should_mine:
            # Try weak labeling
            can_label, label = weak_label(result['question'])

            results.append({
                'source': 'eval',
                'query': result['question'],
                'predicted_intent': result.get('intent', ''),
                'confidence': confidence,
                'method': method,
                'request_id': result.get('request_id', ''),
                'passed': result.get('passed', False),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'can_weak_label': can_label,
                'weak_label': label if can_label else '',
            })

    return results


def load_decision_logs(log_path: Path) -> List[Dict]:
    """Load decision logs and extract weak/risky intent examples."""
    results = []

    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)

            # Only process intent entries
            if entry.get('type') != 'intent':
                continue

            confidence = entry.get('confidence', 1.0)
            method = entry.get('method', '')

            # Weak or risky trigger
            should_mine = (
                confidence <= 0.65
                or entry.get("risk_level", "low") != "low"
                or (
                    method == "ml" or method == "v2_model"
                    and confidence < 0.75
                )
            )

            if should_mine:
                # Try weak labeling
                can_label, label = weak_label(entry.get('query', ''))

                results.append({
                    'source': 'decision_log',
                    'query': entry.get('query', ''),
                    'predicted_intent': entry.get('intent', ''),
                    'confidence': confidence,
                    'method': method,
                    'request_id': entry.get('request_id', ''),
                    'timestamp': entry.get('timestamp', ''),
                    'can_weak_label': can_label,
                    'weak_label': label if can_label else '',
                })

    return results


def dedupe_examples(examples: List[Dict]) -> List[Dict]:
    """Deduplicate examples by normalized query.

    Keeps the example with lowest confidence (most concerning) for each normalized query.
    If tied, prefers real log over eval.
    """
    normalized_map: Dict[str, Dict] = {}

    for example in examples:
        normalized = normalize_query(example['query'])

        if normalized not in normalized_map:
            normalized_map[normalized] = example
        else:
            # Keep the one with lower confidence (more concerning)
            if example['confidence'] < normalized_map[normalized]['confidence']:
                normalized_map[normalized] = example
            # If tied, prefer real log over eval
            elif (example['confidence'] == normalized_map[normalized]['confidence'] and
                  example['source'] == 'decision_log' and
                  normalized_map[normalized]['source'] == 'eval'):
                normalized_map[normalized] = example

    return list(normalized_map.values())


def main():
    """Main mining pipeline."""
    parser = argparse.ArgumentParser(description='Mine weak/risky intent examples')
    parser.add_argument('--eval-report', type=str, default='reports/latest.json',
                        help='Path to eval report JSON')
    parser.add_argument('--query-log', type=str, default='logs/decisions.jsonl',
                        help='Path to query decision log JSONL')
    parser.add_argument('--out', type=str, default='data/review_queue.jsonl',
                        help='Output path for review queue JSONL')
    args = parser.parse_args()

    # Paths
    eval_report_path = Path(args.eval_report)
    decision_log_path = Path(args.query_log)
    output_path = Path(args.out)

    # Load data
    print(f"Loading eval report from {eval_report_path}")
    if eval_report_path.exists():
        eval_examples = load_eval_report(eval_report_path)
        print(f"  Found {len(eval_examples)} weak/risky examples from eval")
    else:
        print(f"  Eval report not found, skipping")
        eval_examples = []

    print(f"Loading decision logs from {decision_log_path}")
    if decision_log_path.exists():
        log_examples = load_decision_logs(decision_log_path)
        print(f"  Found {len(log_examples)} weak/risky examples from logs")
    else:
        print(f"  Decision log not found, skipping")
        log_examples = []

    # Combine
    all_examples = eval_examples + log_examples
    print(f"  Total: {len(all_examples)} examples before deduplication")

    # Dedupe
    deduped = dedupe_examples(all_examples)
    print(f"  After deduplication: {len(deduped)} unique queries")

    # Add risk flags and prepare for review
    for example in deduped:
        example['is_ambiguous'] = is_ambiguous_case(
            example['query'],
            example['confidence'],
            example['predicted_intent']
        )
        # Only require manual review if not weak-labelable or ambiguous
        example['needs_manual_review'] = not example.get('can_weak_label', False) or example['is_ambiguous']

    # Output review-ready JSONL
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for example in deduped:
            # Emit review-ready format
            review_entry = {
                'query': example['query'],
                'normalized_query': normalize_query(example['query']),
                'predicted_intent': example['predicted_intent'],
                'confidence': example['confidence'],
                'method': example['method'],
                'is_ambiguous': example['is_ambiguous'],
                'source': example['source'],
                'request_id': example['request_id'],
                'timestamp': example['timestamp'],
                'can_weak_label': example.get('can_weak_label', False),
                'weak_label': example.get('weak_label', ''),
                'label': '',  # Empty - requires manual labeling
                'reviewer_notes': '',
            }
            f.write(json.dumps(review_entry, ensure_ascii=False) + '\n')

    print(f"\n✓ Output review candidates to {output_path}")
    print(f"  Total candidates: {len(deduped)}")

    # Summary statistics
    ambiguous_count = sum(1 for e in deduped if e['is_ambiguous'])
    weak_labelable = sum(1 for e in deduped if e.get('can_weak_label', False))
    print(f"  Ambiguous cases: {ambiguous_count}")
    print(f"  Weak-labelable: {weak_labelable}")
    print(f"  Requires manual review: {len(deduped) - weak_labelable}")

    # Confidence distribution
    if deduped:
        confidences = [e['confidence'] for e in deduped]
        print(f"  Confidence range: {min(confidences):.3f} - {max(confidences):.3f}")
        print(f"  Avg confidence: {sum(confidences) / len(confidences):.3f}")


if __name__ == '__main__':
    main()
