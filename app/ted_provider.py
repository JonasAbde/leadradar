"""
TED Provider — EU tender API integration.

Uses the official eNotices API v3: POST https://api.ted.europa.eu/v3/notices/search
Query syntax: expert search string with field filters.

Fields used (verified):
  notice-identifier, publication-number, publication-date,
  procedure-type, notice-subtype, notice-type, legal-basis,
  notice-title (multilingual dict), buyer-name (multilingual dict),
  buyer-country (array), dispatch-date
"""

import httpx
from datetime import datetime
from typing import List, Dict, Optional


TED_API_URL = "https://api.ted.europa.eu/v3/notices/search"
TED_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "LeadRadar/1.0 (Research Tool; contact@leadradar.dk)",
}

VERIFIED_FIELDS = [
    "notice-identifier",
    "publication-number",
    "publication-date",
    "procedure-type",
    "notice-subtype",
    "notice-type",
    "legal-basis",
    "notice-title",
    "buyer-name",
    "buyer-country",
    "dispatch-date",
]


def _extract_multilingual(d: dict, preferred_langs: list = None) -> str:
    """Extract value from multilingual dict e.g. {'dan': ['text'], 'eng': ['text']}."""
    if not isinstance(d, dict):
        return str(d) if d else ""

    preferred_langs = preferred_langs or ["eng", "dan", "fra", "deu", "mul"]

    for lang in preferred_langs:
        if lang in d and d[lang]:
            val = d[lang][0] if isinstance(d[lang], list) else d[lang]
            return str(val)

    for key, val in d.items():
        if val:
            return str(val[0] if isinstance(val, list) else val)

    return ""


class TEDProvider:
    """Fetch and normalize tender notices from TED API."""

    def __init__(self, base_url: str = TED_API_URL, headers: dict = None):
        self.base_url = base_url
        self.headers = headers or TED_HEADERS

    def fetch_tenders(
        self,
        country: str = "DNK",
        cpv_codes: list = None,
        max_pages: int = 3,
        limit: int = 250,
    ) -> List[dict]:
        """
        Search TED API for tender notices.

        Args:
            country: ISO 3166-1 alpha-3 country code (e.g. 'DNK')
            cpv_codes: list of CPV codes to filter by
            max_pages: maximum pages to fetch
            limit: results per page (max 250)

        Returns:
            List of normalized notice dicts
        """
        cpv_codes = cpv_codes or []
        # Build query: buyer-country='DNK' AND classification-cpv IN (72 7210 7220)
        cpv_str = " ".join(str(c) for c in cpv_codes)

        if cpv_codes:
            query = f"buyer-country='{country}' AND classification-cpv IN ({cpv_str})"
        else:
            query = f"buyer-country='{country}'"

        payload = {
            "query": query,
            "fields": VERIFIED_FIELDS,
            "limit": min(limit, 250),
            "page": 1,
            "scope": "LATEST",  # LATEST = fresh notices (typically last 24h); ACTIVE = all historical
        }

        notices = []
        total_notices = 0

        with httpx.Client(timeout=30) as client:
            for page_num in range(1, max_pages + 1):
                payload["page"] = page_num

                resp = client.post(self.base_url, json=payload, headers=self.headers)

                if resp.status_code != 200:
                    break

                data = resp.json()
                total_notices = data.get("totalNoticeCount", 0)
                page_notices = data.get("notices", [])

                if not page_notices:
                    break

                for n in page_notices:
                    normalized = self._normalize_notice(n)
                    if normalized:
                        notices.append(normalized)

                # Check if we've fetched all results
                if len(notices) >= total_notices:
                    break

                # If page returned fewer items than limit, no more pages
                if len(page_notices) < payload["limit"]:
                    break

        return notices

    def _normalize_notice(self, n: dict) -> Optional[dict]:
        """Extract useful fields from TED notice. Returns None if key fields missing."""
        pub_number = n.get("publication-number", "") or ""
        if not pub_number:
            return None  # Skip notices without idempotency key

        return {
            "notice_id": n.get("notice-identifier", ""),
            "pub_number": pub_number,
            "title": _extract_multilingual(
                n.get("notice-title", {}), ["eng", "dan"]
            ),
            "buyer": _extract_multilingual(
                n.get("buyer-name", {}), ["dan", "eng"]
            ),
            "buyer_country": self._extract_country(n.get("buyer-country")),
            "pub_date": n.get("publication-date", ""),
            "dispatch_date": n.get("dispatch-date", ""),
            "subtype": n.get("notice-subtype", ""),
            "notice_type": n.get("notice-type", ""),
            "procedure": n.get("procedure-type", ""),
            "legal_basis": n.get("legal-basis", ""),
            "url": f"https://ted.europa.eu/en/notice/{pub_number}" if pub_number else "",
        }

    @staticmethod
    def _extract_country(country_field) -> str:
        """Extract country from buyer-country array field."""
        if isinstance(country_field, list) and len(country_field) > 0:
            return str(country_field[0])
        return str(country_field) if country_field else ""
