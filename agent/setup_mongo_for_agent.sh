#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# VPS MongoDB Setup Script for E4b Agent Backend
# Run once on VPS as root or sudo user
#
# What this does:
#   1. Binds MongoDB to 0.0.0.0 (all interfaces)
#   2. Creates a dedicated agent user in camp_ads DB
#   3. Opens port 27017 in firewall
#   4. Restarts MongoDB
#
# Usage:
#   chmod +x setup_mongo_for_agent.sh
#   sudo bash setup_mongo_for_agent.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

MONGO_DB="camp_ads"
AGENT_USER="agent"
AGENT_PASS="camp_ads_agent_2026"  # Change this to a strong password

echo "[1/4] Updating MongoDB config to bind to 0.0.0.0..."
MONGOD_CONF="/etc/mongod.conf"

if [ -f "$MONGOD_CONF" ]; then
    # Replace bindIp line
    sed -i 's/bindIp: 127.0.0.1/bindIp: 0.0.0.0/' "$MONGOD_CONF"
    echo "      Done: bindIp set to 0.0.0.0"
else
    echo "      WARNING: $MONGOD_CONF not found — adding net config manually"
    cat >> "$MONGOD_CONF" <<EOF

net:
  bindIp: 0.0.0.0
  port: 27017
EOF
fi

echo "[2/4] Restarting MongoDB..."
systemctl restart mongod
sleep 3
systemctl status mongod --no-pager | grep "Active:"

echo "[3/4] Creating agent DB user..."
mongosh "$MONGO_DB" --eval "
  db.createUser({
    user: '${AGENT_USER}',
    pwd: '${AGENT_PASS}',
    roles: [{ role: 'readWrite', db: '${MONGO_DB}' }]
  });
  print('User created: ${AGENT_USER}');
" 2>/dev/null || echo "      User may already exist — skipping"

echo "[4/4] Opening firewall port 27017..."
if command -v ufw &>/dev/null; then
    ufw allow 27017/tcp
    ufw status | grep 27017
    echo "      TIP: Restrict to agent IP for security:"
    echo "      ufw delete allow 27017/tcp"
    echo "      ufw allow from <AGENT_IP> to any port 27017"
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --permanent --add-port=27017/tcp
    firewall-cmd --reload
fi

echo ""
echo "========================================="
echo "Setup complete!"
echo ""
echo "Add this to your agent .env:"
echo "  MONGODB_URI=mongodb://${AGENT_USER}:${AGENT_PASS}@api.pawgrammers.io.vn:27017/${MONGO_DB}"
echo ""
echo "Test connection:"
echo "  mongosh 'mongodb://${AGENT_USER}:${AGENT_PASS}@api.pawgrammers.io.vn:27017/${MONGO_DB}'"
echo "========================================="
