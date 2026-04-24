"""CRM Provider Interface — LeadRadar CRM abstraction layer.

All CRM adapters implement this interface. Consumers (sync worker, dashboard)
never touch provider internals — only call methods on BaseCRMProvider.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class LeadData:
    """Canonical lead data passed to all CRM providers."""
    id: int  # LeadRadar internal ID
    title: str
    company: str
    description: Optional[str] = None
    url: Optional[str] = None
    location: Optional[str] = None
    score: int = 0
    # Enrichment
    cvr_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    zipcode: Optional[str] = None
    city: Optional[str] = None
    industry_desc: Optional[str] = None
    company_type: Optional[str] = None
    employee_count: Optional[int] = None
    owner_name: Optional[str] = None
    # Source
    source_type: Optional[str] = None
    source_name: Optional[str] = None


@dataclass
class SyncResult:
    """Result of a CRM sync operation."""
    success: bool
    company_id: Optional[str] = None
    contact_id: Optional[str] = None
    lead_id: Optional[str] = None
    error: Optional[str] = None
    raw_response: Optional[Dict] = None


class BaseCRMProvider(ABC):
    """Interface all CRM providers must implement."""
    
    name: str = "base"
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    @abstractmethod
    def test_connection(self) -> bool:
        """Return True if credentials work and API is reachable."""
        pass
    
    @abstractmethod
    def create_or_update_company(self, lead: LeadData) -> SyncResult:
        """Create or update company in CRM. Return external company ID."""
        pass
    
    @abstractmethod
    def create_or_update_contact(self, lead: LeadData) -> SyncResult:
        """Create or update contact person. Return external contact ID."""
        pass
    
    @abstractmethod
    def create_lead_or_deal(self, lead: LeadData, company_id: str, contact_id: Optional[str] = None) -> SyncResult:
        """Create lead/deal in CRM. Return external lead/deal ID."""
        pass
    
    def sync_lead(self, lead: LeadData) -> SyncResult:
        """Full sync: company → contact → lead. Override if provider needs special flow."""
        company_result = self.create_or_update_company(lead)
        if not company_result.success:
            return company_result
        
        contact_result = self.create_or_update_contact(lead)
        # Contact may be optional — don't fail if not found
        
        lead_result = self.create_lead_or_deal(
            lead,
            company_id=company_result.company_id,
            contact_id=contact_result.contact_id if contact_result.success else None
        )
        
        return SyncResult(
            success=lead_result.success,
            company_id=company_result.company_id,
            contact_id=contact_result.contact_id if contact_result.success else None,
            lead_id=lead_result.lead_id,
            error=lead_result.error,
            raw_response=lead_result.raw_response
        )
