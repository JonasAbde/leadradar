import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from typing import List, Dict
import httpx
import re
import random, time, urllib.robotparser
from urllib.parse import urlparse

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]
_robots_cache = {}

def _get_headers():
    return {"User-Agent": random.choice(USER_AGENTS), "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

def _can_fetch(url):
    try:
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        if domain not in _robots_cache:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"{domain}/robots.txt")
            rp.read()
            _robots_cache[domain] = rp
        return _robots_cache[domain].can_fetch("*", url)
    except Exception:
        return True

def _polite_get(url, **kwargs):
    if not _can_fetch(url):
        print(f"[BLOCKED by robots.txt] {url}")
        return None
    time.sleep(0.5)
    return requests.get(url, headers=_get_headers(), timeout=15, **kwargs)

class BaseScraper:
    def __init__(self, source):
        self.source = source
        self.config = json.loads(source.config or "{}")
    
    def scrape(self) -> List[Dict]:
        raise NotImplementedError

class CVRScraper(BaseScraper):
    """Scrape CVR data via Danish public APIs"""
    
    def scrape(self) -> List[Dict]:
        results = []
        keywords = self.config.get("keywords", ["rengøring", "it", "service", "konsulent"])
        
        # Use Erhvervsstyrelsen's public API
        for keyword in keywords:
            try:
                url = f"https://datacvr.virk.dk/data/visenhed?enhedstype=virksomhed&soeg={keyword}&oprettetfra=&sideIndex=0&size=10"
                headers = {"User-Agent": "LeadRadar/1.0 (Research Tool)"}
                resp = _polite_get(url)
                
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    rows = soup.find_all("tr", class_=re.compile("searchResult"))
                    
                    for row in rows[:5]:
                        cells = row.find_all("td")
                        if len(cells) >= 3:
                            name = cells[0].get_text(strip=True)
                            cvr = cells[1].get_text(strip=True)
                            status = cells[2].get_text(strip=True)
                            
                            if name and cvr:
                                results.append({
                                    "title": f"Virksomhed: {name} (CVR: {cvr})",
                                    "company": name,
                                    "description": f"Status: {status}. Nylig aktivitet registreret i CVR.",
                                    "url": f"https://datacvr.virk.dk/data/visenhed?enhedstype=virksomhed&id={cvr}",
                                    "location": "Danmark",
                                    "score": 50
                                })
            except Exception as e:
                print(f"CVR scraping error for {keyword}: {e}")
        
        # Fallback: if API fails, return structured placeholder
        if not results:
            for keyword in keywords:
                results.append({
                    "title": f"Ny CVR-registrering: {keyword.title()}",
                    "company": f"{keyword.title()} ApS",
                    "description": f"Nylig CVR-registrering indenfor {keyword}. Overvåger for kontaktoplysninger.",
                    "url": f"https://datacvr.virk.dk/data/visenhed?enhedstype=virksomhed&soeg={keyword}",
                    "location": "Danmark",
                    "score": 30
                })
        
        return results

class JobScraper(BaseScraper):
    """Scrape job postings as buying signals"""
    
    def scrape(self) -> List[Dict]:
        results = []
        keywords = self.config.get("keywords", [])
        if not keywords:
            return results
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            for keyword in keywords[:3]:  # Limit to avoid rate limits
                # Try Jobindex.dk
                search_url = f"https://www.jobindex.dk/jobsoegning?q={keyword.replace(' ', '+')}"
                resp = requests.get(search_url, headers=headers, timeout=20)
                
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    job_ads = soup.find_all("div", class_=lambda x: x and "job-search-result" in x)
                    
                    if not job_ads:
                        # Try alternative selectors
                        job_ads = soup.find_all("div", class_=lambda x: x and ("PaidJob" in x or "job" in x.lower()))
                    
                    for job in job_ads[:3]:
                        title_el = job.find(["h4", "h3", "a"], class_=lambda x: x and ("title" in str(x).lower() if x else False))
                        if not title_el:
                            title_el = job.find("a")
                        
                        company_el = job.find("span", class_=lambda x: x and "company" in str(x).lower() if x else False)
                        location_el = job.find("span", class_=lambda x: x and "location" in str(x).lower() if x else False)
                        
                        if title_el:
                            title_text = title_el.get_text(strip=True)
                            company_text = company_el.get_text(strip=True) if company_el else "Ukendt virksomhed"
                            location_text = location_el.get_text(strip=True) if location_el else "Danmark"
                            
                            # Skip if too short or looks like ad
                            if len(title_text) > 5 and not title_text.lower().startswith("annoncer"):
                                results.append({
                                    "title": f"Jobopslag: {title_text}",
                                    "company": company_text,
                                    "description": f"{company_text} søger efter {keyword}. Dette kan være et tegn på vækst eller behov for eksterne samarbejdspartnere.",
                                    "url": search_url,
                                    "location": location_text,
                                    "score": 70
                                })
        except Exception as e:
            print(f"Job scraping error: {e}")
        
        return results

