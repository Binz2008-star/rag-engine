"""Evaluation runner that uses baseline validation but routes through agents."""

import sys
import os
import time
import json
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add openclaw to path
sys.path.insert(0, r"C:\openclaw")
from router import route_task

# Add assistant to path
sys.path.insert(0, r"D:\AI\assistant")
from app.rag_service import get_rag_service

# Import evaluation logic from original eval_runner
from eval_runner import (
    evaluate_answer,
    normalize_arabic,
    extract_expected_terms,
    normalize_expected_terms as normalize_terms,
    enforce_english_only
)

# Add agent paths with distinct imports
research_path = os.path.join(r"C:\openclaw", "agents", "research")
analyst_path = os.path.join(r"C:\openclaw", "agents", "analyst")

# Import research tools
sys.path.insert(0, research_path)
import tools as research_tools
sys.path.remove(research_path)

# Import analyst tools
sys.path.insert(0, analyst_path)
import tools as analyst_tools
sys.path.remove(analyst_path)


def query_through_agent(question: str) -> Dict[str, Any]:
    """Route query through appropriate agent and return response in RagPipeline format."""
    # Determine which agent should handle this
    agent = route_task(question)
    
    if agent == "research":
        result = research_tools.research_query(question)
        # Convert to RagPipeline format
        return {
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "context": [],  # Not available from agent
            "latency": result.get("timing", {}).get("total_time", 0)
        }
    elif agent == "analyst":
        result = analyst_tools.analyze_with_rag(question)
        return {
            "answer": result.get("analysis", ""),
            "sources": result.get("sources", []),
            "context": [],
            "latency": result.get("timing", {}).get("total_time", 0)
        }
    else:
        # For other agents, fall back to direct RAG
        service = get_rag_service()
        response = service.query(question)
        return {
            "answer": response.answer,
            "sources": response.sources,
            "context": [],
            "latency": response.total_time
        }


def run_agent_eval(queries_file: str = "tests/eval_queries.json", report_file: str = None) -> Dict[str, Any]:
    """Run evaluation through agents using baseline validation."""
    if report_file is None:
        report_file = f"reports/agent_eval_baseline_{int(time.time())}.json"
    
    # Load queries
    with open(queries_file, 'r', encoding='utf-8') as f:
        queries = json.load(f)
    
    results = []
    passed = 0
    failed = 0
    errors = 0
    
    print(f"Running {len(queries)} queries through agents with baseline validation...")
    
    for i, query_data in enumerate(queries, 1):
        query = query_data["question"]
        expected_exact = query_data.get("expected_exact", "")
        expected_terms = query_data.get("expected_terms", [])
        forbidden_terms = query_data.get("forbidden_terms", [])
        expected_source = query_data.get("expected_source", "")
        suite = query_data.get("suite", "unknown")
        
        print(f"[{i}/{len(queries)}] {query}")
        
        try:
            start_time = time.perf_counter()
            response = query_through_agent(query)
            end_time = time.perf_counter()
            
            answer = response["answer"]
            sources = response["sources"]
            
            # Normalize query and answer for evaluation
            query_norm = normalize_arabic(query)
            answer_norm = normalize_arabic(answer)
            
            # Apply answer normalization
            answer_norm = normalize_terms(answer_norm, query_norm)
            
            # Enforce English-only for Arabic queries
            if "arabic" in suite or any('\u0600' <= c <= '\u06FF' for c in query):
                answer_norm = enforce_english_only(answer_norm)
            
            # Evaluate using baseline logic
            eval_result = evaluate_answer(
                query_norm,
                answer_norm,
                sources,
                expected_exact,
                expected_terms,
                forbidden_terms,
                expected_source
            )
            
            # Add timing and agent info
            eval_result["latency"] = end_time - start_time
            eval_result["agent"] = route_task(query)
            eval_result["suite"] = suite
            
            status = "✓ PASS" if eval_result["passed"] else "✗ FAIL"
            print(f"  {status}")
            print(f"  Answer ({eval_result['latency']:.2f}s): {answer[:100]}...")
            print(f"  Sources: {sources[:3]}")  # Show first 3 sources
            
            if not eval_result["passed"]:
                print(f"  Reasons: {eval_result['reasons']}")
                failed += 1
            else:
                passed += 1
            
            results.append(eval_result)
            
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            errors += 1
            results.append({
                "query": query,
                "passed": False,
                "error": str(e),
                "reasons": ["error"],
                "agent": route_task(query),
                "suite": suite,
                "latency": 0
            })
    
    # Calculate metrics using baseline logic
    total = len(queries)
    pass_rate = (passed / total) * 100
    
    # Source match accuracy
    source_matches = sum(1 for r in results if r.get("source_match", False))
    source_match_acc = (source_matches / total) * 100 if total > 0 else 0
    
    # Top-1 source accuracy
    top1_matches = sum(1 for r in results if r.get("top1_source_match", False))
    top1_source_acc = (top1_matches / total) * 100 if total > 0 else 0
    
    # Source precision
    source_precision = source_match_acc / 100 if pass_rate > 0 else 0
    
    # Refusal accuracy
    refusals = [r for r in results if r.get("is_refusal", False)]
    refusal_acc = sum(1 for r in refusals if r.get("passed", False)) / len(refusals) * 100 if refusals else 100
    
    # Average latency
    avg_latency = sum(r.get("latency", 0) for r in results if "latency" in r) / total
    
    # Failure buckets
    failure_buckets = {}
    for result in results:
        if not result.get("passed", False):
            for reason in result.get("reasons", []):
                failure_buckets[reason] = failure_buckets.get(reason, 0) + 1
    
    # Agent distribution
    agent_counts = {}
    for result in results:
        agent = result.get("agent", "unknown")
        agent_counts[agent] = agent_counts.get(agent, 0) + 1
    
    summary = {
        "metrics": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": pass_rate / 100,
            "source_match_accuracy": source_match_acc / 100,
            "top1_source_accuracy": top1_source_acc / 100,
            "source_precision": source_precision,
            "refusal_accuracy": refusal_acc / 100,
            "failure_buckets": failure_buckets,
            "avg_elapsed_s": avg_latency
        },
        "agent_distribution": agent_counts,
        "results": results
    }
    
    # Save report
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n============================================================")
    print(f"  Pass rate:            {pass_rate:.1f}%  ({passed}/{total})")
    print(f"  Source match acc:     {source_match_acc:.1f}%")
    print(f"  Top-1 source acc:     {top1_source_acc:.1f}%")
    print(f"  Source precision:     {source_precision:.2f}")
    print(f"  Refusal accuracy:   {refusal_acc:.1f}%")
    print(f"  Errors:             {errors}")
    print(f"  Failure buckets:    {failure_buckets}")
    print(f"  Avg latency:        {avg_latency:.2f}s")
    print(f"  Agent distribution: {agent_counts}")
    print(f"============================================================")
    print(f"Report saved → {report_file}")
    
    return summary


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run evaluation through agents with baseline validation")
    parser.add_argument("--queries", default="tests/eval_queries.json", help="Queries file")
    parser.add_argument("--report", help="Report file path")
    
    args = parser.parse_args()
    
    run_agent_eval(args.queries, args.report)
