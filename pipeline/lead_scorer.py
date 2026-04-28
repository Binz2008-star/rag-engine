"""
Lead Scorer - 6-dimension scoring (0-100) for ECO Technology leads.
"""
from typing import Dict, Any, Optional
import re


class LeadScorer:
    """Scores leads across 6 dimensions with RAG confidence bonus."""

    # Canonical schema - required fields for scoring
    REQUIRED_FIELDS = [
        "services_required",
        "company_name",
        "location",
        "source",
    ]

    # Optional fields (message is minor signal only)
    OPTIONAL_FIELDS = [
        "message",
        "email",
        "full_name",
        "phone",
    ]

    # Scoring weights (max 100)
    WEIGHTS = {
        'urgency': 35,
        'service_type': 20,
        'company_type': 18,
        'emirate': 15,
        'source': 15,
        'rag_bonus': 10,  # Bonus for high RAG confidence
    }

    # Urgency keywords (35 max)
    URGENCY_HIGH = ['urgent', 'asap', 'emergency', 'immediate', 'today', 'critical']
    URGENCY_MED = ['this week', 'soon', 'quickly', 'fast', 'tomorrow']
    URGENCY_LOW = ['next week', 'next month', 'planning', 'considering', 'quote']

    # High-value service types (20 max)
    HIGH_VALUE_SERVICES = ['grease trap', 'waste management', 'sewage', 'tank cleaning']
    MEDIUM_VALUE_SERVICES = ['jetting', 'drain cleaning', 'pumping']

    # Company types (18 max)
    HIGH_VALUE_COMPANIES = ['hotel', 'restaurant', 'hospital', 'clinic', 'mall', 'supermarket']
    MEDIUM_VALUE_COMPANIES = ['factory', 'warehouse', 'office', 'building']

    # Emirates (15 max)
    EMIRATE_PRIORITY = {
        'dubai': 15,
        'abu dhabi': 12,
        'sharjah': 10,
        'ajman': 8,
        'ras al khaimah': 7,
        'fujairah': 7,
        'umm al quwain': 5,
    }

    # Source quality (15 max)
    SOURCE_PRIORITY = {
        'jotform-ai-agent': 15,
        'website': 12,
        'referral': 14,
        'google': 10,
        'social_media': 8,
        'cold_call': 5,
    }

    def __init__(self):
        self.max_score = 100

    def score(self, lead_data: Dict[str, Any], rag_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculate lead score 0-100 across 6 dimensions.

        Args:
            lead_data: Lead information with fields like services_required, company_name, location, etc.
            rag_result: Optional RAG classification result with intent and confidence

        Returns:
            Dict with score breakdown, total score, band, and recommended action
        """
        scores = {
            'urgency': self._score_urgency(lead_data),
            'service_type': self._score_service_type(lead_data),
            'company_type': self._score_company_type(lead_data),
            'emirate': self._score_emirate(lead_data),
            'source': self._score_source(lead_data),
            'rag_bonus': 0,
        }

        # Calculate weighted scores
        weighted_scores = {
            'urgency': (scores['urgency'] / 100) * self.WEIGHTS['urgency'],
            'service_type': (scores['service_type'] / 100) * self.WEIGHTS['service_type'],
            'company_type': (scores['company_type'] / 100) * self.WEIGHTS['company_type'],
            'emirate': (scores['emirate'] / 100) * self.WEIGHTS['emirate'],
            'source': (scores['source'] / 100) * self.WEIGHTS['source'],
            'rag_bonus': 0,
        }

        # Add RAG confidence bonus if available
        if rag_result and rag_result.get('confidence', 0) >= 0.8:
            weighted_scores['rag_bonus'] = self.WEIGHTS['rag_bonus']
            scores['rag_bonus'] = 100

        total_score = int(sum(weighted_scores.values()))
        band = self._get_band(total_score)

        return {
            'lead_score': total_score,
            'score_band': band,
            'scores': scores,
            'weighted_scores': weighted_scores,
            'recommended_action': self._get_recommended_action(band, lead_data),
        }

    def _score_urgency(self, lead_data: Dict[str, Any]) -> int:
        """Score urgency 0-100 based on message (minor signal) and field completeness."""
        text = self._extract_text(lead_data).lower()

        # Check for high urgency signals (message is minor signal, max 5 points)
        urgency_bonus = 0
        if any(kw in text for kw in self.URGENCY_HIGH):
            urgency_bonus = 5
        elif any(kw in text for kw in self.URGENCY_MED):
            urgency_bonus = 3
        elif any(kw in text for kw in self.URGENCY_LOW):
            urgency_bonus = 1

        # Base score from form completeness (required fields)
        required_fields = ['email', 'phone', 'company_name']
        filled = sum(1 for f in required_fields if lead_data.get(f))
        base_score = 20 + (filled * 15)  # 20-65 based on completeness

        # Add message bonus (minor signal only)
        return min(base_score + urgency_bonus, 100)

    def _score_service_type(self, lead_data: Dict[str, Any]) -> int:
        """Score service type 0-100."""
        services = lead_data.get('services_required', [])
        if isinstance(services, str):
            services = [services]

        services_text = ' '.join(services).lower()

        # Check for high-value services
        if any(svc in services_text for svc in self.HIGH_VALUE_SERVICES):
            return 100
        if any(svc in services_text for svc in self.MEDIUM_VALUE_SERVICES):
            return 70

        # Any service is better than none
        return 40 if services else 0

    def _score_company_type(self, lead_data: Dict[str, Any]) -> int:
        """Score company type 0-100."""
        company = lead_data.get('company_name', '').lower()

        if any(ct in company for ct in self.HIGH_VALUE_COMPANIES):
            return 100
        if any(ct in company for ct in self.MEDIUM_VALUE_COMPANIES):
            return 70

        # Has a company name
        return 50 if company else 0

    def _score_emirate(self, lead_data: Dict[str, Any]) -> int:
        """Score emirate/location 0-100."""
        location = lead_data.get('location', '').lower()

        for emirate, score in self.EMIRATE_PRIORITY.items():
            if emirate in location:
                # Normalize to 0-100 scale
                return int((score / 15) * 100)

        return 50  # Default if location unknown

    def _score_source(self, lead_data: Dict[str, Any]) -> int:
        """Score lead source 0-100."""
        source = lead_data.get('source', '').lower()

        for src, score in self.SOURCE_PRIORITY.items():
            if src in source:
                return int((score / 15) * 100)

        return 50  # Default source score

    def _get_band(self, score: int) -> str:
        """Convert score to band."""
        if score >= 80:
            return 'HOT'
        elif score >= 60:
            return 'WARM'
        elif score >= 40:
            return 'MEDIUM'
        else:
            return 'COLD'

    def _get_recommended_action(self, band: str, lead_data: Dict[str, Any]) -> str:
        """Generate recommended action based on band and lead data."""
        actions = {
            'HOT': 'Call within 1 hour - High urgency/service fit',
            'WARM': 'Call within 2 hours - Good potential, quick follow-up',
            'MEDIUM': 'Email proposal within 4 hours, schedule call',
            'COLD': 'Add to nurture campaign, weekly check-in',
        }
        return actions.get(band, 'Review and categorize')

    def _extract_text(self, lead_data: Dict[str, Any]) -> str:
        """Extract all text from lead for analysis."""
        text_parts = []
        for key in ['message', 'notes', 'services_required', 'company_name']:
            val = lead_data.get(key, '')
            if isinstance(val, list):
                text_parts.extend(val)
            elif val:
                text_parts.append(str(val))
        return ' '.join(text_parts)


# Singleton instance
_scorer: Optional[LeadScorer] = None


def get_scorer() -> LeadScorer:
    """Get or create singleton LeadScorer."""
    global _scorer
    if _scorer is None:
        _scorer = LeadScorer()
    return _scorer
