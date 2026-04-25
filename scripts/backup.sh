#!/bin/bash
# LeadRadar Database Backup
# Usage: cron daily or manual
# Keeps last 7 backups, runs silent (no stdout/stderr unless error)

set -euo pipefail

DB="/home/ubuntu/leadradar/data/leadradar.db"
BACKUP_DIR="/home/ubuntu/leadradar/backups"
KEEP=7

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB" ]; then
    echo "ERROR: Database not found at $DB" >&2
    exit 1
fi

# Create timestamped backup using atomic copy
TS=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/leadradar_${TS}.db"
cp "$DB" "$BACKUP_FILE"

# Verify backup was created and is non-empty
if [ ! -s "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file is empty" >&2
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Keep only the last N backups
cd "$BACKUP_DIR"
ls -1t leadradar_*.db 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --

exit 0
