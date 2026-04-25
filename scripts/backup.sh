#!/bin/bash
# LeadRadar daily DB backup
# Run via cron at 03:00 or systemd timer

set -euo pipefail

DB_FILE="/home/ubuntu/leadradar/data/leadradar.db"
BACKUP_DIR="/home/ubuntu/backups"
DATE=$(date +%Y-%m-%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/leadradar-$DATE.db"
KEEP_DAYS=30

# Create backup dir if missing
mkdir -p "$BACKUP_DIR"

# SQLite backup (safe copy while DB is open)
sqlite3 "$DB_FILE" ".backup '$BACKUP_FILE'"

# Compress
gzip -f "$BACKUP_FILE"

# Clean old backups (>30 days)
find "$BACKUP_DIR" -name 'leadradar-*.db.gz' -mtime +$KEEP_DAYS -delete

echo "[$(date -Iseconds)] Backup created: ${BACKUP_FILE}.gz"
