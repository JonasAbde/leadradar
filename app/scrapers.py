import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from typing import List, Dict
import httpx

class BaseScraper:
    def __init__(self, source):
        self.source = source
        self.config = json.loads(source.config or "{}")
    
    def scrape(self) -> List[Dict]:
        raise NotImplementedError

class CVRScraper(BaseScraper):
    """Scrape CVR data for new companies in relevant industries"""
    
    def scrape(self) -> List[Dict]:
        # For Danish market - scrape erhvervsstyrelsen.dk or similar
        # This is a simplified version - real implementation needs proper API/robots check
        results = []
        keywords = self.config.get("keywords", ["rengøring", "it", "service", "konsulent"])
        
        for keyword in keywords:
            # Placeholder: In production, this would call CVR API or scrape with proper rules
            # For now, return mock data structure
            results.append({
                "title": f"Ny virksomhed i {keyword}",
                "company": f"{keyword.title()} ApS",
                "description": f"Nystartet virksomhed indenfor {keyword}",
                "url": "#",
                "location": "Danmark"
            })
        
        return results

class JobScraper(BaseScraper):
    """Scrape job postings as buying signals"""
    
    def scrape(self) -> List[Dict]:
        results = []
        keywords = self.config.get("keywords", [])
        
        try:
            # Scrape Jobindex.dk or Ofir.dk for relevant postings
            headers = {"User-Agent": "LeadRadar/1.0 (Research Tool)"}
            
            for keyword in keywords:
                url = f"https://www.jobindex.dk/jobsoegning?q={keyword}"
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    jobs = soup.find_all("div", class_="PaidJob", limit=5)
                    
                    for job in jobs:
                        title_el = job.find("h4")
                        company_el = job.find("span", class_="company")
                        
                        if title_el:
                            results.append({
                                "title": f"Job: {title_el.get_text(strip=True)}",
                                "company": company_el.get_text(strip=True) if company_el else "Unknown",
                                "description": f"Sejob posting for {keyword}",
                                "url": url,
                                "location": "Danmark"
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
            # Monitor PressNews.dk or similar for company news
            rss_feeds = self.config.get("feeds", [])
            
            for feed in rss_feeds:
                resp = requests.get(feed, timeout=15)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "xml")
                    items = soup.find_all("item", limit=5)
                    
                    for item in items:
                        title = item.find("title")
                        desc = item.find("description")
                        link = item.find("link")
                        
                        if title:
                            title_text = title.get_text(strip=True)
                            if any(kw.lower() in title_text.lower() for kw in keywords):
                                results.append({
                                    "title": f"News: {title_text}",
                                    "company": "News Alert",
                                    "description": desc.get_text(strip=True)[:200] if desc else "",
                                    "url": link.get_text(strip=True) if link else "#",
                                    "location": "Danmark"
                                })
        except Exception as e:
            print(f"News scraping error: {e}")
        
        return results

class CompetitorScraper(BaseScraper):
    """Monitor competitor websites for changes"""
    
    def scrape(self) -> List[Dict]:
        results = []
        
        try:
            url = self.source.url
            headers = {"User-Agent": "LeadRadar/1.0 (Monitoring)"}
            resp = requests.get(url, headers=headers, timeout=15)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                
                # Extract pricing info if available
                price_selectors = self.config.get("price_selectors", [".price", "[data-price]"])
                prices = []
                for sel in price_selectors:
                    el = soup.select_one(sel)
                    if el:
                        prices.append(el.get_text(strip=True))
                
                results.append({
                    "title": f"Competitor Monitor: {self.source.name}",
                    "company": self.source.name,
                    "description": f"Price found: {', '.join(prices)}" if prices else "Website monitored",
                    "url": url,
                    "location": "Danmark",
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
