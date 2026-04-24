"""HubSpot CRM Adapter — implements BaseCRMProvider.

Requires HUBSPOT_PRIVATE_APP_TOKEN env var.
Never commits token to git.
Idempotent: searches by CVR and domain before create.
"""

import os
from typing import Dict, Any, Optional
import requests

from . import BaseCRMProvider, LeadData, SyncResult

HUBSPOT_API_BASE = "https://api.hubapi.com"


class HubSpotProvider(BaseCRMProvider):
    """HubSpot CRM adapter. Uses Private App token via env var."""
    
    name = "hubspot"
    
    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        # Token priority: explicit config > env var > None
        self.token = config.get("token") or os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "")
        if not self.token:
            raise ValueError("HubSpot token required. Set HUBSPOT_PRIVATE_APP_TOKEN env var or pass in config.")
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        })
    
    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        url = f"{HUBSPOT_API_BASE}{endpoint}"
        try:
            resp = self.session.get(url, params=params or {}, timeout=15)
            if resp.status_code == 204:
                return {}
            if resp.status_code >= 400:
                return {"_error": f"HTTP {resp.status_code}", "_body": resp.text[:500]}
            return resp.json()
        except requests.RequestException as e:
            return {"_error": str(e)}
    
    def _post(self, endpoint: str, payload: Dict) -> Optional[Dict]:
        url = f"{HUBSPOT_API_BASE}{endpoint}"
        try:
            resp = self.session.post(url, json=payload, timeout=15)
            if resp.status_code >= 400:
                return {"_error": f"HTTP {resp.status_code}", "_body": resp.text[:500]}
            return resp.json()
        except requests.RequestException as e:
            return {"_error": str(e)}
    
    def _patch(self, endpoint: str, payload: Dict) -> Optional[Dict]:
        url = f"{HUBSPOT_API_BASE}{endpoint}"
        try:
            resp = self.session.patch(url, json=payload, timeout=15)
            if resp.status_code >= 400:
                return {"_error": f"HTTP {resp.status_code}", "_body": resp.text[:500]}
            return resp.json()
        except requests.RequestException as e:
            return {"_error": str(e)}
    
    def test_connection(self) -> bool:
        # Use account info endpoint to verify token
        result = self._get("/integrations/v1/me")
        if result and "_error" not in result:
            return True
        return False
    
    def _search_company_by_cvr(self, cvr: str) -> Optional[str]:
        """Search HubSpot for company by CVR number. Returns company ID or None."""
        result = self._post("/crm/v3/objects/companies/search", {
            "filterGroups": [{
                "filters": [{
                    "propertyName": "cvr_number",
                    "operator": "EQ",
                    "value": cvr
                }]
            }],
            "properties": ["name", "cvr_number"]
        })
        if result and "_error" not in result:
            results = result.get("results", [])
            if results:
                return results[0].get("id")
        return None
    
    def _search_company_by_domain(self, domain: str) -> Optional[str]:
        """Search by domain (fallback)."""
        result = self._post("/crm/v3/objects/companies/search", {
            "filterGroups": [{
                "filters": [{
                    "propertyName": "domain",
                    "operator": "EQ",
                    "value": domain
                }]
            }],
            "properties": ["name", "domain"]
        })
        if result and "_error" not in result:
            results = result.get("results", [])
            if results:
                return results[0].get("id")
        return None
    
    def _extract_domain(self, email: Optional[str]) -> Optional[str]:
        if email and "@" in email:
            return email.split("@")[1]
        return None
    
    def create_or_update_company(self, lead: LeadData) -> SyncResult:
        # Search by CVR first
        company_id = None
        if lead.cvr_number:
            company_id = self._search_company_by_cvr(lead.cvr_number)
        
        # Fallback: search by domain
        if not company_id and lead.email:
            domain = self._extract_domain(lead.email)
            if domain:
                company_id = self._search_company_by_domain(domain)
        
        # Build properties
        properties = {
            "name": lead.company,
            "phone": lead.phone or "",
            "address": lead.address or "",
            "city": lead.city or "",
            "zip": lead.zipcode or "",
            "industry": lead.industry_desc or "",
            "numberofemployees": str(lead.employee_count) if lead.employee_count else "",
            "type": lead.company_type or "",
        }
        # Add CVR as custom property if available
        if lead.cvr_number:
            properties["cvr_number"] = lead.cvr_number
        
        if company_id:
            # Update existing
            result = self._patch(f"/crm/v3/objects/companies/{company_id}", {"properties": properties})
            if result and "_error" in result:
                return SyncResult(
                    success=False,
                    error=f"Update company failed: {result['_error']}"
                )
            return SyncResult(success=True, company_id=company_id)
        else:
            # Create new
            result = self._post("/crm/v3/objects/companies", {"properties": properties})
            if result and "_error" in result:
                return SyncResult(
                    success=False,
                    error=f"Create company failed: {result['_error']}"
                )
            return SyncResult(success=True, company_id=result.get("id"))
    
    def _search_contact_by_email(self, email: str) -> Optional[str]:
        """Search HubSpot for contact by email."""
        result = self._post("/crm/v3/objects/contacts/search", {
            "filterGroups": [{
                "filters": [{
                    "propertyName": "email",
                    "operator": "EQ",
                    "value": email
                }]
            }],
            "properties": ["email", "firstname", "lastname"]
        })
        if result and "_error" not in result:
            results = result.get("results", [])
            if results:
                return results[0].get("id")
        return None
    
    def create_or_update_contact(self, lead: LeadData) -> SyncResult:
        if not lead.email and not lead.phone:
            return SyncResult(success=False, error="No email or phone for contact")
        
        contact_id = None
        if lead.email:
            contact_id = self._search_contact_by_email(lead.email)
        
        # Parse name
        firstname, lastname = "", ""
        if lead.owner_name:
            parts = lead.owner_name.strip().split(None, 1)
            firstname = parts[0]
            lastname = parts[1] if len(parts) > 1 else ""
        
        properties = {
            "firstname": firstname or lead.company,
            "lastname": lastname,
            "email": lead.email or "",
            "phone": lead.phone or "",
        }
        
        if contact_id:
            result = self._patch(f"/crm/v3/objects/contacts/{contact_id}", {"properties": properties})
            if result and "_error" in result:
                return SyncResult(success=False, error=f"Update contact failed: {result['_error']}")
            return SyncResult(success=True, contact_id=contact_id)
        else:
            result = self._post("/crm/v3/objects/contacts", {"properties": properties})
            if result and "_error" in result:
                return SyncResult(success=False, error=f"Create contact failed: {result['_error']}")
            return SyncResult(success=True, contact_id=result.get("id"))
    
    def create_lead_or_deal(self, lead: LeadData, company_id: str, contact_id: Optional[str] = None) -> SyncResult:
        """Create a Deal in HubSpot linked to company and contact."""
        
        properties = {
            "dealname": lead.title or f"Lead: {lead.company}",
            "amount": str(lead.score * 100) if lead.score else "0",
            "pipeline": "default",
            "dealstage": "appointmentscheduled",  # Initial stage
        }
        
        result = self._post("/crm/v3/objects/deals", {
            "properties": properties,
            "associations": [
                {"to": {"id": company_id}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 5}]},  # Company
            ]
        })
        
        if contact_id:
            # Associate contact too
            deal_id = result.get("id") if result else None
            if deal_id:
                self._post(f"/crm/v3/objects/deals/{deal_id}/associations/contact/{contact_id}/3", {})
        
        if result and "_error" in result:
            return SyncResult(success=False, error=f"Create deal failed: {result['_error']}")
        
        return SyncResult(success=True, lead_id=result.get("id"))
