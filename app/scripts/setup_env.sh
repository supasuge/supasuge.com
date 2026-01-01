#!/usr/bin/env bash
# =============================================================================
# Environment Setup Script for supasuge.com
# =============================================================================
# This script helps configure the .env file for production deployment.
# It generates secure secrets and validates configuration.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${PROJECT_ROOT}/.env"
ENV_EXAMPLE="${PROJECT_ROOT}/.env.example"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# Generate secure secret
generate_secret() {
    local length=${1:-32}
    python3 -c "import secrets; print(secrets.token_hex($length))"
}

generate_password() {
    local length=${1:-24}
    python3 -c "import secrets; print(secrets.token_urlsafe($length))"
}

# Validate email format
validate_email() {
    local email=$1
    if [[ "$email" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        return 0
    fi
    return 1
}

# Validate domain format
validate_domain() {
    local domain=$1
    if [[ "$domain" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$ ]]; then
        return 0
    fi
    return 1
}

# Interactive setup
interactive_setup() {
    log_info "========================================="
    log_info "supasuge.com Environment Setup"
    log_info "========================================="
    echo ""

    # Check if .env already exists
    if [[ -f "$ENV_FILE" ]]; then
        log_warn ".env file already exists!"
        read -p "Do you want to overwrite it? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Setup cancelled."
            exit 0
        fi
    fi

    # Start with .env.example as template
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    log_success "Created .env from template"
    echo ""

    # Collect required information
    log_step "Domain Configuration"
    while true; do
        read -p "Enter your domain name (e.g., supasuge.com): " domain
        if validate_domain "$domain"; then
            break
        else
            log_error "Invalid domain format. Please try again."
        fi
    done

    log_step "Email Configuration"
    while true; do
        read -p "Enter your email for Let's Encrypt notifications: " email
        if validate_email "$email"; then
            break
        else
            log_error "Invalid email format. Please try again."
        fi
    done

    log_step "Site Configuration"
    read -p "Enter your site name [Evan Pardon's Portfolio]: " site_name
    site_name=${site_name:-"Evan Pardon's Portfolio"}

    read -p "Enter admin email [admin@${domain}]: " admin_email
    admin_email=${admin_email:-"admin@${domain}"}

    # Generate secrets
    log_step "Generating secure secrets..."
    SECRET_KEY=$(generate_secret 32)
    ANALYTICS_SALT=$(generate_secret 24)
    MYSQL_PASSWORD=$(generate_password 24)
    MYSQL_ROOT_PASSWORD=$(generate_password 24)

    log_success "Generated all secrets securely"
    echo ""

    # Update .env file
    log_step "Writing configuration to .env..."

    # Use sed to replace values (cross-platform compatible)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s|^DOMAIN=.*|DOMAIN=${domain}|" "$ENV_FILE"
        sed -i '' "s|^SITE_NAME=.*|SITE_NAME=${site_name}|" "$ENV_FILE"
        sed -i '' "s|^SITE_URL=.*|SITE_URL=https://${domain}|" "$ENV_FILE"
        sed -i '' "s|^CERTBOT_EMAIL=.*|CERTBOT_EMAIL=${email}|" "$ENV_FILE"
        sed -i '' "s|^ADMIN_EMAIL=.*|ADMIN_EMAIL=${admin_email}|" "$ENV_FILE"
        sed -i '' "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" "$ENV_FILE"
        sed -i '' "s|^ANALYTICS_SALT=.*|ANALYTICS_SALT=${ANALYTICS_SALT}|" "$ENV_FILE"
        sed -i '' "s|^MYSQL_PASSWORD=.*|MYSQL_PASSWORD=${MYSQL_PASSWORD}|" "$ENV_FILE"
        sed -i '' "s|^MYSQL_ROOT_PASSWORD=.*|MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}|" "$ENV_FILE"
    else
        # Linux
        sed -i "s|^DOMAIN=.*|DOMAIN=${domain}|" "$ENV_FILE"
        sed -i "s|^SITE_NAME=.*|SITE_NAME=${site_name}|" "$ENV_FILE"
        sed -i "s|^SITE_URL=.*|SITE_URL=https://${domain}|" "$ENV_FILE"
        sed -i "s|^CERTBOT_EMAIL=.*|CERTBOT_EMAIL=${email}|" "$ENV_FILE"
        sed -i "s|^ADMIN_EMAIL=.*|ADMIN_EMAIL=${admin_email}|" "$ENV_FILE"
        sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" "$ENV_FILE"
        sed -i "s|^ANALYTICS_SALT=.*|ANALYTICS_SALT=${ANALYTICS_SALT}|" "$ENV_FILE"
        sed -i "s|^MYSQL_PASSWORD=.*|MYSQL_PASSWORD=${MYSQL_PASSWORD}|" "$ENV_FILE"
        sed -i "s|^MYSQL_ROOT_PASSWORD=.*|MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}|" "$ENV_FILE"
    fi

    log_success ".env file configured successfully!"
    echo ""

    # Display summary
    log_info "========================================="
    log_info "Configuration Summary"
    log_info "========================================="
    echo -e "${CYAN}Domain:${NC}       ${domain}"
    echo -e "${CYAN}Site Name:${NC}    ${site_name}"
    echo -e "${CYAN}Admin Email:${NC}  ${admin_email}"
    echo -e "${CYAN}Cert Email:${NC}   ${email}"
    echo ""
    log_warn "Your secrets have been generated and saved securely."
    log_warn "NEVER commit the .env file to version control!"
    echo ""

    # Display next steps
    chmod 600 "$ENV_FILE" || true
}

# Non-interactive setup (for automation)
noninteractive_setup() {
    local domain=$1
    local email=$2
    local site_name=${3:-"Evan Pardon's Portfolio"}

    # Validate inputs
    if ! validate_domain "$domain"; then
        log_error "Invalid domain format: $domain"
        exit 1
    fi

    if ! validate_email "$email"; then
        log_error "Invalid email format: $email"
        exit 1
    fi

    # Create .env from template
    cp "$ENV_EXAMPLE" "$ENV_FILE"

    # Generate secrets
    SECRET_KEY=$(generate_secret 32)
    ANALYTICS_SALT=$(generate_secret 24)
    MYSQL_PASSWORD=$(generate_password 24)
    MYSQL_ROOT_PASSWORD=$(generate_password 24)

    # Update .env
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|^DOMAIN=.*|DOMAIN=${domain}|" "$ENV_FILE"
        sed -i '' "s|^SITE_NAME=.*|SITE_NAME=${site_name}|" "$ENV_FILE"
        sed -i '' "s|^SITE_URL=.*|SITE_URL=https://${domain}|" "$ENV_FILE"
        sed -i '' "s|^CERTBOT_EMAIL=.*|CERTBOT_EMAIL=${email}|" "$ENV_FILE"
        sed -i '' "s|^ADMIN_EMAIL=.*|ADMIN_EMAIL=admin@${domain}|" "$ENV_FILE"
        sed -i '' "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" "$ENV_FILE"
        sed -i '' "s|^ANALYTICS_SALT=.*|ANALYTICS_SALT=${ANALYTICS_SALT}|" "$ENV_FILE"
        sed -i '' "s|^MYSQL_PASSWORD=.*|MYSQL_PASSWORD=${MYSQL_PASSWORD}|" "$ENV_FILE"
        sed -i '' "s|^MYSQL_ROOT_PASSWORD=.*|MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}|" "$ENV_FILE"
    else
        sed -i "s|^DOMAIN=.*|DOMAIN=${domain}|" "$ENV_FILE"
        sed -i "s|^SITE_NAME=.*|SITE_NAME=${site_name}|" "$ENV_FILE"
        sed -i "s|^SITE_URL=.*|SITE_URL=https://${domain}|" "$ENV_FILE"
        sed -i "s|^CERTBOT_EMAIL=.*|CERTBOT_EMAIL=${email}|" "$ENV_FILE"
        sed -i "s|^ADMIN_EMAIL=.*|ADMIN_EMAIL=admin@${domain}|" "$ENV_FILE"
        sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" "$ENV_FILE"
        sed -i "s|^ANALYTICS_SALT=.*|ANALYTICS_SALT=${ANALYTICS_SALT}|" "$ENV_FILE"
        sed -i "s|^MYSQL_PASSWORD=.*|MYSQL_PASSWORD=${MYSQL_PASSWORD}|" "$ENV_FILE"
        sed -i "s|^MYSQL_ROOT_PASSWORD=.*|MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}|" "$ENV_FILE"
    fi

    log_success ".env configured for ${domain}"
    chmod 600 "$ENV_FILE" || true
    log_success ".env configured via chmod 600 .env"
}

# Usage information
usage() {
    cat <<EOF
${BLUE}supasuge.com Environment Setup Script${NC}

${CYAN}Usage:${NC}
  $0                                    # Interactive setup
  $0 <domain> <email> [site_name]       # Non-interactive setup

${CYAN}Examples:${NC}
  $0                                    # Interactive mode
  $0 supasuge.com admin@supasuge.com    # Auto-generate with defaults
  $0 example.com you@example.com "My Site"  # Custom site name

${CYAN}Features:${NC}
  - Generates cryptographically secure secrets
  - Validates domain and email formats
  - Creates production-ready .env configuration
  - Provides clear next steps

EOF
}

# Main
main() {
    cd "$PROJECT_ROOT"

    # Check for Python 3
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not found"
        exit 1
    fi

    # Check for .env.example
    if [[ ! -f "$ENV_EXAMPLE" ]]; then
        log_error ".env.example not found at: $ENV_EXAMPLE"
        exit 1
    fi

    case "${1:-}" in
        -h|--help|help)
            usage
            ;;
        "")
            interactive_setup
            ;;
        *)
            if [[ $# -lt 2 ]]; then
                log_error "Non-interactive mode requires domain and email"
                echo ""
                usage
                exit 1
            fi
            noninteractive_setup "$1" "$2" "${3:-}"
            ;;
    esac
}

main "$@"
