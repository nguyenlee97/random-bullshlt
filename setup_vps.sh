#!/bin/bash
# =============================================================================
# VPS Setup Script — Claw-a-thon Ad Platform
# Covers: MongoDB 7, Node.js/PM2, Nginx (all sites + API + frontends), SSL
# =============================================================================
set -e

echo "======================================================================"
echo " Claw-a-thon Ad Platform — VPS Setup"
echo "======================================================================"

# ── 1. System Packages ─────────────────────────────────────────────────────
echo ""
echo "[1/8] Installing system packages..."
apt-get update -qq
apt-get install -y nginx unzip curl gnupg ca-certificates lsb-release

# ── 2. MongoDB 7.x ────────────────────────────────────────────────────────
echo ""
echo "[2/8] Installing MongoDB 7.x Community Edition..."
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc \
    | gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] \
https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" \
    | tee /etc/apt/sources.list.d/mongodb-org-7.0.list
apt-get update -qq
apt-get install -y mongodb-org
systemctl enable mongod
systemctl start mongod
echo "MongoDB status:"
mongod --version

# ── 3. Node.js 20.x + PM2 ────────────────────────────────────────────────
echo ""
echo "[3/8] Installing Node.js 20.x + PM2..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs
npm install -g pm2
echo "Node: $(node -v) | npm: $(npm -v) | PM2: $(pm2 -v)"

# ── 4. Deploy Static Files ────────────────────────────────────────────────
echo ""
echo "[4/8] Extracting website and frontend files..."
if [ ! -f "deploy_new.zip" ]; then
    echo "ERROR: deploy_new.zip not found in the current directory!"
    exit 1
fi

# Unzip everything into /var/www
unzip -o deploy_new.zip -d /var/www/

# Set correct permissions
chown -R www-data:www-data /var/www/
chmod -R 755 /var/www/

echo "Static files deployed to /var/www/"

# ── 5. Backend API Setup ──────────────────────────────────────────────────
echo ""
echo "[5/8] Setting up backend API..."
BACKEND_DIR="/var/www/backend"

if [ ! -d "$BACKEND_DIR" ]; then
    echo "ERROR: $BACKEND_DIR not found after unzip. Check deploy_new.zip structure."
    exit 1
fi

cd "$BACKEND_DIR"
npm install --omit=dev

# Ensure uploads directory exists (for creative images)
mkdir -p "$BACKEND_DIR/uploads"
chown www-data:www-data "$BACKEND_DIR/uploads" 2>/dev/null || true

# Write production .env
cat > .env << 'ENVEOF'
PORT=3000
MONGODB_URI=mongodb://localhost:27017/adspilot
NODE_ENV=production
PUBLIC_BASE_URL=https://api.pawgrammers.io.vn
ALLOWED_ORIGINS=https://adspilot.pawgrammers.io.vn,https://analytics.pawgrammers.io.vn,https://znews-stg.pawgrammers.io.vn,https://baomoi-stg.pawgrammers.io.vn,https://zingmp3-stg.pawgrammers.io.vn
ENVEOF

echo "Running database seed..."
node seed/index.js && echo "Seed complete." || echo "Seed failed (DB may already have data — continuing)"

# Start / restart via PM2
pm2 delete adspilot-api 2>/dev/null || true
pm2 start server.js --name adspilot-api --update-env
pm2 save
pm2 startup systemd -u root --hp /root | tail -1 | bash || true
echo "Backend running via PM2. Status:"
pm2 list

cd /root   # back to home

# ── 6. Nginx Configuration ────────────────────────────────────────────────
echo ""
echo "[6/8] Writing Nginx configurations..."
NGINX_AVAIL="/etc/nginx/sites-available"
NGINX_ENABLED="/etc/nginx/sites-enabled"

# Remove default site
rm -f "$NGINX_ENABLED/default"

# ── 6a. API Backend ───────────────────────────────────────────────────────
cat > "$NGINX_AVAIL/api.pawgrammers.io.vn" << 'EOF'
server {
    listen 80;
    server_name api.pawgrammers.io.vn;

    # Allow up to 25 MB uploads (AI-generated images ~10 MB + base64 overhead)
    client_max_body_size 25m;
    client_body_timeout  60s;

    # Proxy to Node.js backend (API + /uploads static files both served by Express)
    location / {
        proxy_pass         http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 10s;
    }
}
EOF

