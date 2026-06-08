#!/bin/bash
# n8n VPS Automated Setup Script

echo "========================================="
echo "        n8n Automated Setup Script       "
echo "========================================="

N8N_DOMAIN="n8n.pawgrammers.io.vn"
SSL_EMAIL="weggb.misaya@gmail.com"
DB_PASS="le_nguyen123"

echo ""
echo "Configuration summary:"
echo "Domain: $N8N_DOMAIN"
echo "Email: $SSL_EMAIL"
echo "Password: [HIDDEN]"
echo ""
echo "WARNING: Please ensure you have created a DNS A Record for $N8N_DOMAIN pointing to this VPS IP before proceeding."
read -p "Press Enter to begin the installation..."

echo "1. Updating system and installing dependencies..."
apt update && apt upgrade -y
apt install -y curl nano

echo "2. Installing Docker and Docker Compose..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    apt install docker-compose-v2 -y
    usermod -aG docker $USER
else
    echo "Docker is already installed."
fi

echo "3. Setting up n8n configuration..."
mkdir -p ~/n8n
cd ~/n8n

cat << EOF > docker-compose.yml
version: '3.7'

services:
  n8n:
    image: n8nio/n8n
    restart: always
    ports:
      - "127.0.0.1:5678:5678"
    environment:
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_PORT=5432
      - DB_POSTGRESDB_DATABASE=\${POSTGRES_DB}
      - DB_POSTGRESDB_USER=\${POSTGRES_USER}
      - DB_POSTGRESDB_PASSWORD=\${POSTGRES_PASSWORD}
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on:
      - postgres

  postgres:
    image: postgres:15
    restart: always
    environment:
      - POSTGRES_DB=\${POSTGRES_DB}
      - POSTGRES_USER=\${POSTGRES_USER}
      - POSTGRES_PASSWORD=\${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  n8n_data:
  postgres_data:
EOF

cat << EOF > .env
POSTGRES_DB=n8n
POSTGRES_USER=n8nuser
POSTGRES_PASSWORD=$DB_PASS
EOF

echo "4. Starting n8n containers..."
docker compose up -d

echo "5. Installing and configuring NGINX..."
apt install nginx -y

cat << EOF > /etc/nginx/sites-available/n8n
server {
    listen 80;
    server_name $N8N_DOMAIN;

    location / {
        proxy_pass http://localhost:5678;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Host \$host;
    }
}
EOF

ln -sf /etc/nginx/sites-available/n8n /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

echo "6. Installing Certbot and securing with SSL..."
apt install certbot python3-certbot-nginx -y

# Run certbot non-interactively
certbot --nginx -d $N8N_DOMAIN --non-interactive --agree-tos -m $SSL_EMAIL --redirect

echo "========================================="
echo "Installation Complete!"
echo "Your n8n instance should now be securely available at:"
echo "https://$N8N_DOMAIN"
echo "========================================="
