#!/usr/bin/env bash
set -euo pipefail

# Repo root = parent of scripts/
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
cd "$ROOT_DIR"

log()  { printf "\033[0;34m[sitectl]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*" >&2; }
err()  { printf "\033[0;31m[err]\033[0m %s\n" "$*" >&2; }

need_cmd() { command -v "$1" >/dev/null 2>&1 || { err "Missing command: $1"; exit 1; }; }

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  else
    need_cmd docker-compose
    docker-compose "$@"
  fi
}

load_env_required() {
  [[ -f "$ENV_FILE" ]] || { err "Missing .env at $ENV_FILE"; exit 1; }
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a

  : "${DOMAIN:?DOMAIN not set in .env}"
  : "${CERTBOT_EMAIL:?CERTBOT_EMAIL not set in .env}"
  : "${SECRET_KEY:?SECRET_KEY not set in .env}"
  : "${ANALYTICS_SALT:?ANALYTICS_SALT not set in .env}"
  : "${MYSQL_PASSWORD:?MYSQL_PASSWORD not set in .env}"
  : "${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD not set in .env}"
}

setup_dirs() {
  mkdir -p nginx/webroot/.well-known/acme-challenge nginx/conf.d nginx/templates
  mkdir -p keys data content/articles public static templates migrations instance
  chmod 755 nginx/webroot || true
}

ensure_dhparam() {
  local f="nginx/dhparam.pem"
  if [[ -f "$f" ]]; then
    return 0
  fi

  warn "Missing ${f}. Generating it now (required by nginx.conf ssl_dhparam)."
  need_cmd openssl
  mkdir -p nginx
  # 2048 is a sane default; if you want 4096, change it (and enjoy the CPU fan cosplay).
  openssl dhparam -out "$f" 2048
  log "Generated ${f}"
}

cert_exists() {
  # Direct file check instead of running certbot container
  # Faster and doesn't require container startup

  # Check if volume is mounted locally via Docker volume inspect
  if docker volume inspect supasuge_certbot_etc >/dev/null 2>&1; then
    local mount_point
    mount_point=$(docker volume inspect supasuge_certbot_etc \
      --format '{{ .Mountpoint }}' 2>/dev/null)

    if [[ -n "$mount_point" && -f "${mount_point}/live/${DOMAIN}/fullchain.pem" ]]; then
      return 0
    fi
  fi

  # Fallback to container check if volume inspection fails
  compose run --rm --entrypoint="" certbot \
    test -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" >/dev/null 2>&1
}

nginx_gen() {
  need_cmd envsubst
  setup_dirs

  local out="nginx/conf.d/site.conf"
  local local_t="nginx/templates/site.local.conf.template"
  local http_t="nginx/templates/site.http.conf.template"
  local https_t="nginx/templates/site.https.conf.template"

  # Check for local development mode
  if [[ "${LOCAL_DEV:-0}" == "1" ]]; then
    [[ -f "$local_t" ]] || { err "Missing template: $local_t"; exit 1; }
    # Local template has hardcoded domain - no substitution needed
    cp "$local_t" "$out"
    log "Generated LOCAL DEV nginx config -> $out (supasuge.com hardcoded)"
    return 0
  fi

  # Production mode: Load environment and check for SSL certificate
  load_env_required

  if cert_exists; then
    [[ -f "$https_t" ]] || { err "Missing template: $https_t"; exit 1; }
    DOMAIN="$DOMAIN" envsubst '${DOMAIN}' < "$https_t" > "$out"
    log "Generated HTTPS nginx config -> $out"
  else
    [[ -f "$http_t" ]] || { err "Missing template: $http_t"; exit 1; }
    DOMAIN="$DOMAIN" envsubst '${DOMAIN}' < "$http_t" > "$out"
    log "Generated HTTP nginx config -> $out"
  fi
}

show_failure_logs() {
  warn "---- docker compose ps ----"
  compose ps || true

  warn "---- web logs (tail) ----"
  compose logs --tail=200 web || true

  warn "---- db logs (tail) ----"
  compose logs --tail=200 db || true

  warn "---- nginx logs (tail) ----"
  compose logs --tail=200 nginx || true
}

