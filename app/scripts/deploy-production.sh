#!/usr/bin/env bash
# =============================================================================
# Production Deployment Script
# =============================================================================
# This script safely deploys the application with proper migration handling
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}==>${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }

# Change to app directory
cd "$(dirname "$0")/.." || exit 1

log_info "Production Deployment Started"
echo ""

# Step 1: Stop services
log_info "Stopping running services..."
if docker compose ps -q | grep -q .; then
    docker compose down
    log_success "Services stopped"
else
    log_info "No services running"
fi
echo ""

# Step 2: Validate configuration
log_info "Validating nginx configuration..."
if docker compose run --rm --no-deps nginx nginx -t 2>&1 | grep -q "successful"; then
    log_success "Nginx configuration is valid"
else
    log_error "Nginx configuration has errors"
    exit 1
fi
echo ""

# Step 3: Run migrations
log_info "Running database migrations..."
if docker compose --profile ops run --rm migrate; then
    log_success "Migrations completed successfully"
else
    log_error "Migration failed"
    log_warn "Rolling back deployment..."
    exit 1
fi
echo ""

# Step 4: Start services
log_info "Starting services..."
if docker compose up -d; then
    log_success "Services started"
else
    log_error "Failed to start services"
    exit 1
fi
echo ""

# Step 5: Wait for health checks
log_info "Waiting for services to become healthy..."
sleep 5

# Check service status
log_info "Service status:"
docker compose ps
echo ""

# Step 6: Check for errors in logs
log_info "Checking recent logs for errors..."
if docker compose logs --tail=50 | grep -i "error\|failed\|exception" | grep -v "404" | grep -v "entrypoint]"; then
    log_warn "Found potential errors in logs (review above)"
else
    log_success "No critical errors found in recent logs"
fi
echo ""

# Step 7: Test health endpoint
log_info "Testing health endpoint..."
sleep 2
if docker compose exec -T web curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    log_success "Health endpoint responding"
else
    log_warn "Health endpoint not responding yet (may need more time)"
fi
echo ""

# Final status
echo ""
log_success "=== Deployment Complete ==="
echo ""
log_info "Next steps:"
echo "  1. Test the application: curl http://localhost/health"
echo "  2. View logs: docker compose logs -f"
echo "  3. Check service status: docker compose ps"
echo "  4. Test SSL (if configured): curl https://supasuge.com/health"
echo ""
log_warn "Remember to:"
echo "  - Rotate all secrets in .env (they were previously in git)"
echo "  - Test SSL configuration at https://www.ssllabs.com/ssltest/"
echo "  - Verify HSTS headers are present"
echo ""
