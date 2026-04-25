#!/usr/bin/env python3
"""Migrate LeadRadar data from SQLite to PostgreSQL."""
import os
import sys

sys.path.insert(0, "/home/ubuntu/leadradar")

# Read from SQLite
os.environ["DATABASE_URL"] = "sqlite:///./data/leadradar.db"
from app import models
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Connect to both databases
sqlite_engine = models.engine
pg_engine = create_engine("postgresql://leadradar:leadradar_secure_pass@localhost/leadradar")

SQLiteSession = sessionmaker(bind=sqlite_engine)
PGSession = sessionmaker(bind=pg_engine)

sqlite_s = SQLiteSession()
pg_s = PGSession()

# Drop and recreate tables in PostgreSQL
print("Creating PostgreSQL tables...")
models.Base.metadata.drop_all(pg_engine)
models.Base.metadata.create_all(pg_engine)

def copy_table(sqlite_session, pg_session, model_cls):
    """Copy all rows from SQLite to PostgreSQL for a given model."""
    rows = sqlite_session.query(model_cls).all()
    if not rows:
        print(f"  {model_cls.__tablename__}: 0 rows")
        return 0
    
    count = 0
    for old_row in rows:
        kwargs = {}
        for col in model_cls.__table__.columns:
            kwargs[col.name] = getattr(old_row, col.name)
        
        new_row = model_cls(**kwargs)
        pg_session.add(new_row)
        count += 1
    
    pg_session.commit()
    print(f"  {model_cls.__tablename__}: {count} rows")
    return count

try:
    print("Migrating data...")
    total = 0
    # Order matters for FK constraints
    total += copy_table(sqlite_s, pg_s, models.User)
    total += copy_table(sqlite_s, pg_s, models.Source)
    total += copy_table(sqlite_s, pg_s, models.Lead)
    total += copy_table(sqlite_s, pg_s, models.UserNotificationPreference)
    total += copy_table(sqlite_s, pg_s, models.Alert)
    total += copy_table(sqlite_s, pg_s, models.CRMProviderConfig)
    total += copy_table(sqlite_s, pg_s, models.CRMSyncQueue)
    
    # Fix sequences
    pg_s.execute(text("SELECT setval('users_id_seq', (SELECT MAX(id) FROM users))"))
    pg_s.execute(text("SELECT setval('sources_id_seq', (SELECT MAX(id) FROM sources))"))
    pg_s.execute(text("SELECT setval('leads_id_seq', (SELECT MAX(id) FROM leads))"))
    pg_s.commit()
    
    print(f"\nTotal: {total} rows migrated successfully.")
    print("Next: update .env DATABASE_URL and restart the service.")
    
except Exception as e:
    pg_s.rollback()
    print(f"Migration failed: {e}")
    raise
finally:
    sqlite_s.close()
    pg_s.close()
