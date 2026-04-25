"""
Lead Scoring — relevance scoring for TED tender notices.

Score factors:
  - CPV match: +30
  - Country match (DNK): +20
  - Deadline within 30 days: +15
  - Deadline within 7 days: +10 extra
  - Has estimated value: +5
  - Keyword in title: +10
  - Published < 7 days ago: +10
  - Normalized to 0-100

Returns (score, reasons) tuple.
"""

from datetime import datetime, timedelta
from typing import List, Tuple


def _parse_date(date_str: str) -> datetime:
    """Try to parse a date string."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except (ValueError, TypeError):
            continue
    return None


def score_lead(
    lead: dict,
    cpv_codes: list = None,
    keywords: list = None,
    target_country: str = "DNK",
) -> Tuple[int, List[str]]:
    """
    Score a lead dict for relevance.

    Args:
        lead: dict with lead fields (title, cpv_values, buyer_country, deadline_date, etc.)
        cpv_codes: pack CPV codes to match against
        keywords: pack keywords for title matching
        target_country: country code to match against

    Returns:
        (score, reasons) tuple where score is 0-100 and reasons is list of strings
    """
    score = 0
    reasons = []
    raw_score = 0

    # CPV match (+30)
    lead_cpv = lead.get("cpv_values", [])
    if isinstance(lead_cpv, str):
        try:
            import json
            lead_cpv = json.loads(lead_cpv) if lead_cpv else []
        except (json.JSONDecodeError, TypeError):
            lead_cpv = [lead_cpv] if lead_cpv else []

    if cpv_codes and lead_cpv:
        # Check if any lead CPV starts with any pack CPV prefix
        for pack_cpv in cpv_codes:
            for l_cpv in lead_cpv:
                l_cpv_str = str(l_cpv).strip()
                if l_cpv_str.startswith(pack_cpv[:2]):
                    raw_score += 30
                    reasons.append(f"CPV match: {l_cpv_str}")
                    break
            else:
                continue
            break

    # Country match (+20)
    buyer_country = str(lead.get("buyer_country", "")).strip().upper()
    if buyer_country == target_country.upper():
        raw_score += 20
        reasons.append(f"Country match: {buyer_country}")

    # Deadline urgency
    deadline_str = lead.get("deadline_date", "")
    deadline = _parse_date(deadline_str)
    if deadline:
        now = datetime.now()
        days_until = (deadline - now).days

        if 0 <= days_until <= 7:
            raw_score += 25  # +15 base + +10 extra
            reasons.append(f"Deadline within 7 days ({days_until} days left)")
        elif 7 < days_until <= 30:
            raw_score += 15
            reasons.append(f"Deadline within 30 days ({days_until} days left)")
        else:
            reasons.append(f"Deadline far out ({days_until} days)")

    # Has estimated value (+5)
    estimated_value = lead.get("estimated_value")
    if estimated_value and estimated_value not in (0, "", None):
        raw_score += 5
        reasons.append(f"Estimated value: {estimated_value}")

    # Keyword in title (+10)
    title = (lead.get("title") or "").lower()
    if keywords and title:
        for kw in keywords:
            if kw.lower() in title:
                raw_score += 10
                reasons.append(f"Keyword '{kw}' in title")
                break

    # Published recently (+10)
    pub_date_str = lead.get("pub_date", "")
    pub_date = _parse_date(pub_date_str)
    if pub_date:
        days_since = (datetime.now() - pub_date).days
        if days_since < 7:
            raw_score += 10
            reasons.append(f"Published {days_since} days ago")

    # Normalize to 0-100
    # Max raw possible: 30+20+25+5+10+10 = 100
    # So normalize by capping at 100
    score = min(raw_score, 100)

    if not reasons:
        reasons.append("No strong signals")

    return score, reasons