# ── 6b. AdsPilot Frontend ─────────────────────────────────────────────────
cat > "$NGINX_AVAIL/adspilot.pawgrammers.io.vn" << 'EOF'
server {
    listen 80;
    server_name adspilot.pawgrammers.io.vn;

    root  /var/www/adspilot_frontend;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # No-cache for HTML; long-cache for assets
    location ~* \.html$ {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }
    location ~* \.(js|css|png|jpg|svg|ico)$ {
        expires 7d;
        add_header Cache-Control "public, max-age=604800";
    }
}
EOF

# ── 6c. Analytics Frontend ────────────────────────────────────────────────
cat > "$NGINX_AVAIL/analytics.pawgrammers.io.vn" << 'EOF'
server {
    listen 80;
    server_name analytics.pawgrammers.io.vn;

    root  /var/www/analytics_frontend;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~* \.html$ {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }
    location ~* \.(js|css|png|jpg|svg|ico)$ {
        expires 7d;
        add_header Cache-Control "public, max-age=604800";
    }
}
EOF

# ── 6d. BaoMoi Replicate ──────────────────────────────────────────────────
cat > "$NGINX_AVAIL/baomoi-stg.pawgrammers.io.vn" << 'EOF'
server {
    listen 80;
    server_name baomoi-stg.pawgrammers.io.vn;

    root  /var/www/baomoi_replicate;
    index index.html index.htm;

    location / {
        try_files $uri $uri/ =404;
    }
}
EOF

# ── 6e. ZingMP3 Replicate ─────────────────────────────────────────────────
cat > "$NGINX_AVAIL/zingmp3-stg.pawgrammers.io.vn" << 'EOF'
server {
    listen 80;
    server_name zingmp3-stg.pawgrammers.io.vn;

    root  /var/www/zingmp3_replicate;
    index index.html index.htm;

    location / {
        try_files $uri $uri/ =404;
    }
}
EOF

# ── 6f. Znews Replicate ───────────────────────────────────────────────────
cat > "$NGINX_AVAIL/znews-stg.pawgrammers.io.vn" << 'EOF'
server {
    listen 80;
    server_name znews-stg.pawgrammers.io.vn;

    root  /var/www/znews_replicate;
    index index.html index.htm;

    location / {
        try_files $uri $uri/ =404;
    }
}
EOF

# Enable all sites
for SITE in \
    api.pawgrammers.io.vn \
    adspilot.pawgrammers.io.vn \
    analytics.pawgrammers.io.vn \
    baomoi-stg.pawgrammers.io.vn \
    zingmp3-stg.pawgrammers.io.vn \
    znews-stg.pawgrammers.io.vn; do
    ln -sf "$NGINX_AVAIL/$SITE" "$NGINX_ENABLED/"
    echo "  ✔ Enabled: $SITE"
done

# ── 7. Test and Restart Nginx ─────────────────────────────────────────────
echo ""
echo "[7/8] Testing and restarting Nginx..."
nginx -t && systemctl restart nginx
echo "Nginx is running."

# ── 8. SSL with Certbot (optional) ───────────────────────────────────────
echo ""
echo "[8/8] Installing Certbot and obtaining SSL certificates..."
apt-get install -y certbot python3-certbot-nginx

certbot --nginx \
    -d api.pawgrammers.io.vn \
    -d adspilot.pawgrammers.io.vn \
    -d analytics.pawgrammers.io.vn \
    -d znews-stg.pawgrammers.io.vn \
    -d baomoi-stg.pawgrammers.io.vn \
    -d zingmp3-stg.pawgrammers.io.vn \
    --non-interactive --agree-tos -m admin@pawgrammers.io.vn \
    && echo "SSL certificates obtained." \
    || echo "SSL FAILED — check DNS propagation and retry: certbot --nginx -d <domain>"

# Auto-renewal already set up by certbot; verify:
systemctl enable certbot.timer 2>/dev/null || true

# ── Done ──────────────────────────────────────────────────────────────────
echo ""
echo "======================================================================"
echo " Deployment Complete!"
echo "======================================================================"
echo ""
echo "  API Backend    → https://api.pawgrammers.io.vn"
echo "  AdsPilot FE    → https://adspilot.pawgrammers.io.vn"
echo "  Analytics FE   → https://analytics.pawgrammers.io.vn"
echo "  Znews Test     → https://znews-stg.pawgrammers.io.vn"
echo "  BaoMoi Test    → https://baomoi-stg.pawgrammers.io.vn"
echo "  ZingMP3 Test   → https://zingmp3-stg.pawgrammers.io.vn"
echo ""
echo "  PM2 status: pm2 list"
echo "  Backend logs: pm2 logs adspilot-api"
echo "  Nginx logs: tail -f /var/log/nginx/error.log"
echo "======================================================================"