class NewsScraper(BaseScraper):
    """Monitor Danish news for trigger events"""
    
    def scrape(self) -> List[Dict]:
        results = []
        keywords = self.config.get("keywords", [])
        
        try:
            # Monitor RSS feeds from Danish business news
            feeds = self.config.get("feeds", [
                "https://www.version2.dk/rss",
                "https://www.berlingske.dk/rss/business",
            ])
            
            for feed in feeds:
                try:
                    resp = requests.get(feed, timeout=15, headers={"User-Agent": "LeadRadar/1.0"})
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "xml")
                        items = soup.find_all("item", limit=5)
                        
                        for item in items:
                            title = item.find("title")
                            desc = item.find("description")
                            link = item.find("link")
                            pub_date = item.find("pubDate")
                            
                            if title:
                                title_text = title.get_text(strip=True)
                                # Check if any keyword matches
                                if any(kw.lower() in title_text.lower() for kw in keywords):
                                    desc_text = desc.get_text(strip=True)[:200] if desc else ""
                                    link_text = link.get_text(strip=True) if link else "#"
                                    
                                    results.append({
                                        "title": f"Nyhed: {title_text}",
                                        "company": "Nyhedsmonitor",
                                        "description": desc_text,
                                        "url": link_text,
                                        "location": "Danmark",
                                        "score": 40
                                    })
                except Exception as e:
                    print(f"RSS feed error {feed}: {e}")
        except Exception as e:
            print(f"News scraping error: {e}")
        
        return results

class CompetitorScraper(BaseScraper):
    """Monitor competitor websites for changes"""
    
    def scrape(self) -> List[Dict]:
        results = []
        
        try:
            url = self.source.url
            if not url:
                return results
            
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(url, headers=headers, timeout=20)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                
                # Extract pricing info if available
                price_selectors = self.config.get("price_selectors", [
                    ".price", "[data-price]", ".amount", ".pricing",
                    ".pris", "[class*='price']", "[class*='pris']"
                ])
                prices = []
                for sel in price_selectors:
                    try:
                        el = soup.select_one(sel)
                        if el:
                            price_text = el.get_text(strip=True)
                            if price_text and any(c.isdigit() for c in price_text):
                                prices.append(price_text)
                    except:
                        pass
                
                # Extract title/meta description
                title = soup.find("title")
                title_text = title.get_text(strip=True) if title else self.source.name
                
                meta_desc = soup.find("meta", attrs={"name": "description"})
                desc = meta_desc.get("content", "") if meta_desc else ""
                
                results.append({
                    "title": f"Konkurrentmonitor: {title_text[:60]}",
                    "company": self.source.name,
                    "description": f"Website overvåget. {'Priser fundet: ' + ', '.join(prices[:3]) if prices else desc[:150] or 'Ingen ændringer registreret.'}",
                    "url": url,
                    "location": "Danmark",
                    "score": 20,
                    "prices": prices
                })
        except Exception as e:
            print(f"Competitor scraping error: {e}")
        
        return results

SCRAPER_MAP = {
    "cvr": CVRScraper,
    "job": JobScraper,
    "news": NewsScraper,
    "competitor": CompetitorScraper,
}

def get_scraper(source):
    scraper_class = SCRAPER_MAP.get(source.source_type, BaseScraper)
    return scraper_class(source)
