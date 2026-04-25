"""
Lead Pack Definitions — vertical-specific CPV code bundles for TED tenders.

Each pack defines:
  - cpv_codes: list of CPV codes used in TED API queries
  - keywords: used for relevance scoring (title matching)
  - country: ISO 3166-1 alpha-3 country code
"""

LEAD_PACKS = {
    "cleaning_facility": {
        "name": "Cleaning & Facility Services",
        "cpv_codes": ["90910000", "90911000", "90911200", "90911300", "90919200", "50000000", "50800000"],
        "keywords": ["cleaning", "facility", "maintenance", "janitorial"],
        "country": "DNK",
    },
    "it_software": {
        "name": "IT & Software",
        "cpv_codes": ["72000000", "72100000", "72200000", "72210000", "72220000", "72230000", "72240000", "72260000"],
        "keywords": ["software", "it", "computer", "digital", "system", "platform"],
        "country": "DNK",
    },
    "construction": {
        "name": "Construction & Infrastructure",
        "cpv_codes": ["45000000", "45200000", "45210000", "45230000", "45240000", "45300000", "45400000"],
        "keywords": ["construction", "building", "infrastructure", "civil", "renovation"],
        "country": "DNK",
    },
    "consulting": {
        "name": "Consulting & Business Services",
        "cpv_codes": ["73000000", "73100000", "73200000", "73400000", "79000000", "79100000", "79200000", "79300000"],
        "keywords": ["consulting", "advisory", "analysis", "strategy", "management"],
        "country": "DNK",
    },
}


def get_pack(pack_slug: str) -> dict:
    """Get a lead pack definition by slug."""
    return LEAD_PACKS.get(pack_slug)


def all_packs() -> dict:
    """Get all lead pack definitions."""
    return LEAD_PACKS
