#!/usr/bin/env python3
"""Quick migration for SQLite: add enrichment columns to leads table."""
import sqlite3, os

db_path = os.path.expanduser("~/leadradar/data/leadradar.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

new_columns = [
    ("cvr_number", "TEXT"),
    ("address", "TEXT"),
    ("zipcode", "TEXT"),
    ("city", "TEXT"),
    ("industry_code", "TEXT"),
    ("industry_desc", "TEXT"),
    ("company_type", "TEXT"),
    ("employee_count", "INTEGER"),
    ("owner_name", "TEXT"),
    ("enriched", "INTEGER DEFAULT 0"),
    ("enriched_at", "TEXT"),
    ("enrichment_data", "TEXT"),
]

for col_name, col_type in new_columns:
    try:
        cursor.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")
        print(f"✅ Added column: {col_name}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print(f"⏩ Column {col_name} already exists")
        else:
            print(f"❌ Error adding {col_name}: {e}")

conn.commit()
conn.close()
print("Migration complete.")
