#!/usr/bin/env sh
set -eu

DOMAIN="${DOMAIN:-supasuge.com}"
EMAIL="${CERTBOT_EMAIL:-epardo1742@proton.me}"

docker compose run --rm certbot certonly \
  --webroot --webroot-path /var/www/certbot \
  -d "$DOMAIN" -d "www.$DOMAIN" \
  --email "$EMAIL" \
  --agree-tos --no-eff-email

docker compose exec -T nginx nginx -s reload
