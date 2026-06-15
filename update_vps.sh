#!/bin/bash
# =============================================================================
# update_vps.sh — Lightweight code update (NO system package reinstall)
# Run this for every code update after the initial setup_vps.sh was completed.
# Usage: bash update_vps.sh
# =============================================================================
set -e

echo "======================================================"
echo " AdsPilot — Code Update Deploy"
echo "======================================================"

# ── 1. Extract new code ────────────────────────────────────────────────────
echo ""
echo "[1/4] Extracting deploy_new.zip..."
if [ ! -f "deploy_new.zip" ]; then
    echo "ERROR: deploy_new.zip not found in the current directory!"
    exit 1
fi
unzip -o deploy_new.zip -d /var/www/
chown -R www-data:www-data /var/www/ || true   # non-fatal: www-data may not exist on all VPS configs
echo "Code extracted to /var/www/"

# ── 2. Backend: install any new npm deps + restart ────────────────────────
echo ""
echo "[2/4] Updating backend dependencies..."
cd /var/www/backend
npm install --omit=dev
echo "Dependencies up to date."

# ── 3. Restart backend via PM2 ────────────────────────────────────────────
echo ""
echo "[3/4] Restarting backend via PM2..."
pm2 restart adspilot-api --update-env || pm2 start server.js --name adspilot-api
pm2 save
echo "Backend restarted."
pm2 list

# ── 4. Reload Nginx (no restart needed for static file changes) ───────────
echo ""
echo "[4/4] Reloading Nginx..."
nginx -t && nginx -s reload
echo "Nginx reloaded."

cd /root
echo ""
echo "======================================================"
echo " Update Complete!"
echo "======================================================"
echo ""
echo "  AdsPilot → https://adspilot.pawgrammers.io.vn"
echo "  API      → https://api.pawgrammers.io.vn/api/health"
echo ""
echo "  PM2 logs: pm2 logs adspilot-api"
echo "======================================================"
