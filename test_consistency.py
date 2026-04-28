from lead_scorer import get_scorer

scorer = get_scorer()

# API format test
api_lead = {
    'services_required': ['grease trap', 'waste management'],
    'company_name': 'Test Restaurant',
    'location': 'Dubai',
    'source': 'jotform-ai-agent',
    'message': 'Restaurant grease trap emergency, 5 locations Dubai',
}
rag_result = {'intent': 'eco', 'confidence': 0.9, 'method': 'api_direct'}

result = scorer.score(api_lead, rag_result)
print(f"API Score: {result['lead_score']}, Band: {result['score_band']}")
print(f"Action: {result['recommended_action']}")
print(f"Breakdown: {result['scores']}")

# Backfill format test (same LeadScorer)
backfill_lead = {
    'services_required': ['grease trap', 'waste management'],
    'company_name': 'Test Restaurant',
    'location': 'Dubai',
    'source': 'jotform-ai-agent',
    'full_name': 'Test User',
    'email': 'test@example.com',
}

result2 = scorer.score(backfill_lead, rag_result)
print(f"\nBackfill Score: {result2['lead_score']}, Band: {result2['score_band']}")
print(f"Consistent: {result['lead_score'] == result2['lead_score']}")
