#!/usr/bin/env bash
#
# obtain-certs.sh - Obtain SSL/TLS certificates from Let's Encrypt
#
# This script automates the process of obtaining SSL/TLS certificates
# for your domain using Certbot and Let's Encrypt via HTTP-01 challenge.
#
# Prerequisites:
# - Docker and Docker Compose installed
# - DOMAIN and CERTBOT_EMAIL set in .env file
# - DNS A/AAAA records pointing to your server
# - Ports 80 and 443 open in firewall
#
# Usage:
#   ./scripts/obtain-certs.sh           # Obtain certificates
#   ./scripts/obtain-certs.sh --staging # Test with staging server (recommended first)
#   ./scripts/obtain-certs.sh --force   # Force renewal
#

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load environment variables
if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
    log_error ".env file not found at $PROJECT_ROOT/.env"
    log_info "Copy .env.example to .env and configure it first:"
    log_info "  cp .env.example .env"
    log_info "  # Edit .env with your DOMAIN and CERTBOT_EMAIL"
    exit 1
fi

# Source .env file
set -a
source "$PROJECT_ROOT/.env"
set +a

# Check required environment variables
if [[ -z "${DOMAIN:-}" ]]; then
    log_error "DOMAIN not set in .env file"
    exit 1
fi

if [[ -z "${CERTBOT_EMAIL:-}" ]]; then
    log_error "CERTBOT_EMAIL not set in .env file"
    log_info "Set CERTBOT_EMAIL in .env to your email address for Let's Encrypt notifications"
    exit 1
fi

# Parse command line arguments
STAGING_FLAG=""
FORCE_RENEWAL=""

for arg in "$@"; do
    case $arg in
        --staging)
            STAGING_FLAG="--staging"
            log_warn "Using Let's Encrypt STAGING server (certificates won't be trusted)"
            ;;
        --force)
            FORCE_RENEWAL="--force-renewal"
            log_info "Force renewal enabled"
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --staging    Use Let's Encrypt staging server (for testing)"
            echo "  --force      Force certificate renewal"
            echo "  --help       Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $arg"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

cd "$PROJECT_ROOT"

# Ensure required directories exist
log_info "Creating required directories..."
mkdir -p nginx/webroot

# Ensure dhparam.pem exists (required for nginx SSL)
if [[ ! -f nginx/dhparam.pem ]]; then
    log_warn "nginx/dhparam.pem not found, generating (this may take several minutes)..."
    openssl dhparam -out nginx/dhparam.pem 2048
    log_success "Generated nginx/dhparam.pem"
fi

# Check if nginx is already running
if docker compose ps nginx | grep -q "Up"; then
    log_info "Nginx is running, will reload after obtaining certificates"
    NGINX_RUNNING=true
else
    log_info "Starting nginx for ACME challenge..."
    docker compose up -d nginx
    NGINX_RUNNING=false
    # Wait for nginx to be ready
    sleep 3
fi

# Run certbot to obtain certificates
log_info "Obtaining SSL certificates for: $DOMAIN and www.$DOMAIN"
log_info "Certificate email: $CERTBOT_EMAIL"

set +e
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$CERTBOT_EMAIL" \
    --agree-tos \
    --no-eff-email \
    $STAGING_FLAG \
    $FORCE_RENEWAL \
    -d "$DOMAIN" \
    -d "www.$DOMAIN"

CERTBOT_EXIT_CODE=$?
set -e

if [[ $CERTBOT_EXIT_CODE -eq 0 ]]; then
    log_success "Certificates obtained successfully!"

    # Reload nginx to use new certificates
    if [[ "$NGINX_RUNNING" == "true" ]]; then
        log_info "Reloading nginx configuration..."
        docker compose exec nginx nginx -s reload
        log_success "Nginx reloaded"
    else
        log_info "Restarting nginx to use new certificates..."
        docker compose restart nginx
        log_success "Nginx restarted"
    fi

    log_success "SSL/TLS setup complete!"
    log_info "Certificates stored in Docker volume: supasuge_certbot_etc"
    log_info "Certificates are valid for 90 days"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Test your site: https://$DOMAIN"
    log_info "  2. Set up automatic renewal with: scripts/renew-certs.sh"
    log_info "  3. Add renewal to cron: 0 0 * * * /path/to/scripts/renew-certs.sh"
else
    log_error "Failed to obtain certificates (exit code: $CERTBOT_EXIT_CODE)"
    log_info ""
    log_info "Troubleshooting:"
    log_info "  1. Ensure DNS records point to this server:"
    log_info "     dig $DOMAIN"
    log_info "     dig www.$DOMAIN"
    log_info "  2. Ensure ports 80 and 443 are open:"
    log_info "     sudo ufw status (if using ufw)"
    log_info "     sudo iptables -L -n (if using iptables)"
    log_info "  3. Check nginx logs:"
    log_info "     docker compose logs nginx"
    log_info "  4. Try staging first to test:"
    log_info "     $0 --staging"
    exit 1
fi