init_cert() {
  load_env_required
  setup_dirs

  need_cmd envsubst
  local out="nginx/conf.d/site.conf"
  local http_t="nginx/templates/site.http.conf.template"
  [[ -f "$http_t" ]] || { err "Missing template: $http_t"; exit 1; }

  DOMAIN="$DOMAIN" envsubst '${DOMAIN}' < "$http_t" > "$out"

  log "Starting nginx for ACME HTTP-01 challenge..."
  compose up -d nginx

  log "Requesting cert via webroot for ${DOMAIN} + www.${DOMAIN}..."
  compose run --rm certbot certonly \
    --webroot --webroot-path /var/www/certbot \
    --non-interactive --agree-tos --no-eff-email \
    --email "${CERTBOT_EMAIL}" \
    -d "${DOMAIN}" -d "www.${DOMAIN}"

  log "Cert obtained. Switching nginx to HTTPS config..."
  nginx_gen
  compose exec -T nginx nginx -s reload || compose restart nginx
}

renew_cert() {
  load_env_required
  log "Renewing certs..."
  compose run --rm certbot renew
  log "Reloading nginx..."
  compose exec -T nginx nginx -s reload || compose restart nginx
}

build_sitemap() {
  log "Building sitemap.xml inside web container..."
  if ! compose exec -T web python scripts/build_sitemap.py; then
    warn "Sitemap build failed (non-fatal). Check web logs."
    return 1
  fi
  return 0
}

health() {
  log "Checking container status..."
  compose ps || { show_failure_logs; return 1; }

  log "Checking nginx config..."
  compose exec -T nginx nginx -t || { show_failure_logs; return 1; }

  log "Checking app health endpoint through nginx (upstream)..."
  if ! compose exec -T nginx sh -lc 'wget -qO- http://app/health | head -c 200; echo'; then
    show_failure_logs
    return 1
  fi
}

compose_up() {
  need_cmd docker

  # Skip env validation in LOCAL_DEV mode
  if [[ "${LOCAL_DEV:-0}" != "1" ]]; then
    load_env_required
  fi

  setup_dirs
  ensure_dhparam

  nginx_gen

  log "Building images..."
  compose build

  log "Starting db + redis..."
  compose up -d db redis

  log "Starting web..."
  compose up -d web

  log "Starting nginx..."
  compose up -d nginx

  # Skip certificate logic in LOCAL_DEV
  if [[ "${LOCAL_DEV:-0}" == "1" ]]; then
    log "LOCAL_DEV mode - skipping certificate checks"
  elif ! cert_exists; then
    warn "No cert found yet. Attempting automatic issuance..."
    init_cert
  else
    log "Cert already exists. Ensuring HTTPS config is active..."
    nginx_gen
    compose exec -T nginx nginx -s reload || compose restart nginx
  fi

  log "Running health checks..."
  health || { err "Health checks failed."; exit 1; }

  # Build sitemap once the app is up
  build_sitemap || true

  if [[ "${LOCAL_DEV:-0}" == "1" ]]; then
    log "Done. Site should be up at: http://localhost"
  else
    log "Done. Site should be up at: https://${DOMAIN}"
  fi
}

compose_down() { log "Stopping stack..."; compose down; }

logs() {
  local svc="${1:-}"
  if [[ -n "$svc" ]]; then compose logs -f "$svc"; else compose logs -f; fi
}

usage() {
  cat <<EOF
Usage: $0 <command>

Core:
  up                 Build + start stack + auto-issue cert if missing + health checks
  down               Stop stack
  logs [service]     Follow logs
  nginx-gen          Regenerate nginx/conf.d/site.conf (auto http/https)
  init-cert          Obtain initial Let's Encrypt cert (HTTP-01 webroot)
  renew-cert         Renew certs + reload nginx
  health             Basic health checks
EOF
}

main() {
  local cmd="${1:-}"; shift || true
  case "$cmd" in
    up) compose_up ;;
    down) compose_down ;;
    logs) logs "${1:-}" ;;
    nginx-gen) nginx_gen ;;
    init-cert) init_cert ;;
    renew-cert) renew_cert ;;
    health) health ;;
    ""|-h|--help) usage ;;
    *) err "Unknown command: $cmd"; usage; exit 1 ;;
  esac
}

main "$@"
