#!/bin/bash
# LeadRadar DB backup — run via cron daily
DB="/home/ubuntu/leadradar/data/leadradar.db"
BACKUP_DIR="/home/ubuntu/leadradar/backups"
mkdir -p "$BACKUP_DIR"
TS=$(date +%Y%m%d_%H%M%S)
cp "$DB" "$BACKUP_DIR/leadradar_${TS}.db"
find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete
