#!/usr/bin/env python3
"""
Migration 004: TED Tender Fields
Adds TED-specific columns to the leads table for storing EU tender data.
Safe to re-run (checks columns before adding).
"""

import sqlite3
import os
from pathlib import Path

DB = Path(__file__).resolve().parent / "data" / "leadradar.db"
assert DB.exists(), f"Database not found: {DB}"

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())

conn = sqlite3.connect(DB)
c = conn.cursor()

# ── TED fields on leads table ─────────────────────────────────────

columns = [
    ("notice_identifier", "TEXT"),
    ("notice_idempotency_key", "TEXT"),
    ("cpv_values", "TEXT"),
    ("estimated_value", "REAL"),
    ("deadline_date", "TEXT"),
    ("procurement_type", "TEXT"),
    ("notice_subtype", "TEXT"),
    ("source_url", "TEXT"),
    ("buyer_country", "TEXT DEFAULT 'DNK'"),
    ("data_source", "TEXT DEFAULT 'ted'"),
    ("is_stale", "INTEGER DEFAULT 0"),
    ("last_seen_at", "TEXT"),
]

for col_name, col_type in columns:
    if column_exists(c, "leads", col_name):
        print(f"⚠️  Column '{col_name}' already exists — skipping")
    else:
        c.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")
        print(f"✅ Added column: {col_name} ({col_type})")

conn.commit()
conn.close()
print("🎉 Migration 004 complete")
