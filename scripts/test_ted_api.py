#!/usr/bin/env python3
"""
TED API spike test.
Endpoint: POST https://ted.europa.eu/api/v3/notices/search
Anonymous access for published notices.
No DB writes.
"""
import requests
import json

BASE_URL = "https://ted.europa.eu/api/v3/notices/search"

def search_ted(cpv_codes, country="DK", max_results=20):
    """Search TED API for tender notices."""
    payload = {
        "fields": ["ND", "NC", "PD", "ODS", "OJ", "AU"],
        "query": {
            "searchCriteria": {
                "country": [country],
                "cpv": cpv_codes,
                "noticeType": ["Contract notice", "Prior information notice"],
            }
        },
        "size": max_results,
        "sort": {"field": "PD", "order": "DESC"},
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "LeadRadar/1.0 (Research Tool; contact@leadradar.dk)",
    }
    
    resp = requests.post(BASE_URL, json=payload, headers=headers, timeout=30)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Error: {resp.text[:500]}")
        return []
    
    data = resp.json()
    notices = data.get("notices", [])
    print(f"Total hits: {data.get('totalNotices', 'N/A')}")
    print(f"Returned: {len(notices)}")
    return notices


def normalize_notice(n):
    """Extract useful fields from TED notice."""
    # n structure varies — handle nested dicts
    title = n.get("title", [""])[0] if isinstance(n.get("title"), list) else n.get("title", "")
    if not title and "content" in n:
        title = n["content"].get("title", [""])[0] if isinstance(n["content"].get("title"), list) else n["content"].get("title", "")
    
    # Contracting authority
    auth = n.get("contractingAuthority", "")
    if not auth and "content" in n:
        auth = n["content"].get("contractingAuthority", "")
    if isinstance(auth, list):
        auth = auth[0] if auth else ""
    if isinstance(auth, dict):
        auth = auth.get("officialName", auth.get("name", ""))
    
    # Publication date
    pub_date = n.get("publicationDate", "")
    if not pub_date and "content" in n:
        pub_date = n["content"].get("publicationDate", "")
    
    # Notice ID / URI
    notice_id = n.get("noticeId", "")
    if not notice_id:
        notice_id = n.get("id", "")
    
    uri = n.get("uri", "")
    if not uri and notice_id:
        uri = f"https://ted.europa.eu/en/notice/{notice_id}/text"
    
    # CPV
    cpv = n.get("mainCPV", "")
    if not cpv and "content" in n:
        cpv = n["content"].get("mainCPV", "")
    
    return {
        "notice_id": notice_id,
        "title": title,
        "authority": auth,
        "pub_date": pub_date,
        "uri": uri,
        "cpv": cpv,
    }


if __name__ == "__main__":
    # Test 1: Cleaning / facility services (CPV 90)
    print("=" * 60)
    print("TEST 1: CPV 90 (Sewage/refuse/sanitation/cleaning)")
    print("=" * 60)
    notices = search_ted(["90"], country="DK", max_results=10)
    for i, n in enumerate(notices[:3]):
        norm = normalize_notice(n)
        print(f"\n--- Sample {i+1} ---")
        for k, v in norm.items():
            print(f"  {k}: {str(v)[:100]}")
    
    # Test 2: Facility management (CPV 50)
    print("\n" + "=" * 60)
    print("TEST 2: CPV 50 (Repair/maintenance services)")
    print("=" * 60)
    notices = search_ted(["50"], country="DK", max_results=10)
    for i, n in enumerate(notices[:3]):
        norm = normalize_notice(n)
        print(f"\n--- Sample {i+1} ---")
        for k, v in norm.items():
            print(f"  {k}: {str(v)[:100]}")
    
    # Test 3: IT services (CPV 72)
    print("\n" + "=" * 60)
    print("TEST 3: CPV 72 (IT services)")
    print("=" * 60)
    notices = search_ted(["72"], country="DK", max_results=10)
    for i, n in enumerate(notices[:3]):
        norm = normalize_notice(n)
        print(f"\n--- Sample {i+1} ---")
        for k, v in norm.items():
            print(f"  {k}: {str(v)[:100]}")
    
    # Test 4: Combined CPVs
    print("\n" + "=" * 60)
    print("TEST 4: CPV 50 + 72 + 90 (combined)")
    print("=" * 60)
    notices = search_ted(["50", "72", "90"], country="DK", max_results=10)
    for i, n in enumerate(notices[:3]):
        norm = normalize_notice(n)
        print(f"\n--- Sample {i+1} ---")
        for k, v in norm.items():
            print(f"  {k}: {str(v)[:100]}")
