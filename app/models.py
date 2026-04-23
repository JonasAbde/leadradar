from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./leadradar.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    stripe_customer_id = Column(String, nullable=True)
    subscription_tier = Column(String, default="free")  # free, pro, agency
    created_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)
    
    sources = relationship("Source", back_populates="user")
    leads = relationship("Lead", back_populates="user")

class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    source_type = Column(String)  # cvr, job, news, competitor
    url = Column(String)
    config = Column(Text, default="{}")  # JSON config
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
    status = Column(String, default="new")  # new, contacted, qualified, won, lost
    score = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    notified = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="leads")

class CompetitorSnapshot(Base):
    __tablename__ = "competitor_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    competitor_name = Column(String)
    url = Column(String)
    price = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    changes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
