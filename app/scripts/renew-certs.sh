#!/usr/bin/env bash
#
# renew-certs.sh - Renew SSL/TLS certificates from Let's Encrypt
#
# This script renews SSL/TLS certificates if they are due for renewal
# (within 30 days of expiration). Safe to run frequently via cron.
#
# Recommended cron schedule (runs daily at midnight):
#   0 0 * * * /path/to/scripts/renew-certs.sh >> /var/log/certbot-renew.log 2>&1
#
# Usage:
#   ./scripts/renew-certs.sh
#   ./scripts/renew-certs.sh --force  # Force renewal even if not due
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

# Parse command line arguments
FORCE_RENEWAL=""

for arg in "$@"; do
    case $arg in
        --force)
            FORCE_RENEWAL="--force-renewal"
            log_info "Force renewal enabled"
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
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

log_info "$(date '+%Y-%m-%d %H:%M:%S') - Checking for certificate renewal..."

# Run certbot renew
set +e
docker compose run --rm certbot renew $FORCE_RENEWAL
CERTBOT_EXIT_CODE=$?
set -e

if [[ $CERTBOT_EXIT_CODE -eq 0 ]]; then
    log_success "Certificate renewal check complete"

    # Reload nginx if certificates were renewed
    log_info "Reloading nginx configuration..."
    docker compose exec nginx nginx -s reload || docker compose restart nginx
    log_success "Nginx reloaded"

    log_success "Certificate renewal process complete"
else
    log_error "Certificate renewal failed (exit code: $CERTBOT_EXIT_CODE)"
    exit 1
fi
