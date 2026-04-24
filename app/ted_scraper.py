"""
TED EU tender scraper using Playwright headless browser.
AWS WAF blocks direct API access — browser automation required.
Runs as standalone cron job or called from scheduler.
Idempotency on notice_number.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from typing import List, Dict


def fetch_ted_notices(country_filter: str = None, max_pages: int = 3) -> List[Dict]:
    """Fetch tender notices from TED search results via headless browser."""
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for page_num in range(1, max_pages + 1):
            url = f"https://ted.europa.eu/search/result?search-scope=ALL&page={page_num}"
            try:
                page.goto(url, wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(4000)

                rows = page.locator("tr").element_handles()
                if len(rows) <= 1:
                    break

                for row in rows[1:]:
                    cells = row.query_selector_all("td")
                    if len(cells) < 5:
                        continue

                    try:
                        link = cells[1].query_selector("a")
                        if not link:
                            continue
                        notice_num = link.inner_text().strip()
                        href = link.get_attribute("href") or ""

                        desc_text = cells[2].inner_text().strip()
                        lines = [l.strip() for l in desc_text.split('\n') if l.strip()]
                        title = lines[0] if lines else ""

                        authority = ""
                        for line in lines:
                            if line.startswith("Official name:"):
                                authority = line.replace("Official name:", "").strip()

                        country = cells[3].inner_text().strip()

                        if country_filter and country_filter not in country:
                            continue

                        pub_date = cells[4].inner_text().strip()
                        deadline = cells[5].inner_text().strip() if len(cells) > 5 else ""

                        notice_url = f"https://ted.europa.eu{href}" if href else ""

                        results.append({
                            "notice_number": notice_num,
                            "title": title,
                            "description": desc_text[:300],
                            "company": authority or country,
                            "country": country,
                            "pub_date": pub_date,
                            "deadline": deadline,
                            "url": notice_url,
                            "score": 65,
                            "source_type": "ted_eu",
                        })
                    except Exception:
                        continue

                if len(rows) < 50:
                    break
            except Exception as e:
                print(f"TED page {page_num} error: {e}")
                break

        browser.close()

    return results


def save_ted_notices_to_db(notices: List[Dict], user_id: int = 1):
    """Save fetched notices as leads in the database."""
    from app import models

    db = models.SessionLocal()
    try:
        source = db.query(models.Source).filter(
            models.Source.user_id == user_id,
            models.Source.source_type == "ted_eu"
        ).first()

        if not source:
            source = models.Source(
                user_id=user_id,
                name="TED EU Tenders",
                source_type="ted_eu",
                url="https://ted.europa.eu",
                config='{"country": "DK"}',
            )
            db.add(source)
            db.commit()
            db.refresh(source)

        saved = 0
        skipped = 0
        for notice in notices:
            existing = db.query(models.Lead).filter(
                models.Lead.user_id == user_id,
                models.Lead.url == notice["url"]
            ).first()

            if existing:
                skipped += 1
                continue

            lead = models.Lead(
                user_id=user_id,
                source_id=source.id,
                title=notice["title"][:200],
                description=notice["description"],
                url=notice["url"],
                company=notice["company"][:100],
                location=notice["country"],
                score=notice["score"],
            )
            db.add(lead)
            saved += 1

        db.commit()
        print(f"[TED] Saved {saved} new notices, skipped {skipped} duplicates")
        return saved
    finally:
        db.close()


if __name__ == "__main__":
    print("Fetching TED notices (all countries)...")
    notices = fetch_ted_notices(country_filter=None, max_pages=1)
    print(f"Found {len(notices)} notices")
    for n in notices[:5]:
        print(f"  {n['notice_number']} | {n['country']} | {n['title'][:60]}")
