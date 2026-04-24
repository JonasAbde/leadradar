"""CRM Sync Worker — process sync queue, retry logic, safe to rerun.

Design rules:
- Never blocks scraper — queue is async
- Safe to stop and resume (uses DB state)
- Exponential backoff on failures
- Mock provider used by default (no external calls without config)
"""

import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Type
from sqlalchemy.orm import Session

from .crm import BaseCRMProvider, LeadData
from .crm.mock_provider import MockCRMProvider
from .crm.hubspot_provider import HubSpotProvider

# Provider registry — extend here
PROVIDER_MAP: dict[str, Type[BaseCRMProvider]] = {
    "mock": MockCRMProvider,
    "hubspot": HubSpotProvider,
}

def get_provider(provider_name: str, config: dict):
    """Factory: get CRM provider by name."""
    cls = PROVIDER_MAP.get(provider_name)
    if not cls:
        raise ValueError(f"Unknown CRM provider: {provider_name}")
    return cls(config)


def _build_lead_data(lead, db=None) -> LeadData:
    """Convert DB Lead model to canonical LeadData."""
    source_type = None
    source_name = None
    if db is not None and lead.source_id:
        from app import models
        s = db.query(models.Source).filter(models.Source.id == lead.source_id).first()
        if s:
            source_type = s.source_type
            source_name = s.name
    elif hasattr(lead, 'source') and lead.source:
        source_type = lead.source.source_type
        source_name = lead.source.name
    
    return LeadData(
        id=lead.id,
        title=lead.title or "",
        company=lead.company or "",
        description=lead.description,
        url=lead.url,
        location=lead.location,
        score=lead.score or 0,
        cvr_number=lead.cvr_number,
        phone=lead.phone,
        email=lead.contact_email,
        address=lead.address,
        zipcode=lead.zipcode,
        city=lead.city,
        industry_desc=lead.industry_desc,
        company_type=lead.company_type,
        employee_count=lead.employee_count,
        owner_name=lead.owner_name,
        source_type=source_type,
        source_name=source_name,
    )


def _make_idempotency_key(lead_id: int) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d")
    return hashlib.sha256(f"{lead_id}:{ts}".encode()).hexdigest()[:16]


def process_sync_queue(db: Session, max_jobs: int = 10) -> dict:
    """Process pending CRM sync jobs from queue.
    
    Returns summary of processed jobs.
    Safe to call repeatedly — idempotent.
    """
    from app import models
    
    # Find jobs ready to run
    jobs = db.query(models.CRMSyncQueue).filter(
        models.CRMSyncQueue.status.in_(["pending", "failed"]),
        models.CRMSyncQueue.attempts < models.CRMSyncQueue.max_attempts,
    ).filter(
        (models.CRMSyncQueue.next_retry_at == None) | 
        (models.CRMSyncQueue.next_retry_at <= datetime.utcnow())
    ).order_by(models.CRMSyncQueue.created_at).limit(max_jobs).all()
    
    summary = {"processed": 0, "success": 0, "failed": 0, "skipped": 0}
    
    for job in jobs:
        try:
            # Mark in_progress
            job.status = "in_progress"
            db.commit()
            
            # Get lead
            lead = db.query(models.Lead).filter(
                models.Lead.id == job.lead_id,
                models.Lead.user_id == job.user_id
            ).first()
            
            if not lead:
                job.status = "failed"
                job.error = "Lead not found"
                db.commit()
                summary["failed"] += 1
                continue
            
            # Get user's CRM config
            config = db.query(models.CRMProviderConfig).filter(
                models.CRMProviderConfig.user_id == job.user_id,
                models.CRMProviderConfig.provider == job.provider,
                models.CRMProviderConfig.enabled == True
            ).first()
            
            if not config:
                job.status = "failed"
                job.error = "No CRM config enabled for this provider"
                db.commit()
                summary["skipped"] += 1
                continue
            
            # Build provider
            provider_config = {}
            try:
                import json
                provider_config = json.loads(config.config_json or "{}")
            except:
                pass
            
            # Add token from env if available (for HubSpot)
            if job.provider == "hubspot":
                token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "")
                if token:
                    provider_config["token"] = token
            
            provider = get_provider(job.provider, provider_config)
            
            # Check connection
            if not provider.test_connection():
                job.status = "failed"
                job.error = "CRM connection test failed"
                job.attempts += 1
                # Set retry
                backoff = min(2 ** job.attempts, 3600)  # Max 1 hour
                job.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff)
                db.commit()
                summary["failed"] += 1
                continue
            
            # Sync
            lead_data = _build_lead_data(lead, db)
            result = provider.sync_lead(lead_data)
            
            if result.success:
                job.status = "done"
                lead.crm_provider = job.provider
                lead.crm_external_company_id = result.company_id
                lead.crm_external_contact_id = result.contact_id
                lead.crm_external_lead_id = result.lead_id
                lead.crm_sync_status = "synced"
                lead.crm_last_sync_at = datetime.utcnow()
                lead.crm_last_error = None
                lead.crm_sync_attempts = (lead.crm_sync_attempts or 0) + 1
                lead.crm_idempotency_key = _make_idempotency_key(lead.id)
                db.commit()
                summary["success"] += 1
            else:
                job.status = "failed"
                job.error = result.error or "Unknown sync error"
                job.attempts += 1
                backoff = min(2 ** job.attempts, 3600)
                job.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff)
                
                lead.crm_sync_status = "failed"
                lead.crm_last_error = result.error
                lead.crm_sync_attempts = (lead.crm_sync_attempts or 0) + 1
                db.commit()
                summary["failed"] += 1
            
            summary["processed"] += 1
            
        except Exception as e:
            db.rollback()
            job.status = "failed"
            job.error = str(e)[:500]
            job.attempts += 1
            backoff = min(2 ** job.attempts, 3600)
            job.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff)
            db.commit()
            summary["failed"] += 1
            summary["processed"] += 1
    
    return summary


def enqueue_lead_sync(db: Session, lead_id: int, user_id: int, provider: str = "mock") -> bool:
    """Add a lead to CRM sync queue. Returns True if enqueued."""
    from app import models
    
    # Check if already pending
    existing = db.query(models.CRMSyncQueue).filter(
        models.CRMSyncQueue.lead_id == lead_id,
        models.CRMSyncQueue.status.in_(["pending", "in_progress"])
    ).first()
    
    if existing:
        return False
    
    job = models.CRMSyncQueue(
        lead_id=lead_id,
        user_id=user_id,
        provider=provider,
        status="pending"
    )
    db.add(job)
    db.commit()
    return True
