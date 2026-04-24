"""Mock CRM Provider — implements BaseCRMProvider for safe testing.

No external calls. Stores "synced" records in memory for inspection.
Used as default provider when no real CRM is configured.
"""

from typing import Dict, Any, Optional
from . import BaseCRMProvider, LeadData, SyncResult


class MockCRMProvider(BaseCRMProvider):
    """In-memory mock CRM. No network calls, no secrets needed."""
    
    name = "mock"
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config or {})
        self.companies: Dict[str, Dict] = {}   # external_id → data
        self.contacts: Dict[str, Dict] = {}    # external_id → data
        self.leads: Dict[str, Dict] = {}       # external_id → data
        self.call_log: list = []               # audit trail
    
    def _log(self, method: str, lead_id: int, result: str):
        self.call_log.append({"method": method, "lead_id": lead_id, "result": result})
    
    def test_connection(self) -> bool:
        self._log("test_connection", 0, "mock_always_ok")
        return True
    
    def create_or_update_company(self, lead: LeadData) -> SyncResult:
        # Idempotency key: company name + CVR
        ext_id = f"mock_company_{lead.cvr_number or hash(lead.company) & 0xFFFFFFFF}"
        
        existing = self.companies.get(ext_id)
        if existing:
            existing.update({
                "name": lead.company,
                "cvr": lead.cvr_number,
                "industry": lead.industry_desc,
                "employees": lead.employee_count,
                "address": lead.address,
                "city": lead.city,
                "zip": lead.zipcode,
            })
            self._log("create_or_update_company", lead.id, "updated")
        else:
            self.companies[ext_id] = {
                "name": lead.company,
                "cvr": lead.cvr_number,
                "industry": lead.industry_desc,
                "employees": lead.employee_count,
                "address": lead.address,
                "city": lead.city,
                "zip": lead.zipcode,
                "raw": lead,
            }
            self._log("create_or_update_company", lead.id, "created")
        
        return SyncResult(success=True, company_id=ext_id)
    
    def create_or_update_contact(self, lead: LeadData) -> SyncResult:
        if not lead.email and not lead.phone and not lead.owner_name:
            self._log("create_or_update_contact", lead.id, "skipped_no_data")
            return SyncResult(success=False, error="No contact data available")
        
        ext_id = f"mock_contact_{lead.email or lead.phone or hash(lead.owner_name or '') & 0xFFFFFFFF}"
        
        existing = self.contacts.get(ext_id)
        if existing:
            existing.update({
                "name": lead.owner_name or lead.company,
                "email": lead.email,
                "phone": lead.phone,
                "company": lead.company,
            })
            self._log("create_or_update_contact", lead.id, "updated")
        else:
            self.contacts[ext_id] = {
                "name": lead.owner_name or lead.company,
                "email": lead.email,
                "phone": lead.phone,
                "company": lead.company,
                "raw": lead,
            }
            self._log("create_or_update_contact", lead.id, "created")
        
        return SyncResult(success=True, contact_id=ext_id)
    
    def create_lead_or_deal(self, lead: LeadData, company_id: str, contact_id: Optional[str] = None) -> SyncResult:
        ext_id = f"mock_lead_{lead.id}"
        
        existing = self.leads.get(ext_id)
        if existing:
            existing.update({
                "title": lead.title,
                "description": lead.description,
                "score": lead.score,
                "company_id": company_id,
                "contact_id": contact_id,
                "source": lead.source_type,
            })
            self._log("create_lead_or_deal", lead.id, "updated")
        else:
            self.leads[ext_id] = {
                "title": lead.title,
                "description": lead.description,
                "score": lead.score,
                "company_id": company_id,
                "contact_id": contact_id,
                "source": lead.source_type,
                "raw": lead,
            }
            self._log("create_lead_or_deal", lead.id, "created")
        
        return SyncResult(success=True, lead_id=ext_id)
