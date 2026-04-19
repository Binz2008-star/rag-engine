"""Unit tests for KnowledgeGapAnalyzer"""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

from analysis.knowledge_gap import KnowledgeGapAnalyzer, _VALID_GAP_TYPES, _FALLBACK
from app.models import KnowledgeGap


def test_knowledge_gap_analyzer_cache():
    """Test that caching works - same query should not call LLM twice."""
    mock_llm = Mock()
    analyzer = KnowledgeGapAnalyzer(mock_llm)
    
    # Mock the _run method to track calls
    original_run = analyzer._run
    call_count = [0]
    
    def mock_run(query, intent, normalized_query):
        call_count[0] += 1
        return original_run(query, intent, normalized_query)
    
    analyzer._run = mock_run
    
    # Patch LLM call to return valid JSON
    with patch('analysis.knowledge_gap.requests.post') as mock_post:
        mock_post.return_value.json.return_value = {
            "message": {
                "content": '{"gap_type": "missing_information", "confidence_if_adversarial": 0.5, "suggested_action": "add_docs"}'
            }
        }
        
        # First call
        result1 = analyzer.analyze("test query", "cv", "test query")
        assert call_count[0] == 1
        
        # Second call with same parameters - should hit cache
        result2 = analyzer.analyze("test query", "cv", "test query")
        assert call_count[0] == 1  # Should still be 1, not 2
        
        # Different query - should call LLM again
        result3 = analyzer.analyze("different query", "cv", "different query")
        assert call_count[0] == 2
        
        assert result1.gap_type == result2.gap_type
        assert result1 == result2


def test_knowledge_gap_analyzer_parse_valid_json():
    """Test parsing of valid JSON response."""
    mock_llm = Mock()
    analyzer = KnowledgeGapAnalyzer(mock_llm)
    
    valid_json = '{"gap_type": "missing_information", "confidence_if_adversarial": 0.75, "suggested_action": "add_documents_on_X"}'
    result = analyzer._parse(valid_json)
    
    assert result.gap_type == "missing_information"
    assert result.confidence_if_adversarial == 0.75
    assert result.suggested_action == "add_documents_on_X"


def test_knowledge_gap_analyzer_parse_json_with_extra_text():
    """Test parsing JSON when response has extra text."""
    mock_llm = Mock()
    analyzer = KnowledgeGapAnalyzer(mock_llm)
    
    response = "Here's the analysis: {\"gap_type\": \"terminology_mismatch\", \"confidence_if_adversarial\": 0.3, \"suggested_action\": \"clarify_terminology\"} Done."
    result = analyzer._parse(response)
    
    assert result.gap_type == "terminology_mismatch"
    assert result.confidence_if_adversarial == 0.3
    assert result.suggested_action == "clarify_terminology"


def test_knowledge_gap_analyzer_parse_invalid_json():
    """Test fallback on invalid JSON."""
    mock_llm = Mock()
    analyzer = KnowledgeGapAnalyzer(mock_llm)
    
    invalid_json = "not valid json at all"
    result = analyzer._parse(invalid_json)
    
    assert result == _FALLBACK


def test_knowledge_gap_analyzer_parse_invalid_gap_type():
    """Test fallback on invalid gap_type."""
    mock_llm = Mock()
    analyzer = KnowledgeGapAnalyzer(mock_llm)
    
    json_with_invalid_type = '{"gap_type": "invalid_type", "confidence_if_adversarial": 0.5, "suggested_action": "add_docs"}'
    result = analyzer._parse(json_with_invalid_type)
    
    assert result.gap_type == "missing_information"  # Should fallback to default


def test_knowledge_gap_analyzer_confidence_clamping():
    """Test that confidence is clamped to [0.0, 1.0]."""
    mock_llm = Mock()
    analyzer = KnowledgeGapAnalyzer(mock_llm)
    
    # Test > 1.0
    json_high = '{"gap_type": "missing_information", "confidence_if_adversarial": 1.5, "suggested_action": "add_docs"}'
    result = analyzer._parse(json_high)
    assert result.confidence_if_adversarial == 1.0
    
    # Test < 0.0
    json_low = '{"gap_type": "missing_information", "confidence_if_adversarial": -0.5, "suggested_action": "add_docs"}'
    result = analyzer._parse(json_low)
    assert result.confidence_if_adversarial == 0.0


def test_valid_gap_types():
    """Test that _VALID_GAP_TYPES contains expected values."""
    expected = {
        "missing_information",
        "terminology_mismatch",
        "scope_out_of_bounds",
        "ambiguous_query",
        "temporal_mismatch",
    }
    assert _VALID_GAP_TYPES == expected


def test_fallback_structure():
    """Test that _FALLBACK has correct structure."""
    assert isinstance(_FALLBACK, KnowledgeGap)
    assert _FALLBACK.gap_type == "missing_information"
    assert _FALLBACK.confidence_if_adversarial == 0.0
    assert _FALLBACK.suggested_action == "add_relevant_documents"


def test_knowledge_gap_analyzer_llm_failure():
    """Test fallback when LLM call fails."""
    mock_llm = Mock()
    analyzer = KnowledgeGapAnalyzer(mock_llm)
    
    with patch('analysis.knowledge_gap.requests.post') as mock_post:
        mock_post.side_effect = Exception("LLM connection failed")
        
        result = analyzer._run("test", "cv", "test")
        
        assert result == _FALLBACK


if __name__ == "__main__":
    test_knowledge_gap_analyzer_cache()
    test_knowledge_gap_analyzer_parse_valid_json()
    test_knowledge_gap_analyzer_parse_json_with_extra_text()
    test_knowledge_gap_analyzer_parse_invalid_json()
    test_knowledge_gap_analyzer_parse_invalid_gap_type()
    test_knowledge_gap_analyzer_confidence_clamping()
    test_valid_gap_types()
    test_fallback_structure()
    test_knowledge_gap_analyzer_llm_failure()
    print("All tests passed!")
