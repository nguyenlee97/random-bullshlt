#!/bin/bash
# VPS Setup Script for Replicated Sites

echo "1. Installing required packages..."
apt-get update
apt-get install -y nginx unzip

echo "2. Extracting website files..."
if [ ! -f "deploy.zip" ]; then
    echo "Error: deploy.zip not found in the current directory!"
    exit 1
fi

unzip -o deploy.zip -d /var/www/

echo "3. Setting up Nginx configurations..."

# Baomoi Replicate
cat << 'EOF' > /etc/nginx/sites-available/baomoi-stg.pawgrammers.io.vn
server {
    listen 80;
    server_name baomoi-stg.pawgrammers.io.vn;
    root /var/www/baomoi_replicate;
    index index.html index.htm;

    location / {
        try_files $uri $uri/ =404;
    }
}
EOF

# ZingMP3 Replicate
cat << 'EOF' > /etc/nginx/sites-available/zingmp3-stg.pawgrammers.io.vn
server {
    listen 80;
    server_name zingmp3-stg.pawgrammers.io.vn;
    root /var/www/zingmp3_replicate;
    index index.html index.htm;

    location / {
        try_files $uri $uri/ =404;
    }
}
EOF

# Znews Replicate
cat << 'EOF' > /etc/nginx/sites-available/znews-stg.pawgrammers.io.vn
server {
    listen 80;
    server_name znews-stg.pawgrammers.io.vn;
    root /var/www/znews_replicate;
    index index.html index.htm;

    location / {
        try_files $uri $uri/ =404;
    }
}
EOF

echo "4. Enabling sites..."
ln -sf /etc/nginx/sites-available/baomoi-stg.pawgrammers.io.vn /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/zingmp3-stg.pawgrammers.io.vn /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/znews-stg.pawgrammers.io.vn /etc/nginx/sites-enabled/

# Remove default nginx site if it exists to avoid conflicts
rm -f /etc/nginx/sites-enabled/default

echo "5. Testing Nginx config and restarting..."
nginx -t && systemctl restart nginx

echo "============================================="
echo "Deployment Complete! Your sites are live at:"
echo "http://baomoi-stg.pawgrammers.io.vn"
echo "http://zingmp3-stg.pawgrammers.io.vn"
echo "http://znews-stg.pawgrammers.io.vn"
echo "============================================="
