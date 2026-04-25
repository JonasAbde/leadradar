#!/usr/bin/env python3
"""
TED API spike test — official eNotices API v3.
Endpoint: POST https://api.ted.europa.eu/v3/notices/search
Query syntax: expert search string
CPV field: classification-cpv
Country: DNK (ISO 3166-1 alpha-3)

No DB writes. Prints results to stdout.

Verified working fields:
- notice-identifier, publication-number, publication-date
- procedure-type, notice-subtype, notice-type, legal-basis
- notice-title (multilingual dict)
- buyer-name (multilingual dict)
- buyer-country (array)
- dispatch-date, links
"""
import requests
import json
import sys
from datetime import datetime

BASE_URL = "https://api.ted.europa.eu/v3/notices/search"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "LeadRadar/1.0 (Research Tool; contact@leadradar.dk)",
}

# Verified working fields from TED API
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
    """Extract value from multilingual dict e.g. {'dan': ['DTU'], 'eng': ['DTU']}."""
    if not isinstance(d, dict):
        return str(d) if d else ""
    
    preferred_langs = preferred_langs or ["eng", "dan", "fra", "deu", "mul"]
    
    for lang in preferred_langs:
        if lang in d and d[lang]:
            val = d[lang][0] if isinstance(d[lang], list) else d[lang]
            return str(val)
    
    # Return any available value
    for key, val in d.items():
        if val:
            return str(val[0] if isinstance(val, list) else val)
    
    return ""


def search_ted(cpv_codes: list, country: str = "DNK", max_results: int = 10):
    """Search TED API for tender notices."""
    cpv_str = " ".join(str(c) for c in cpv_codes)
    
    if cpv_codes:
        query = f"buyer-country='{country}' AND classification-cpv IN ({cpv_str})"
    else:
        query = f"buyer-country='{country}'"

    payload = {
        "query": query,
        "fields": VERIFIED_FIELDS,
        "limit": min(max_results, 250),
        "page": 1,
        "scope": "ACTIVE",
    }
    
    resp = requests.post(BASE_URL, json=payload, headers=HEADERS, timeout=30)
    return resp


def normalize_notice(n: dict) -> dict:
    """Extract useful fields from TED notice."""
    pub_number = n.get("publication-number", "")
    
    return {
        "notice_id": n.get("notice-identifier", ""),
        "publication_number": pub_number,
        "title": _extract_multilingual(n.get("notice-title", {}), ["eng", "dan"]),
        "buyer": _extract_multilingual(n.get("buyer-name", {}), ["dan", "eng"]),
        "buyer_country": n.get("buyer-country", [""])[0] if isinstance(n.get("buyer-country"), list) else "",
        "cpv_raw": n.get("classification-cpv", ""),
        "pub_date": n.get("publication-date", ""),
        "dispatch_date": n.get("dispatch-date", ""),
        "subtype": n.get("notice-subtype", ""),
        "notice_type": n.get("notice-type", ""),
        "procedure": n.get("procedure-type", ""),
        "legal_basis": n.get("legal-basis", ""),
        "url": f"https://ted.europa.eu/en/notice/{pub_number}" if pub_number else "",
    }


def test_pack(name: str, cpv_codes: list, max_results: int = 10):
    """Test a single lead pack."""
    print(f"\n{'='*60}")
    print(f"PACK: {name}")
    print(f"CPV: {cpv_codes}")
    print(f"{'='*60}")
    
    resp = search_ted(cpv_codes, max_results=max_results)
    
    if resp.status_code == 200:
        data = resp.json()
        total = data.get("totalNoticeCount", 0)
        notices = data.get("notices", [])
        print(f"\n✅ Status: {resp.status_code} | Total hits: {total} | Returned: {len(notices)}")
        
        for i, n in enumerate(notices[:min(3, len(notices))]):
            norm = normalize_notice(n)
            print(f"\n--- Sample {i+1} ---")
            for k, v in norm.items():
                if v:
                    print(f"  {k}: {str(v)[:100]}")
        
        if total < 5:
            print(f"\n  ⚠ Few results, may need broader CPV codes")
        
        return total
    else:
        error_body = resp.text[:300] if resp.text else "No body"
        print(f"\n❌ Status: {resp.status_code} | Error: {error_body}")
        return 0


if __name__ == "__main__":
    print(f"TED API Spike Test — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    results = {}
    
    # Test 1: Cleaning / facility services
    results["Cleaning / Facility"] = test_pack(
        "Cleaning / Facility",
        ["90910000", "90911000", "90911200", "90911300", "90919200", "50000000", "50800000"],
        max_results=10
    )
    
    # Test 2: IT / Software
    results["IT / Software"] = test_pack(
        "IT / Software",
        ["72000000", "72100000", "72200000", "72210000", "72220000", "72230000", "72240000", "72260000"],
        max_results=10
    )
    
    # Test 3: Construction / Maintenance
    results["Construction / Maintenance"] = test_pack(
        "Construction / Maintenance",
        ["45000000", "45200000", "45210000", "45230000", "45240000", "45300000", "45400000"],
        max_results=10
    )
    
    # Test 4: Consulting / Business Services
    results["Consulting / Business Services"] = test_pack(
        "Consulting / Business Services",
        ["73000000", "73100000", "73200000", "73400000", "79000000", "79100000", "79200000", "79300000"],
        max_results=10
    )
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for pack, count in results.items():
        status = "✅" if count > 0 else "❌"
        print(f"  {status} {pack}: {count} tenders")
    
    total_all = sum(results.values())
    print(f"\n  Total tenders across all packs: {total_all}")
    
    if total_all == 0:
        print("\n⚠ NO RESULTS — need to investigate CPV codes or query syntax")
        sys.exit(1)
    else:
        print("\n✅ SPIKE TEST SUCCESSFUL — API integration working")
        print("="*60)
