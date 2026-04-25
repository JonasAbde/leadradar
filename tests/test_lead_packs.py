"""Tests for lead packs structure and functions."""

import pytest
from app.lead_packs import LEAD_PACKS, get_pack, all_packs


class TestLeadPacksStructure:
    """Test LEAD_PACKS has valid structure."""

    def test_packs_not_empty(self):
        assert len(LEAD_PACKS) > 0

    def test_each_pack_has_required_fields(self):
        required = {"name", "cpv_codes", "keywords", "country"}
        for slug, pack in LEAD_PACKS.items():
            missing = required - set(pack.keys())
            assert not missing, f"Pack '{slug}' missing: {missing}"

    def test_pack_names_are_strings(self):
        for slug, pack in LEAD_PACKS.items():
            assert isinstance(pack["name"], str)
            assert len(pack["name"]) > 0

    def test_cpv_codes_are_list(self):
        for slug, pack in LEAD_PACKS.items():
            assert isinstance(pack["cpv_codes"], list)
            assert len(pack["cpv_codes"]) > 0
            for cpv in pack["cpv_codes"]:
                assert isinstance(cpv, str)
                assert len(cpv) > 0

    def test_keywords_are_list(self):
        for slug, pack in LEAD_PACKS.items():
            assert isinstance(pack["keywords"], list)
            assert len(pack["keywords"]) > 0
            for kw in pack["keywords"]:
                assert isinstance(kw, str)
                assert len(kw) > 0

    def test_country_is_valid_string(self):
        for slug, pack in LEAD_PACKS.items():
            assert isinstance(pack["country"], str)
            assert len(pack["country"]) == 3  # ISO 3166-1 alpha-3


class TestPacksExist:
    """Test expected packs exist."""

    def test_cleaning_facility_pack(self):
        pack = get_pack("cleaning_facility")
        assert pack is not None
        assert "cleaning" in [kw.lower() for kw in pack["keywords"]]

    def test_it_software_pack(self):
        pack = get_pack("it_software")
        assert pack is not None
        assert "software" in [kw.lower() for kw in pack["keywords"]]

    def test_construction_pack(self):
        pack = get_pack("construction")
        assert pack is not None
        assert any("construction" in kw.lower() for kw in pack["keywords"])

    def test_consulting_pack(self):
        pack = get_pack("consulting")
        assert pack is not None
        assert any("consulting" in kw.lower() for kw in pack["keywords"])


class TestGetPack:
    """Test get_pack function."""

    def test_get_valid_pack(self):
        pack = get_pack("it_software")
        assert pack == LEAD_PACKS["it_software"]

    def test_get_invalid_pack(self):
        assert get_pack("nonexistent") is None

    def test_all_packs_returns_dict(self):
        packs = all_packs()
        assert isinstance(packs, dict)
        assert len(packs) == len(LEAD_PACKS)


class TestCPVCodeValidity:
    """Basic sanity checks on CPV codes."""

    def test_cpv_codes_are_8_digits(self):
        """CPV codes should be 8-digit strings ending with checksum."""
        for slug, pack in LEAD_PACKS.items():
            for cpv in pack["cpv_codes"]:
                assert len(cpv) == 8, f"{slug}: CPV {cpv} not 8 digits"
                assert cpv.isdigit(), f"{slug}: CPV {cpv} not numeric"

    def test_no_duplicate_cpv_within_pack(self):
        for slug, pack in LEAD_PACKS.items():
            assert len(pack["cpv_codes"]) == len(set(pack["cpv_codes"])), \
                f"Pack '{slug}' has duplicate CPV codes"

    def test_no_duplicate_keywords_within_pack(self):
        for slug, pack in LEAD_PACKS.items():
            lowered = [kw.lower() for kw in pack["keywords"]]
            assert len(lowered) == len(set(lowered)), \
                f"Pack '{slug}' has duplicate keywords"
