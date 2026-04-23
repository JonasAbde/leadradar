#!/bin/bash
# Deploy LeadRadar to local VPS

cd ~/leadradar
source venv/bin/activate

# Ensure data dir exists
mkdir -p data

# Kill existing instance
pkill -f "python run.py" || true

# Start in background
nohup python run.py > data/server.log 2>&1 &

echo "LeadRadar started on http://$(hostname -I | awk '{print $1}'):8000"
echo "Logs: tail -f ~/leadradar/data/server.log"
