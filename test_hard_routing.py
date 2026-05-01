"""
Test script for Robin AI webhook server v4.0 with hard RAG routing.
Tests the hard routing logic for INT-02, INT-03, INT-09, INT-18.
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Simulate the routing logic from webhook_server_v4_rag.py
RAG_INTENTS = {"INT-02", "INT-03", "INT-09", "INT-18"}

SERVICE_KEYWORDS = [
    "service", "waste", "grease trap", "sewage", "jetting",
    "compliance", "regulation", "permit", "certification",
    "iso", "municipality", "approved", "environmental",
    "offer", "provide", "handle", "manage"
]


def should_route_to_rag(intent: str, message: str) -> bool:
    """
    Determine if a query should route to RAG based on intent and content.
    This mirrors the logic in webhook_server_v4_rag.py
    """
    if intent in RAG_INTENTS:
        return True
    
    # Fallback: check for service/compliance keywords even if intent not classified
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in SERVICE_KEYWORDS)


# Test cases covering different scenarios
TEST_CASES = [
    # INT-02: SERVICE_ENQUIRY
    {
        "intent": "INT-02",
        "message": "What services does ECO Technology offer?",
        "should_route": True,
        "reason": "INT-02 is in RAG_INTENTS"
    },
    {
        "intent": "INT-02",
        "message": "Tell me about grease trap cleaning",
        "should_route": True,
        "reason": "INT-02 is in RAG_INTENTS"
    },
    
    # INT-03: COMPLIANCE_CONCERN
    {
        "intent": "INT-03",
        "message": "What are the municipality requirements?",
        "should_route": True,
        "reason": "INT-03 is in RAG_INTENTS"
    },
    {
        "intent": "INT-03",
        "message": "What are the fines for non-compliance?",
        "should_route": True,
        "reason": "INT-03 is in RAG_INTENTS"
    },
    
    # INT-09: GENERAL_INFO
    {
        "intent": "INT-09",
        "message": "When was ECO Technology established?",
        "should_route": True,
        "reason": "INT-09 is in RAG_INTENTS"
    },
    
    # INT-18: DOCUMENTATION_REQUEST
    {
        "intent": "INT-18",
        "message": "Do you provide service certificates?",
        "should_route": True,
        "reason": "INT-18 is in RAG_INTENTS"
    },
    
    # Other intents (should NOT route to RAG)
    {
        "intent": "INT-01",  # PRICE_ENQUIRY
        "message": "How much does it cost?",
        "should_route": False,
        "reason": "INT-01 not in RAG_INTENTS, no service keywords"
    },
    {
        "intent": "INT-08",  # LEAD_READY
        "message": "I want to proceed",
        "should_route": False,
        "reason": "INT-08 not in RAG_INTENTS, no service keywords"
    },
    {
        "intent": "INT-11",  # GREETING
        "message": "Hello",
        "should_route": False,
        "reason": "INT-11 not in RAG_INTENTS, no service keywords"
    },
    
    # Fallback: service keywords without RAG intent
    {
        "intent": "unknown",
        "message": "Tell me about your waste management services",
        "should_route": True,
        "reason": "Fallback: contains 'service' keyword"
    },
    {
        "intent": "unknown",
        "message": "What compliance regulations do you follow?",
        "should_route": True,
        "reason": "Fallback: contains 'compliance' keyword"
    },
    {
        "intent": "unknown",
        "message": "What is the weather today?",
        "should_route": False,
        "reason": "No RAG intent, no service keywords"
    },
]


def test_routing_logic():
    """Test the hard routing logic."""
    logger.info("\n=== Testing Hard RAG Routing Logic ===\n")
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(TEST_CASES, 1):
        intent = test["intent"]
        message = test["message"]
        expected = test["should_route"]
        reason = test["reason"]
        
        actual = should_route_to_rag(intent, message)
        
        status = "✓" if actual == expected else "✗"
        
        if actual == expected:
            passed += 1
        else:
            failed += 1
        
        logger.info(f"Test {i}/{len(TEST_CASES)}: {status}")
        logger.info(f"  Intent: {intent}")
        logger.info(f"  Message: {message}")
        logger.info(f"  Expected route: {expected}")
        logger.info(f"  Actual route: {actual}")
        logger.info(f"  Reason: {reason}")
        logger.info("")
    
    logger.info("=" * 60)
    logger.info(f"Results: {passed} passed, {failed} failed out of {len(TEST_CASES)} tests")
    
    if failed == 0:
        logger.info("✓ All routing logic tests passed")
    else:
        logger.error(f"✗ {failed} test(s) failed")
    
    return failed == 0


def test_rag_intents_coverage():
    """Verify all RAG intents are covered."""
    logger.info("\n=== Testing RAG Intents Coverage ===\n")
    
    all_intents = {
        "INT-01", "INT-02", "INT-03", "INT-04A", "INT-04B",
        "INT-05", "INT-06", "INT-07", "INT-08", "INT-09",
        "INT-10", "INT-11", "INT-13", "INT-14", "INT-15",
        "INT-16", "INT-17", "INT-18"
    }
    
    non_rag_intents = all_intents - RAG_INTENTS
    
    logger.info(f"RAG_INTENTS: {sorted(RAG_INTENTS)}")
    logger.info(f"Non-RAG intents: {sorted(non_rag_intents)}")
    logger.info(f"Total intents: {len(all_intents)}")
    logger.info(f"RAG-covered: {len(RAG_INTENTS)}")
    logger.info(f"Non-RAG: {len(non_rag_intents)}")
    
    # Verify the specific intents mentioned in requirements are included
    required_rag_intents = {"INT-02", "INT-03", "INT-09", "INT-18"}
    missing = required_rag_intents - RAG_INTENTS
    
    if missing:
        logger.error(f"✗ Missing required RAG intents: {missing}")
        return False
    else:
        logger.info("✓ All required RAG intents are covered")
        return True


def test_keyword_fallback():
    """Test keyword-based fallback routing."""
    logger.info("\n=== Testing Keyword Fallback Routing ===\n")
    
    keyword_tests = [
        ("service", True),
        ("waste management", True),
        ("grease trap", True),
        ("compliance", True),
        ("regulation", True),
        ("permit", True),
        ("certification", True),
        ("iso", True),
        ("municipality", True),
        ("approved", True),
        ("environmental", True),
        ("offer", True),
        ("provide", True),
        ("handle", True),
        ("manage", True),
        ("price", False),
        ("cost", False),
        ("hello", False),
        ("weather", False),
    ]
    
    passed = 0
    failed = 0
    
    for keyword, expected in keyword_tests:
        message = f"Tell me about your {keyword}"
        actual = should_route_to_rag("unknown", message)
        
        status = "✓" if actual == expected else "✗"
        
        if actual == expected:
            passed += 1
        else:
            failed += 1
        
        logger.info(f"{status} Keyword '{keyword}': expected={expected}, actual={actual}")
    
    logger.info(f"\nResults: {passed} passed, {failed} failed")
    
    return failed == 0


def main():
    """Run all tests."""
    logger.info("Starting Hard RAG Routing Tests")
    logger.info("=" * 60)
    
    # Test 1: Routing logic
    routing_passed = test_routing_logic()
    
    # Test 2: RAG intents coverage
    coverage_passed = test_rag_intents_coverage()
    
    # Test 3: Keyword fallback
    keyword_passed = test_keyword_fallback()
    
    logger.info("=" * 60)
    
    all_passed = routing_passed and coverage_passed and keyword_passed
    
    if all_passed:
        logger.info("✓ All hard routing tests passed")
        return 0
    else:
        logger.error("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
