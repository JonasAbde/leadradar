#!/usr/bin/env python3
import sqlite3, os, shutil

ACTIVE = 'data/leadradar.db'
LEGACY = 'data/leadradar_legacy.db'
BACKUP = 'data/leadradar.db.pre_merge'

# Check active db
conn_a = sqlite3.connect(ACTIVE)
tables_active = [r[0] for r in conn_a.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()]
print("Active tables:", tables_active)

conn_l = sqlite3.connect(LEGACY)
tables_legacy = [r[0] for r in conn_l.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()]
print("Legacy tables:", tables_legacy)

# Print row counts for active
for t in tables_active:
    n = conn_a.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  active.{t}: {n} rows")

# Print row counts for legacy
for t in tables_legacy:
    n = conn_l.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  legacy.{t}: {n} rows")

# Check schema differences
common = set(tables_active) & set(tables_legacy) - {'sqlite_sequence'}
print(f"\nCommon tables: {common}")

for t in common:
    cols_a = set(r[1] for r in conn_a.execute(f"PRAGMA table_info({t})").fetchall())
    cols_l = set(r[1] for r in conn_l.execute(f"PRAGMA table_info({t})").fetchall())
    extra_in_active = cols_a - cols_l
    extra_in_legacy = cols_l - cols_a
    if extra_in_active:
        print(f"  {t}: Active has extra cols: {extra_in_active}")
    if extra_in_legacy:
        print(f"  {t}: Legacy has extra cols: {extra_in_legacy}")

conn_a.close()
conn_l.close()

# Now merge only rows from tables where schemas are compatible
print("\n=== MERGING ===")

# Backup
shutil.copy2(ACTIVE, BACKUP)
print(f"Backup: {BACKUP}")

conn_a = sqlite3.connect(ACTIVE)
conn_l = sqlite3.connect(LEGACY)
conn_a.execute(f"ATTACH DATABASE '{LEGACY}' AS legacy")

total_added = 0

for t in common:
    cols_a = set(r[1] for r in conn_a.execute(f"PRAGMA table_info({t})").fetchall())
    cols_l = set(r[1] for r in conn_l.execute(f"PRAGMA table_info({t})").fetchall())
    
    # Only merge if legacy columns are a subset of active columns
    if not cols_l.issubset(cols_a):
        print(f"  {t}: SKIPPED — schema incompatible (legacy has extra cols: {cols_l - cols_a})")
        continue
    
    before = conn_a.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    col_str = ', '.join(cols_l)
    
    conn_a.execute(f"""
        INSERT OR IGNORE INTO {t} ({col_str})
        SELECT {col_str} FROM legacy.{t}
    """)
    conn_a.commit()
    
    after = conn_a.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    added = after - before
    total_added += added
    if added > 0:
        print(f"  {t}: +{added} rows")
    else:
        print(f"  {t}: no new rows")

conn_a.close()
conn_l.close()

print(f"\nMerge complete! Total rows added: {total_added}")
print(f"Active DB size: {os.path.getsize(ACTIVE)} bytes")

# Clean up legacy
os.rename(LEGACY, LEGACY + '.merged')
print(f"Legacy DB renamed to {LEGACY}.merged (safe to delete)")
