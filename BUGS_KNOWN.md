# Known Bugs

## RAG Evaluation Issues

### Test 2: CV Tailored Role Regression
- **Issue**: CV tailored role detection has regressed
- **Impact**: Reduced accuracy for CV-related queries
- **Status**: Known, deferred to next phase

### Test 7: Contact Email Missing
- **Issue**: Contact email information not being retrieved/returned
- **Impact**: Missing critical contact information in responses
- **Status**: Known, deferred to next phase

### Arabic Tests 21-23: Over-Refusal
- **Issue**: Arabic language queries being over-refused
- **Impact**: Reduced service quality for Arabic users
- **Status**: Known, deferred to next phase

### High Latency
- **Issue**: Some eval cases exhibit high latency
- **Impact**: Poor user experience on slow queries
- **Status**: Known, deferred to next phase

## Notes

- These bugs are accepted as "good enough for next phase"
- No further modifications to retriever/generation layers until deployment validation complete
- Focus shifted to Render/runtime validation
