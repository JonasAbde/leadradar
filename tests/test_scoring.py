"""Tests for lead scoring logic."""

import pytest
from datetime import datetime, timedelta
from app.scoring import score_lead, _parse_date


class TestParseDate:
    """Test date parsing helper."""

    def test_iso_format(self):
        d = _parse_date("2024-03-15")
        assert d == datetime(2024, 3, 15)

    def test_compact_format(self):
        d = _parse_date("20240315")
        assert d == datetime(2024, 3, 15)

    def test_eu_format(self):
        d = _parse_date("15/03/2024")
        assert d == datetime(2024, 3, 15)

    def test_empty_string(self):
        assert _parse_date("") is None

    def test_none(self):
        assert _parse_date(None) is None

    def test_invalid(self):
        assert _parse_date("not-a-date") is None


class TestScoreLead:
    """Test score_lead with various inputs."""

    def test_empty_lead(self):
        score, reasons = score_lead({})
        assert 0 <= score <= 100
        assert "No strong signals" in reasons

    def test_country_match(self):
        lead = {"buyer_country": "DNK"}
        score, reasons = score_lead(lead, target_country="DNK")
        assert score >= 20
        assert any("Country match" in r for r in reasons)

    def test_country_mismatch(self):
        lead = {"buyer_country": "DEU"}
        score, reasons = score_lead(lead, target_country="DNK")
        assert not any("Country match" in r for r in reasons)

    def test_cpv_match(self):
        lead = {"cpv_values": ["72200000"]}
        score, reasons = score_lead(lead, cpv_codes=["72000000"])
        assert score >= 30
        assert any("CPV match" in r for r in reasons)

    def test_cpv_string_input(self):
        """CPV comes as JSON string from DB."""
        import json
        lead = {"cpv_values": json.dumps(["72200000", "45000000"])}
        score, reasons = score_lead(lead, cpv_codes=["72000000"])
        assert score >= 30

    def test_cpv_no_match(self):
        lead = {"cpv_values": ["99000000"]}
        score, reasons = score_lead(lead, cpv_codes=["72000000"])
        assert not any("CPV match" in r for r in reasons)

    def test_keyword_in_title(self):
        lead = {"title": "Software Development Platform"}
        score, reasons = score_lead(lead, keywords=["software"])
        assert score >= 10
        assert any("Keyword" in r for r in reasons)

    def test_keyword_no_match(self):
        lead = {"title": "Cleaning Services"}
        score, reasons = score_lead(lead, keywords=["software"])
        assert not any("Keyword" in r for r in reasons)

    def test_deadline_urgent(self):
        future = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        lead = {"deadline_date": future}
        score, reasons = score_lead(lead)
        assert score >= 25
        assert any("7 days" in r for r in reasons)

    def test_deadline_upcoming(self):
        future = (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%d")
        lead = {"deadline_date": future}
        score, reasons = score_lead(lead)
        assert score >= 15
        assert any("30 days" in r for r in reasons)

    def test_deadline_far(self):
        future = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        lead = {"deadline_date": future}
        _score, reasons = score_lead(lead)
        assert any("far out" in r for r in reasons)

    def test_has_estimated_value(self):
        lead = {"estimated_value": "500000"}
        score, reasons = score_lead(lead)
        assert score >= 5
        assert any("Estimated value" in r for r in reasons)

    def test_estimated_value_zero(self):
        lead = {"estimated_value": 0}
        score, reasons = score_lead(lead)
        assert not any("Estimated value" in r for r in reasons)

    def test_published_recently(self):
        past = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        lead = {"pub_date": past}
        score, reasons = score_lead(lead)
        assert score >= 10
        assert any("days ago" in r for r in reasons)

    def test_comprehensive_lead(self):
        """Score a lead with all signals present."""
        future = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        lead = {
            "buyer_country": "DNK",
            "cpv_values": ["72200000"],
            "title": "Software Development for Government",
            "deadline_date": future,
            "estimated_value": "100000",
            "pub_date": past,
        }
        score, reasons = score_lead(lead, cpv_codes=["72000000"], keywords=["software"])
        assert 0 < score <= 100
        assert len(reasons) >= 5

    def test_score_capped_at_100(self):
        """Ensure no score exceeds 100."""
        future = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        lead = {
            "buyer_country": "DNK",
            "cpv_values": ["72200000"],
            "title": "Software",
            "deadline_date": future,
            "estimated_value": "1000000",
            "pub_date": past,
        }
        score, _ = score_lead(lead, cpv_codes=["72000000"], keywords=["software"])
        assert score <= 100

    def test_case_insensitive_keywords(self):
        lead = {"title": "SOFTWARE Development"}
        score, reasons = score_lead(lead, keywords=["software"])
        assert any("Keyword" in r for r in reasons)

    def test_case_insensitive_country(self):
        lead = {"buyer_country": "dnk"}
        score, reasons = score_lead(lead, target_country="DNK")
        assert any("Country match" in r for r in reasons)
