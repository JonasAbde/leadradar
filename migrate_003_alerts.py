#!/usr/bin/env python3
"""
Migration 003: Real-Time Alerts
Adds alerts table + user notification preferences.
Safe to re-run (checks before creating).
"""

import sqlite3, os
from pathlib import Path

DB = Path(__file__).resolve().parent / "data" / "leadradar.db"
assert DB.exists(), f"Database not found: {DB}"

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())

def table_exists(cursor, table):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None

conn = sqlite3.connect(DB)
c = conn.cursor()

# ── alerts table ─────────────────────────────────────────────────
if not table_exists(c, "alerts"):
    c.execute("""
        CREATE TABLE alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_type TEXT NOT NULL,
            event TEXT NOT NULL,
            severity TEXT DEFAULT 'info',
            message TEXT NOT NULL,
            lead_id INTEGER,
            link_path TEXT,
            read INTEGER DEFAULT 0,
            sent_email INTEGER DEFAULT 0,
            sent_slack INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
        )
    """)
    c.execute("CREATE INDEX idx_alerts_user ON alerts(user_id)")
    c.execute("CREATE INDEX idx_alerts_read ON alerts(read)")
    c.execute("CREATE INDEX idx_alerts_created ON alerts(created_at)")
    print("✅ Created table: alerts")
else:
    print("⚠️  Table 'alerts' already exists — skipping creation")

# ── user_notification_prefs table ────────────────────────────────
if not table_exists(c, "user_notification_prefs"):
    c.execute("""
        CREATE TABLE user_notification_prefs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            new_lead_web INTEGER DEFAULT 1,
            new_lead_email INTEGER DEFAULT 0,
            new_lead_slack INTEGER DEFAULT 0,
            slack_webhook_url TEXT,
            email_digest INTEGER DEFAULT 0,
            digest_hour INTEGER DEFAULT 7,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    print("✅ Created table: user_notification_prefs")
else:
    print("⚠️  Table 'user_notification_prefs' already exists — skipping creation")

conn.commit()
conn.close()
print("🎉 Migration 003 complete")
