"""Tests for TEDProvider normalization logic."""

import pytest
from app.ted_provider import TEDProvider, _extract_multilingual


class TestExtractMultilingual:
    """Test multilingual field extraction helper."""

    def test_english_preferred(self):
        d = {"eng": ["English title"], "dan": ["Dansk titel"]}
        assert _extract_multilingual(d) == "English title"

    def test_danish_fallback(self):
        d = {"dan": ["Dansk titel"], "deu": ["Deutscher Titel"]}
        assert _extract_multilingual(d, preferred_langs=["dan"]) == "Dansk titel"

    def test_empty_dict_returns_empty(self):
        assert _extract_multilingual({}) == ""

    def test_none_value(self):
        d = {"eng": None, "dan": []}
        assert _extract_multilingual(d) == ""

    def test_non_dict(self):
        assert _extract_multilingual("plain string") == "plain string"
        assert _extract_multilingual(None) == ""

    def test_first_available_fallback(self):
        d = {"zxx": ["Fallback value"]}
        assert _extract_multilingual(d) == "Fallback value"

    def test_list_value_extraction(self):
        d = {"eng": ["A", "B"]}
        assert _extract_multilingual(d) == "A"


class TestTEDProviderNormalization:
    """Test TEDProvider _normalize_notice method."""

    def setup_method(self):
        self.provider = TEDProvider()

    def _make_notice(self, overrides=None):
        """Create a minimal valid notice dict."""
        notice = {
            "publication-number": "2024/S 001-000001",
            "notice-identifier": "123456-2024",
            "notice-title": {"eng": ["Test Tender"]},
            "buyer-name": {"dan": ["Test Buyer"]},
            "buyer-country": ["DNK"],
            "publication-date": "2024-01-15",
            "dispatch-date": "2024-01-14",
            "notice-subtype": "contract",
            "notice-type": "notice",
            "procedure-type": "open",
            "legal-basis": "2014/24/EU",
        }
        if overrides:
            notice.update(overrides)
        return notice

    def test_normalize_valid_notice(self):
        notice = self._make_notice()
        result = self.provider._normalize_notice(notice)
        assert result is not None
        assert result["notice_id"] == "123456-2024"
        assert result["pub_number"] == "2024/S 001-000001"
        assert result["title"] == "Test Tender"
        assert result["buyer"] == "Test Buyer"
        assert result["buyer_country"] == "DNK"
        assert result["pub_date"] == "2024-01-15"
        assert result["subtype"] == "contract"
        assert result["procedure"] == "open"
        assert "ted.europa.eu" in result["url"]

    def test_normalize_missing_pub_number_returns_none(self):
        notice = self._make_notice({"publication-number": ""})
        assert self.provider._normalize_notice(notice) is None

    def test_normalize_missing_pub_number_none_returns_none(self):
        notice = self._make_notice({"publication-number": None})
        assert self.provider._normalize_notice(notice) is None

    def test_normalize_multilingual_title(self):
        notice = self._make_notice({
            "notice-title": {"dan": ["Dansk titel"], "eng": ["English title"]}
        })
        result = self.provider._normalize_notice(notice)
        assert result["title"] == "English title"

    def test_normalize_single_buyer_country(self):
        notice = self._make_notice({"buyer-country": ["DEU"]})
        result = self.provider._normalize_notice(notice)
        assert result["buyer_country"] == "DEU"

    def test_normalize_empty_buyer_country(self):
        notice = self._make_notice({"buyer-country": []})
        result = self.provider._normalize_notice(notice)
        assert result["buyer_country"] == ""

    def test_normalize_non_list_buyer_country(self):
        notice = self._make_notice({"buyer-country": "FRA"})
        result = self.provider._normalize_notice(notice)
        assert result["buyer_country"] == "FRA"


class TestExtractCountry:
    """Test _extract_country static method."""

    def test_list_input(self):
        assert TEDProvider._extract_country(["DNK"]) == "DNK"

    def test_empty_list(self):
        assert TEDProvider._extract_country([]) == ""

    def test_string_input(self):
        assert TEDProvider._extract_country("DEU") == "DEU"

    def test_none_input(self):
        assert TEDProvider._extract_country(None) == ""
