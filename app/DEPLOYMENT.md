# Production Deployment Guide

This guide provides comprehensive instructions for deploying supasuge.com to production.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Environment Configuration](#environment-configuration)
- [Deployment](#deployment)
- [Post-Deployment Verification](#post-deployment-verification)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)
- [Security Considerations](#security-considerations)

## Prerequisites

### Server Requirements

- **OS**: Ubuntu 20.04+ or Debian 11+ (recommended)
- **RAM**: Minimum 2GB, recommended 4GB
- **Storage**: Minimum 20GB
- **Network**: Public IP with ports 80 and 443 accessible

### Required Software

1. **Docker** (v20.10+)
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   ```

2. **Docker Compose** (v2.0+)
   ```bash
   # Usually included with Docker
   docker compose version
   ```

3. **Git**
   ```bash
   sudo apt update
   sudo apt install -y git
   ```

### DNS Configuration

Point your domain to the server:
```
A     @              -> YOUR_SERVER_IP
A     www            -> YOUR_SERVER_IP
```

Wait for DNS propagation (can take up to 48 hours, usually much faster).

Verify DNS:
```bash
dig +short supasuge.com
dig +short www.supasuge.com
```

## Initial Setup

### 1. Clone the Repository

```bash
cd /home/$USER
git clone https://github.com/yourusername/supasuge.com.git
cd supasuge.com
```

### 2. Configure Environment

#### Option A: Interactive Setup (Recommended)

```bash
./scripts/setup_env.sh
```

Follow the prompts to configure your domain, email, and site name. The script will:
- Generate cryptographically secure secrets
- Validate your inputs
- Create a production-ready `.env` file

#### Option B: Non-Interactive Setup

```bash
./scripts/setup_env.sh supasuge.com admin@supasuge.com "My Site Name"
```

#### Option C: Manual Setup

```bash
cp .env.example .env
nano .env
```

**Required Variables to Update:**

| Variable | Description | Example |
|----------|-------------|---------|
| `DOMAIN` | Your domain name (no protocol) | `supasuge.com` |
| `CERTBOT_EMAIL` | Email for Let's Encrypt notifications | `admin@supasuge.com` |
| `SECRET_KEY` | Flask secret (64 hex chars) | Generate with `python3 -c 'import secrets; print(secrets.token_hex(32))'` |
| `ANALYTICS_SALT` | Analytics hashing salt (48 hex chars) | Generate with `python3 -c 'import secrets; print(secrets.token_hex(24))'` |
| `MYSQL_PASSWORD` | Database user password | Generate with `python3 -c 'import secrets; print(secrets.token_urlsafe(24))'` |
| `MYSQL_ROOT_PASSWORD` | Database root password | Generate with `python3 -c 'import secrets; print(secrets.token_urlsafe(24))'` |
| `SITE_NAME` | Display name for your site | `Evan Pardon's Portfolio` |

**Important**: Never commit `.env` to version control!

### 3. Verify Configuration

```bash
# Check that all required variables are set
grep -E "^(DOMAIN|SECRET_KEY|MYSQL_PASSWORD|CERTBOT_EMAIL)=" .env

# Ensure no placeholder values remain
if grep -iE "(REPLACE|changeme|your-)" .env; then
    echo "ERROR: Found placeholder values in .env"
else
    echo "OK: No placeholder values found"
fi
```

## Deployment

### First-Time Deployment

```bash
./deploy.sh deploy
```

This script will:
1. ✅ Validate environment configuration
2. ✅ Generate secure secrets (if not already set)
3. ✅ Build Docker images
4. ✅ Start MySQL database
5. ✅ Start Redis cache
6. ✅ Start web application
7. ✅ Run database migrations
8. ✅ Sync content from filesystem
9. ✅ Build sitemap
10. ✅ Start Nginx reverse proxy
11. ✅ Obtain SSL certificates from Let's Encrypt
12. ✅ Verify all services are healthy

**Deployment typically takes 3-5 minutes.**

### Subsequent Updates

```bash
./deploy.sh update
```

This will:
1. ✅ Backup database
2. ✅ Rebuild Docker images with latest code
3. ✅ Restart services with zero downtime
4. ✅ Run new database migrations
5. ✅ Sync content and rebuild sitemap
6. ✅ Verify deployment health

## Post-Deployment Verification

### 1. Check Service Status

```bash
docker compose ps
```

All services should show `Up` and `healthy`.

### 2. Verify Web Application

```bash
# Internal health check
docker compose exec -T web python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()"

# External health check
curl -I https://supasuge.com
curl -sS https://supasuge.com/health
```

Expected response:
```json
{"status": "healthy", "database": "connected", "redis": "connected"}
```

### 3. Check Database Migrations

```bash
docker compose exec -T web alembic current
docker compose exec -T web alembic history
```

### 4. View Logs

```bash
# All services
./deploy.sh logs

# Specific service
./deploy.sh logs web
./deploy.sh logs nginx
./deploy.sh logs db
```

### 5. Test SSL Certificate

```bash
curl -vI https://supasuge.com 2>&1 | grep -E "(subject|issuer|expire)"
```

Or use: https://www.ssllabs.com/ssltest/

## Troubleshooting

### Database Migration Failures

If you see `[ERROR] Database migrations failed!`, check the logs:

```bash
# View migration errors
docker compose logs --tail=200 web

# Check database connectivity
docker compose exec -T web python -c "
import os
from sqlalchemy import create_engine, text
url = os.environ['DATABASE_URL']
engine = create_engine(url, pool_pre_ping=True)
with engine.connect() as c:
    c.execute(text('SELECT 1'))
print('DB connectivity OK')
"

# Verify PyMySQL is installed
docker compose exec -T web python -c "import pymysql; print('pymysql', pymysql.__version__)"

# Check Alembic configuration
docker compose exec -T web alembic current
```

**Common Causes:**

1. **Missing PyMySQL**: Already included in `requirements.txt:90`
2. **Database not ready**: Wait for DB to be healthy (`docker compose ps db`)
3. **Wrong credentials**: Verify `MYSQL_PASSWORD` in `.env`
4. **Import path issues**: Check `migrations/env.py` imports

**Manual Migration:**

```bash
# Run migrations manually with verbose output
docker compose exec -T web alembic upgrade head --verbose

# If that fails, show the actual error
docker compose exec web /bin/bash
alembic upgrade head
```

### SSL Certificate Issues

If Let's Encrypt fails:

```bash
# Check DNS is pointing to your server
dig +short supasuge.com

# Verify ports 80 and 443 are accessible
sudo netstat -tlnp | grep -E ':(80|443)'

# Check firewall
sudo ufw status

# Manually obtain certificate
docker compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email your@email.com \
  --agree-tos \
  --no-eff-email \
  -d supasuge.com \
  -d www.supasuge.com

# Reload Nginx
docker compose exec nginx nginx -s reload
```

### Service Won't Start

```bash
# Check specific service logs
docker compose logs --tail=100 web
docker compose logs --tail=100 db
docker compose logs --tail=100 nginx

# Restart individual service
./deploy.sh restart web

# Nuclear option: full restart
docker compose down
docker compose up -d
```

### Permission Errors

If you see permission errors for `content` or `public` directories:

```bash
# The docker-compose.yml has been updated to mount these as read-write
# If issues persist, check directory ownership
ls -la content/ public/

# Fix ownership (if needed)
sudo chown -R $USER:$USER content/ public/
```

## Maintenance

### Daily Operations

```bash
# View status
./deploy.sh status

# View logs
./deploy.sh logs [service]

# Restart service
./deploy.sh restart [service]

# Shell into container
./deploy.sh shell web
```

### Backups

```bash
# Manual backup
./deploy.sh backup

# Backups are stored in backups/mysql_backup_TIMESTAMP.sql.gz
# Last 5 backups are kept automatically
```

### SSL Certificate Renewal

Certificates auto-renew via cron. Manual renewal:

```bash
./scripts/sitectl.sh renew-cert
```

### Content Management

```bash
# Sync new articles from content/articles/*.md
docker compose exec -T web python scripts/sync.py

# Rebuild sitemap
docker compose exec -T web python scripts/build_sitemap.py
```

### Monitoring

```bash
# Resource usage
docker stats --no-stream $(docker compose ps -q)

# Disk usage
docker system df

# Clean old images
docker image prune -a
```

## Security Considerations

### Secrets Management

- ✅ `.env` file contains sensitive secrets
- ✅ Never commit `.env` to Git (already in `.gitignore`)
- ✅ Use strong, randomly generated secrets (setup script does this)
- ✅ Rotate secrets periodically (see `docs/SECRETS_ROTATION.md`)

### Container Security

- ✅ Web container runs in read-only mode with minimal capabilities
- ✅ No new privileges allowed
- ✅ Temporary files use tmpfs
- ✅ All capabilities dropped except required ones

### Network Security

- ✅ Services communicate via internal Docker network
- ✅ Only Nginx exposes ports 80 and 443
- ✅ Database and Redis are not publicly accessible

### Admin Authentication

Uses OpenSSH signature-based authentication (no passwords):

```bash
# Generate admin SSH keypair
ssh-keygen -t ed25519 -f keys/admin_ssh -C "admin@supasuge.com"

# Copy public key
cp keys/admin_ssh.pub keys/admin_ssh.pub

# Configure in .env
ADMIN_SSH_PUBLIC_KEY_PATH=keys/admin_ssh.pub
ADMIN_ENABLED=1
```

### Firewall Configuration

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Security Headers

Nginx configuration includes:
- HSTS (HTTP Strict Transport Security)
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin

## Useful Commands Reference

```bash
# Deployment
./deploy.sh deploy              # Initial deployment
./deploy.sh update              # Update deployment

# Management
./deploy.sh status              # Service status
./deploy.sh logs [service]      # View logs
./deploy.sh backup              # Backup database
./deploy.sh restart [service]   # Restart service
./deploy.sh shell [service]     # Shell into container

# Docker Compose
docker compose ps               # List containers
docker compose logs -f web      # Follow logs
docker compose restart web      # Restart service
docker compose down             # Stop all services
docker compose up -d            # Start all services

# Database
docker compose exec -T web alembic current          # Current migration
docker compose exec -T web alembic upgrade head     # Run migrations
docker compose exec db mysql -u root -p blog        # MySQL shell

# Debugging
docker compose exec web /bin/bash                   # Shell into web
docker compose exec web python                      # Python REPL
docker compose logs --tail=200 web                  # Recent logs
```

## Getting Help

- **Logs**: Always check logs first with `./deploy.sh logs [service]`
- **Health**: Verify with `./deploy.sh status` and `curl /health`
- **GitHub Issues**: Report bugs at https://github.com/yourusername/supasuge.com/issues
- **Documentation**: See `CLAUDE.md` for development workflow
- **Security**: For security issues, email security@supasuge.com

## Production Checklist

Before going live:

- [ ] DNS configured and propagated
- [ ] `.env` file configured with production values
- [ ] All secrets are strong and unique
- [ ] SSL certificates obtained successfully
- [ ] All services show `healthy` status
- [ ] Health endpoint returns 200 OK
- [ ] Database migrations completed
- [ ] Content synced and sitemap built
- [ ] Firewall configured
- [ ] Backups tested and working
- [ ] Monitoring set up (optional but recommended)
- [ ] Admin SSH keys configured (if using admin panel)

---

**Last Updated**: 2025-12-28
**Maintained By**: supasuge.com team
