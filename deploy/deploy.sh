#!/bin/bash
set -euo pipefail

echo "=== LeadRadar Deploy Script ==="

# 1. Install dependencies
echo "[1/6] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq nginx certbot python3-certbot-nginx

# 2. Setup app service
echo "[2/6] Setting up systemd service..."
sudo cp deploy/leadradar.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable leadradar

# 3. Setup nginx
echo "[3/6] Configuring nginx..."
sudo cp deploy/nginx-leadradar.conf /etc/nginx/sites-available/leadradar
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/leadradar /etc/nginx/sites-enabled/
sudo nginx -t

# 4. Database migrations
echo "[4/6] Running database migrations..."
cd /home/ubuntu/leadradar
source venv/bin/activate
alembic upgrade head || echo "Alembic not configured, skipping"

# 5. Start services
echo "[5/6] Starting services..."
sudo systemctl restart leadradar
sudo systemctl restart nginx

# 6. SSL (manual step)
echo "[6/6] SSL setup (manual)..."
echo "Run: sudo certbot --nginx -d yourdomain.dk -d www.yourdomain.dk"
echo ""

echo "=== Deploy complete ==="
echo "App:    http://$(curl -s ifconfig.me)"
echo "Status: sudo systemctl status leadradar"
