from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/leadradar.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String, nullable=True)
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    subscription_tier = Column(String, default="free")  # free, pro, agency
    subscription_status = Column(String, default="active")  # active, canceled, past_due
    created_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)
    email_confirmed = Column(Boolean, default=False)
    
    sources = relationship("Source", back_populates="user", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="user", cascade="all, delete-orphan")

class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    source_type = Column(String)  # cvr, job, news, competitor
    url = Column(String)
    config = Column(Text, default="{}")
    last_scraped = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)
    
    user = relationship("User", back_populates="sources")

class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    source_id = Column(Integer, ForeignKey("sources.id"))
    title = Column(String)
    description = Column(Text)
    url = Column(String)
    company = Column(String)
    contact_email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    location = Column(String, nullable=True)
    status = Column(String, default="new")
    score = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    notified = Column(Boolean, default=False)
    
    # Enrichment fields from CVR API
    cvr_number = Column(String, nullable=True)
    address = Column(String, nullable=True)
    zipcode = Column(String, nullable=True)
    city = Column(String, nullable=True)
    industry_code = Column(String, nullable=True)
    industry_desc = Column(String, nullable=True)
    company_type = Column(String, nullable=True)
    employee_count = Column(Integer, nullable=True)
    owner_name = Column(String, nullable=True)
    enriched = Column(Boolean, default=False)
    enriched_at = Column(DateTime, nullable=True)
    enrichment_data = Column(Text, nullable=True)  # JSON blob of raw enrichment
    
    # CRM sync status (new fields)
    crm_provider = Column(String, nullable=True)  # "mock", "hubspot", "pipedrive"
    crm_external_company_id = Column(String, nullable=True)
    crm_external_contact_id = Column(String, nullable=True)
    crm_external_lead_id = Column(String, nullable=True)
    crm_sync_status = Column(String, nullable=True)  # "pending", "synced", "failed"
    crm_last_sync_at = Column(DateTime, nullable=True)
    crm_last_error = Column(Text, nullable=True)
    crm_sync_attempts = Column(Integer, default=0)
    crm_idempotency_key = Column(String, nullable=True)  # lead_id + timestamp hash
    
    # ── TED Tender fields ──
    notice_identifier = Column(String, nullable=True)        # TED notice identifier
    notice_idempotency_key = Column(String, nullable=True, unique=True)  # pub_number for dedup
    cpv_values = Column(Text, nullable=True)                 # JSON array of CPV codes
    estimated_value = Column(Float, nullable=True)           # EUR value
    deadline_date = Column(String, nullable=True)            # Tender deadline
    procurement_type = Column(String, nullable=True)         # procedure-type
    notice_subtype = Column(String, nullable=True)           # notice-subtype
    source_url = Column(String, nullable=True)               # TED notice URL
    buyer_country = Column(String, default="DNK")            # ISO 3166-1 alpha-3
    data_source = Column(String, default="ted")              # "ted", "cvr", etc.
    is_stale = Column(Boolean, default=False)                # whether notice is expired
    last_seen_at = Column(String, nullable=True)             # last fetch timestamp
    
    user = relationship("User", back_populates="leads")

class CRMSyncQueue(Base):
    __tablename__ = "crm_sync_queue"
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String, nullable=False)  # "mock", "hubspot", "pipedrive"
    status = Column(String, default="pending")  # "pending", "in_progress", "done", "failed"
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    next_retry_at = Column(DateTime, nullable=True)

class CRMProviderConfig(Base):
    __tablename__ = "crm_provider_configs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String, nullable=False)  # "mock", "hubspot", "pipedrive"
    enabled = Column(Boolean, default=False)
    auto_sync = Column(Boolean, default=False)
    config_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ── Real-Time Alerts ────────────────────────────────────

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_type = Column(String, nullable=False)           # "lead", "price_drop", "system"
    event = Column(String, nullable=False)                 # "new_lead", "enrichment_done", "crm_error"
    severity = Column(String, default="info")              # "info", "warning", "critical"
    message = Column(Text, nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    link_path = Column(String, nullable=True)              # e.g. "/dashboard?lead=42"
    read = Column(Boolean, default=False)
    sent_email = Column(Boolean, default=False)
    sent_slack = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserNotificationPreference(Base):
    __tablename__ = "user_notification_prefs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    new_lead_web = Column(Boolean, default=True)
    new_lead_email = Column(Boolean, default=False)
    new_lead_slack = Column(Boolean, default=False)
    slack_webhook_url = Column(String, nullable=True)
    email_digest = Column(Boolean, default=False)          # daily digest vs instant
    digest_hour = Column(Integer, default=7)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
