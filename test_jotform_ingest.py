"""Tests for Jotform webhook ingestion service."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add api/server to path for imports
import sys
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from api.server.services.jotform_ingest_service import (
    JotformLead,
    _classify_intent,
    format_jotform_memory,
    ingest_jotform_payload,
    normalize_jotform_payload,
    save_jotform_memory,
)


class TestNormalizeJotformPayload:
    """Test payload normalization."""

    def test_normalizes_name_email_phone_message(self):
        """Test that payload normalizes name, email, phone, and message fields."""
        payload = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "+971500000000",
            "message": "Test message",
        }

        lead = normalize_jotform_payload(payload)

        assert lead.name == "John Doe"
        assert lead.email == "john@example.com"
        assert lead.phone == "+971500000000"
        assert lead.message == "Test message"
        assert lead.source == "jotform"
        assert lead.lead_id  # Should be generated
        assert lead.form_id == ""
        assert lead.submission_id == ""

    def test_handles_alternative_field_names(self):
        """Test that alternative field names are mapped correctly."""
        payload = {
            "visitor_name": "Jane Smith",
            "visitor_email": "jane@example.com",
            "visitor_phone": "+971555555555",
            "fullName": "Should not override visitor_name",
        }

        lead = normalize_jotform_payload(payload)

        assert lead.name == "Jane Smith"  # First match wins
        assert lead.email == "jane@example.com"
        assert lead.phone == "+971555555555"

    def test_handles_missing_fields_gracefully(self):
        """Test that missing fields default to empty strings."""
        payload = {"name": "Only Name"}

        lead = normalize_jotform_payload(payload)

        assert lead.name == "Only Name"
        assert lead.email == ""
        assert lead.phone == ""
        assert lead.company == ""
        assert lead.service == ""
        assert lead.location == ""
        assert lead.urgency == ""
        assert lead.message == ""


class TestClassifyIntent:
    """Test intent classification logic."""

    def test_eco_intent_from_wastewater(self):
        """Test eco intent detected from wastewater keyword."""
        assert _classify_intent("wastewater maintenance", "") == "eco"

    def test_eco_intent_from_grease(self):
        """Test eco intent detected from grease keyword."""
        assert _classify_intent("", "Need grease trap cleaning") == "eco"

    def test_eco_intent_from_waste(self):
        """Test eco intent detected from waste keyword."""
        assert _classify_intent("waste management", "") == "eco"

    def test_eco_intent_from_municipality(self):
        """Test eco intent detected from municipality keyword."""
        assert _classify_intent("", "Municipality services") == "eco"

    def test_eco_intent_from_environmental(self):
        """Test eco intent detected from environmental keyword."""
        assert _classify_intent("environmental consulting", "") == "eco"

    def test_cv_intent_from_resume(self):
        """Test cv intent detected from resume keyword."""
        assert _classify_intent("", "Send my resume") == "cv"

    def test_cv_intent_from_job(self):
        """Test cv intent detected from job keyword."""
        assert _classify_intent("job application", "") == "cv"

    def test_cv_intent_from_career(self):
        """Test cv intent detected from career keyword."""
        assert _classify_intent("", "Career opportunities") == "cv"

    def test_cv_intent_from_deliveroo(self):
        """Test cv intent detected from deliveroo keyword."""
        assert _classify_intent("deliveroo driver", "") == "cv"

    def test_general_intent_fallback(self):
        """Test general intent as fallback."""
        assert _classify_intent("general inquiry", "Just asking") == "general"


class TestFormatJotformMemory:
    """Test memory text formatting."""

    def test_memory_text_contains_source_fields(self):
        """Test that formatted memory contains all source fields."""
        lead = JotformLead(
            lead_id="test-id",
            form_id="form-123",
            submission_id="sub-456",
            name="Test Name",
            email="test@example.com",
            phone="+971500000000",
            company="Test Company",
            service="Test Service",
            location="Dubai",
            urgency="high",
            message="Test message",
            intent="eco",
            raw_payload={"name": "Test Name", "email": "test@example.com"},
        )

        memory_text = format_jotform_memory(lead)

        assert "[Jotform Lead]" in memory_text
        assert "Name: Test Name" in memory_text
        assert "Email: test@example.com" in memory_text
        assert "Phone: +971500000000" in memory_text
        assert "Company: Test Company" in memory_text
        assert "Service: Test Service" in memory_text
        assert "Location: Dubai" in memory_text
        assert "Urgency: high" in memory_text
        assert "Intent: eco" in memory_text
        assert "Message: Test message" in memory_text
        assert "Raw summary:" in memory_text


class TestSaveJotformMemory:
    """Test memory file storage."""

    def test_saves_memory_to_file(self):
        """Test that memory is saved to file correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_dir = Path(tmpdir)
            lead = JotformLead(
                lead_id="test-lead-id",
                form_id="form-123",
                submission_id="sub-456",
                name="Test",
                email="test@example.com",
                phone="+971500000000",
                company="Test Co",
                service="Test Service",
                location="Dubai",
                urgency="high",
                message="Test message",
                intent="eco",
                raw_payload={"name": "Test"},
            )

            file_path = save_jotform_memory(lead, memory_dir)

            assert file_path.exists()
            assert file_path.name == "test-lead-id.txt"
            content = file_path.read_text(encoding="utf-8")
            assert "[Jotform Lead]" in content
            assert "Test" in content


class TestIngestJotformPayload:
    """Test end-to-end ingestion."""

    def test_empty_payload_rejected(self):
        """Test that empty payload is rejected."""
        with pytest.raises(ValueError, match="Payload must be a non-empty dictionary"):
            ingest_jotform_payload({})

    def test_invalid_payload_rejected(self):
        """Test that invalid payload type is rejected."""
        with pytest.raises(ValueError, match="Payload must be a non-empty dictionary"):
            ingest_jotform_payload(None)

        with pytest.raises(ValueError, match="Payload must be a non-empty dictionary"):
            ingest_jotform_payload([])

    def test_raw_payload_preserved(self):
        """Test that raw payload is preserved in lead."""
        payload = {
            "name": "Test",
            "email": "test@example.com",
            "custom_field": "custom_value",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            memory_dir = Path(tmpdir)

            # Mock database save to avoid requiring DATABASE_URL
            with patch("api.server.services.jotform_ingest_service.save_jotform_lead"):
                lead = ingest_jotform_payload(payload, memory_dir=memory_dir)

            assert lead.raw_payload is not None
            assert lead.raw_payload["name"] == "Test"
            assert lead.raw_payload["custom_field"] == "custom_value"

    def test_database_save_called(self):
        """Test that database save is called during ingestion."""
        payload = {
            "name": "Test",
            "email": "test@example.com",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            memory_dir = Path(tmpdir)

            with patch("api.server.services.jotform_ingest_service.save_jotform_lead") as mock_save:
                ingest_jotform_payload(payload, memory_dir=memory_dir)

                mock_save.assert_called_once()

    def test_memory_file_saved(self):
        """Test that memory file is saved during ingestion."""
        payload = {
            "name": "Test",
            "email": "test@example.com",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            memory_dir = Path(tmpdir)

            with patch("api.server.services.jotform_ingest_service.save_jotform_lead"):
                lead = ingest_jotform_payload(payload, memory_dir=memory_dir)

            expected_file = memory_dir / f"{lead.lead_id}.txt"
            assert expected_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
