"""Evaluation runner that routes queries through agents."""

import sys
import os
import time
import json
from typing import Dict, List, Any
from pathlib import Path

# Add openclaw to path
sys.path.insert(0, r"C:\openclaw")
from router import route_task

# Add assistant to path
sys.path.insert(0, r"D:\AI\assistant")
from app.rag_service import get_rag_service

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
    """Route query through appropriate agent and return response."""
    # Determine which agent should handle this
    agent = route_task(question)

    if agent == "research":
        result = research_tools.research_query(question)
        return {
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "is_refusal": result.get("metadata", {}).get("is_refusal", False)
        }
    elif agent == "analyst":
        result = analyst_tools.analyze_with_rag(question)
        return {
            "answer": result.get("analysis", ""),
            "sources": result.get("sources", []),
            "is_refusal": result.get("metadata", {}).get("is_refusal", False)
        }
    else:
        # For other agents, fall back to direct RAG
        service = get_rag_service()
        response = service.query(question)
        return {
            "answer": response.answer,
            "sources": response.sources,
            "is_refusal": response.is_refusal
        }


def run_agent_eval(queries_file: str = "eval_queries.json", report_file: str = None) -> Dict[str, Any]:
    """Run evaluation through agents."""
    if report_file is None:
        report_file = f"reports/agent_eval_{int(time.time())}.json"

    # Load queries
    with open(queries_file, 'r', encoding='utf-8') as f:
        queries = json.load(f)

    results = []
    passed = 0
    failed = 0

    print(f"Running {len(queries)} queries through agents...")

    for i, query_data in enumerate(queries, 1):
        query = query_data["question"]
        expected = query_data.get("expected_exact", "")

        print(f"[{i}/{len(queries)}] {query}")

        try:
            start_time = time.perf_counter()
            response = query_through_agent(query)
            end_time = time.perf_counter()

            answer = response["answer"]
            sources = response["sources"]
            is_refusal = response["is_refusal"]

            # Basic validation
            test_passed = True
            failure_reasons = []

            # Check if answer exists
            if not answer or len(answer.strip()) < 10:
                test_passed = False
                failure_reasons.append("answer too short")

            # Check sources
            if not sources:
                test_passed = False
                failure_reasons.append("no sources")

            # Check refusal format
            if is_refusal and answer != "Insufficient data.":
                test_passed = False
                failure_reasons.append("incorrect refusal format")

            # Check for Arabic in answer (should be English only)
            if any('\u0600' <= char <= '\u06FF' for char in answer):
                test_passed = False
                failure_reasons.append("contains Arabic text")

            status = "✓ PASS" if test_passed else "✗ FAIL"
            print(f"  {status}")
            print(f"  Answer ({end_time - start_time:.2f}s): {answer[:100]}...")
            print(f"  Sources: {sources}")

            if not test_passed:
                print(f"  Reasons: {', '.join(failure_reasons)}")
                failed += 1
            else:
                passed += 1

            results.append({
                "query": query,
                "answer": answer,
                "sources": sources,
                "is_refusal": is_refusal,
                "test_passed": test_passed,
                "failure_reasons": failure_reasons,
                "agent": route_task(query),
                "latency": end_time - start_time
            })

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failed += 1
            results.append({
                "query": query,
                "answer": f"Error: {str(e)}",
                "sources": [],
                "is_refusal": False,
                "test_passed": False,
                "failure_reasons": ["error"],
                "agent": route_task(query),
                "latency": 0
            })

    # Calculate metrics
    total = len(queries)
    pass_rate = (passed / total) * 100

    # Source match accuracy (simplified)
    source_matches = sum(1 for r in results if r["test_passed"] and r["sources"])
    source_match_acc = (source_matches / total) * 100

    # Average latency
    avg_latency = sum(r["latency"] for r in results) / total

    # Agent distribution
    agent_counts = {}
    for result in results:
        agent = result["agent"]
        agent_counts[agent] = agent_counts.get(agent, 0) + 1

    summary = {
        "total_queries": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
        "source_match_accuracy": source_match_acc,
        "avg_latency": avg_latency,
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
    print(f"  Avg latency:          {avg_latency:.2f}s")
    print(f"  Agent distribution:   {agent_counts}")
    print(f"============================================================")
    print(f"Report saved → {report_file}")

    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run evaluation through agents")
    parser.add_argument("--queries", default="eval_queries.json", help="Queries file")
    parser.add_argument("--report", help="Report file path")

    args = parser.parse_args()

    run_agent_eval(args.queries, args.report)
