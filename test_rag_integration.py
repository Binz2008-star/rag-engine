"""
Test script for RAG integration with Robin AI.
Tests service and compliance queries to validate the integration.
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from rag_client import RAGClient, get_rag_client, is_service_or_compliance_query, get_rag_usage_stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Test queries covering different intents
TEST_QUERIES = [
    # Service enquiries (INT-02)
    {
        "query": "What services does ECO Technology offer?",
        "expected_intent": "eco",
        "category": "service_enquiry"
    },
    {
        "query": "Tell me about grease trap cleaning",
        "expected_intent": "eco",
        "category": "service_enquiry"
    },
    {
        "query": "How does biological treatment work?",
        "expected_intent": "eco",
        "category": "service_enquiry"
    },
    {
        "query": "What is UCO recycling?",
        "expected_intent": "eco",
        "category": "service_enquiry"
    },
    
    # Compliance concerns (INT-03)
    {
        "query": "What are the municipality requirements for grease traps?",
        "expected_intent": "eco",
        "category": "compliance_concern"
    },
    {
        "query": "What are the fines for non-compliance?",
        "expected_intent": "eco",
        "category": "compliance_concern"
    },
    {
        "query": "Is ECO Technology municipality approved?",
        "expected_intent": "eco",
        "category": "compliance_concern"
    },
    {
        "query": "What certifications does ECO Technology have?",
        "expected_intent": "eco",
        "category": "compliance_concern"
    },
    
    # Company info (INT-09)
    {
        "query": "When was ECO Technology established?",
        "expected_intent": "eco",
        "category": "company_info"
    },
    {
        "query": "How many clients does ECO Technology have?",
        "expected_intent": "eco",
        "category": "company_info"
    },
    
    # Documentation request (INT-18)
    {
        "query": "Do you provide service certificates?",
        "expected_intent": "eco",
        "category": "documentation_request"
    },
]


def test_query_classification():
    """Test the query classification logic."""
    logger.info("\n=== Testing Query Classification ===\n")
    
    for test in TEST_QUERIES:
        query = test["query"]
        should_route = is_service_or_compliance_query(query)
        
        logger.info(f"Query: {query}")
        logger.info(f"  Should route to RAG: {should_route}")
        logger.info(f"  Category: {test['category']}")
        logger.info("")
    
    logger.info("✓ Query classification tests complete\n")


def test_rag_queries():
    """Test actual RAG queries."""
    logger.info("\n=== Testing RAG Queries ===\n")
    
    client = get_rag_client()
    
    # Test health check first
    logger.info("Testing RAG service health...")
    is_healthy = client.health_check()
    logger.info(f"RAG service healthy: {is_healthy}")
    
    if not is_healthy:
        logger.error("RAG service is not healthy. Skipping query tests.")
        return
    
    logger.info("")
    
    # Run a subset of test queries
    test_subset = TEST_QUERIES[:5]  # Test first 5 queries
    
    for i, test in enumerate(test_subset, 1):
        query = test["query"]
        logger.info(f"Test {i}/{len(test_subset)}: {query}")
        
        try:
            result = client.query(query, caller="test_script")
            
            logger.info(f"  Intent: {result.get('intent')}")
            logger.info(f"  Confidence: {result.get('intent_confidence')}")
            logger.info(f"  Sources: {len(result.get('sources', []))}")
            logger.info(f"  Answer length: {len(result.get('answer', ''))}")
            logger.info(f"  Retrieval time: {result.get('retrieval_time', 0):.3f}s")
            logger.info(f"  Generation time: {result.get('generation_time', 0):.3f}s")
            
            # Check if answer is grounded
            answer = result.get('answer', '')
            if answer and answer != "Insufficient data.":
                logger.info(f"  Answer preview: {answer[:150]}...")
            
            logger.info("")
            
        except Exception as e:
            logger.error(f"  Query failed: {e}")
            logger.info("")
    
    # Show usage stats
    logger.info("=== RAG Usage Statistics ===\n")
    stats = get_rag_usage_stats()
    logger.info(f"Total queries: {stats['total_queries']}")
    logger.info(f"Successful: {stats['successful']}")
    logger.info(f"Failed: {stats['failed']}")
    logger.info(f"Success rate: {stats['success_rate']:.2%}")
    logger.info(f"Average response time: {stats['avg_response_time']:.3f}s")
    logger.info(f"Intent distribution: {stats['intent_distribution']}")
    logger.info(f"Caller distribution: {stats['caller_distribution']}")
    
    logger.info("\n✓ RAG query tests complete\n")


def main():
    """Run all tests."""
    logger.info("Starting RAG Integration Tests")
    logger.info("=" * 60)
    
    # Test 1: Query classification
    test_query_classification()
    
    # Test 2: RAG queries (requires RAG service running)
    logger.info("Note: RAG query tests require RAG service running on http://localhost:8001")
    logger.info("Start the service with: python rag_service.py")
    logger.info("")
    
    try:
        test_rag_queries()
    except Exception as e:
        logger.error(f"RAG query tests failed (service may not be running): {e}")
        logger.info("Start the RAG service and run this test again.")
    
    logger.info("=" * 60)
    logger.info("Integration tests complete")


if __name__ == "__main__":
    main()
