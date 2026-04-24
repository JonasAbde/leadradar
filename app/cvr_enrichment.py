import requests
from typing import Optional, Dict
import json

CVR_API_URL = "https://cvrapi.dk/api"
DEFAULT_HEADERS = {"User-Agent": "LeadRadar/1.0 (research@leadradar.dk)"}

class CVREnricher:
    """Enrich lead data using cvrapi.dk (free Danish CVR lookup).
    
    This is a LOOKUP service: feed it a CVR number or company name,
    get structured company data back.
    
    Rate limit: Be polite, 1 call per 2 seconds max.
    """
    
    def enrich(self, query: str) -> Optional[Dict]:
        """Look up company by CVR number or name.
        
        Args:
            query: CVR number (8 digits) or company name
            
        Returns:
            Dict with structured company data or None if not found/error
        """
        try:
            resp = requests.get(
                CVR_API_URL,
                params={"search": query, "country": "dk"},
                headers=DEFAULT_HEADERS,
                timeout=15
            )
            
            if resp.status_code == 404:
                return None
            if resp.status_code != 200:
                print(f"[CVR API] HTTP {resp.status_code}: {resp.text[:200]}")
                return None
            
            data = resp.json()
            if data.get("error"):
                return None
            
            return self._normalize(data)
            
        except requests.RequestException as e:
            print(f"[CVR API] Network error: {e}")
            return None
        except json.JSONDecodeError:
            print("[CVR API] Invalid JSON response")
            return None
    
    def _normalize(self, raw: Dict) -> Dict:
        """Convert cvrapi.dk response to our standard format."""
        owner_name = None
        owners = raw.get("owners", [])
        if owners and isinstance(owners, list):
            owner_name = owners[0].get("name") if owners[0] else None
        
        return {
            "cvr_number": str(raw.get("vat", "")),
            "company_name": raw.get("name"),
            "address": raw.get("address"),
            "zipcode": raw.get("zipcode"),
            "city": raw.get("city"),
            "phone": raw.get("phone"),
            "email": raw.get("email"),
            "industry_code": str(raw.get("industrycode", "")),
            "industry_desc": raw.get("industrydesc"),
            "company_type": raw.get("companydesc"),
            "employee_count": raw.get("employees"),
            "owner_name": owner_name,
            "start_date": raw.get("startdate"),
            "is_bankrupt": raw.get("creditbankrupt", False),
            "raw_data": raw,  # Store full response for future use
        }

# Global instance
enricher = CVREnricher()

def enrich_lead(lead_company_name: str, lead_cvr: str = None) -> Optional[Dict]:
    """Convenience function: try CVR first, fall back to name."""
    if lead_cvr and lead_cvr.isdigit() and len(lead_cvr) == 8:
        result = enricher.enrich(lead_cvr)
        if result:
            return result
    
    # Try company name
    if lead_company_name and len(lead_company_name) > 2:
        result = enricher.enrich(lead_company_name)
        if result:
            return result
    
    return None
