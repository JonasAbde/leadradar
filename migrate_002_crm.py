#!/usr/bin/env python3
"""Migration 002: Add CRM sync tables and fields."""
import sqlite3, os

db_path = os.path.expanduser("~/leadradar/data/leadradar.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Add CRM fields to leads
lead_crm_cols = [
    ("crm_provider", "TEXT"),
    ("crm_external_company_id", "TEXT"),
    ("crm_external_contact_id", "TEXT"),
    ("crm_external_lead_id", "TEXT"),
    ("crm_sync_status", "TEXT"),
    ("crm_last_sync_at", "TEXT"),
    ("crm_last_error", "TEXT"),
    ("crm_sync_attempts", "INTEGER DEFAULT 0"),
    ("crm_idempotency_key", "TEXT"),
]

for col_name, col_type in lead_crm_cols:
    try:
        cursor.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")
        print(f"✅ leads.{col_name}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print(f"⏩ leads.{col_name}")
        else:
            print(f"❌ leads.{col_name}: {e}")

# Create crm_sync_queue table
try:
    cursor.execute("""
        CREATE TABLE crm_sync_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            attempts INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 5,
            error TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            next_retry_at TEXT
        )
    """)
    print("✅ Table crm_sync_queue created")
except sqlite3.OperationalError as e:
    if "already exists" in str(e):
        print("⏩ Table crm_sync_queue already exists")
    else:
        print(f"❌ crm_sync_queue: {e}")

# Create crm_provider_configs table
try:
    cursor.execute("""
        CREATE TABLE crm_provider_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            enabled BOOLEAN DEFAULT 0,
            auto_sync BOOLEAN DEFAULT 0,
            config_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ Table crm_provider_configs created")
except sqlite3.OperationalError as e:
    if "already exists" in str(e):
        print("⏩ Table crm_provider_configs already exists")
    else:
        print(f"❌ crm_provider_configs: {e}")

conn.commit()
conn.close()
print("Migration 002 complete.")
