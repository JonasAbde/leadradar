#!/usr/bin/env python3
"""
Migration 005: Lead Actions
Adds user action columns to leads table: is_relevant, notes, follow_up_date.
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

columns = [
    ("is_relevant", "INTEGER"),
    ("notes", "TEXT"),
    ("follow_up_date", "TEXT"),
]

for col_name, col_type in columns:
    if column_exists(c, "leads", col_name):
        print(f"⚠️  Column '{col_name}' already exists — skipping")
    else:
        c.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")
        print(f"✅ Added column: {col_name} ({col_type})")

conn.commit()
conn.close()
print("🎉 Migration 005 complete")
