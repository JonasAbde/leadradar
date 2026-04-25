#!/usr/bin/env python3
"""
Merge orphan leadradar.db into data/leadradar.db.

Migrates users, sources, and leads from the root-level leadradar.db
to the canonical data/leadradar.db if they don't already exist.
Safe and idempotent — can be run multiple times without side effects.

Usage:
    python scripts/merge_dbs.py
"""

import sqlite3
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORPHAN_DB = os.path.join(ROOT_DIR, "leadradar.db")
ACTIVE_DB = os.path.join(ROOT_DIR, "data", "leadradar.db")


def get_tables(conn):
    """Return set of table names in a database."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return {row[0] for row in cur.fetchall()}


def get_columns(conn, table):
    """Return list of column names for a table."""
    cur = conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def merge_table(
    orphan_conn, active_conn, table, key_col="id", cols=None
):
    """
    Copy rows from orphan DB to active DB where primary key does not exist.
    Uses INSERT OR IGNORE for idempotency.
    """
    if cols is None:
        cols = get_columns(orphan_conn, table)

    active_tables = get_tables(active_conn)
    if table not in active_tables:
        print(f"  ⚠ Table '{table}' not found in active DB, skipping.")
        return 0

    orphan_cols = get_columns(orphan_conn, table)
    for c in cols:
        if c not in orphan_cols:
            cols.remove(c)
            print(f"  ⚠ Column '{c}' not in orphan DB '{table}', skipping.")

    col_list = ", ".join(cols)
    placeholders = ", ".join(["?" for _ in cols])

    # Fetch all rows from orphan
    orphan_rows = orphan_conn.execute(f"SELECT {col_list} FROM {table}").fetchall()

    inserted = 0
    for row in orphan_rows:
        # Check if key already exists
        key_val = row[cols.index(key_col)] if key_col in cols else None
        if key_val is not None:
            existing = active_conn.execute(
                f"SELECT 1 FROM {table} WHERE {key_col} = ?", (key_val,)
            ).fetchone()
            if existing:
                continue  # Already exists, skip

        try:
            active_conn.execute(
                f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
                row,
            )
            inserted += 1
        except sqlite3.IntegrityError as e:
            print(f"  ⚠ Conflict inserting into {table} key={key_val}: {e}")
            continue

    return inserted


def main():
    if not os.path.exists(ORPHAN_DB):
        print("No orphan DB found at leadradar.db — nothing to merge.")
        return

    if not os.path.exists(ACTIVE_DB):
        print("No active DB found at data/leadradar.db — nothing to merge into.")
        return

    print(f"Orphan DB: {ORPHAN_DB}")
    print(f"Active DB: {ACTIVE_DB}")
    print()

    orphan_conn = sqlite3.connect(ORPHAN_DB)
    active_conn = sqlite3.connect(ACTIVE_DB)

    total_moved = 0
    tables_to_merge = [
        {"table": "users", "key_col": "id"},
        {"table": "sources", "key_col": "id"},
        {"table": "leads", "key_col": "id"},
    ]

    orphan_tables = get_tables(orphan_conn)
    active_tables = get_tables(active_conn)

    for spec in tables_to_merge:
        table = spec["table"]
        key = spec["key_col"]
        if table not in orphan_tables:
            print(f"  Skipping '{table}' — not in orphan DB.")
            continue
        if table not in active_tables:
            print(f"  Skipping '{table}' — not in active DB.")
            continue

        count = merge_table(orphan_conn, active_conn, table, key)
        print(f"  ✓ Merged {count} rows into '{table}'.")
        total_moved += count

    orphan_conn.close()
    active_conn.commit()
    active_conn.close()

    if total_moved == 0:
        print("\nNo new data to merge. Databases are in sync.")
    else:
        print(f"\n✓ Done. Merged {total_moved} total rows.")


if __name__ == "__main__":
    main()
