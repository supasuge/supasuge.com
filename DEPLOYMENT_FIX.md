# Production Deployment Fixes

## Issues Identified from errors.log

### 1. ✅ FIXED: Nginx SSL Cipher Configuration Error
**Error:** `SSL_CTX_set_cipher_list(...) failed (SSL: error:0A000118:SSL routines::invalid command)`

**Root Cause:** OpenSSL 3.x (used in nginx:1.27.3-alpine) doesn't support CHACHA20-POLY1305 cipher names in the old format.

**Fix Applied:** Updated `nginx/nginx.conf` line 74 to remove CHACHA20-POLY1305 ciphers and use only AES-GCM ciphers compatible with OpenSSL 3.x.

**File Changed:** `nginx/nginx.conf`

---

### 2. ✅ FIXED: Nginx HTTP/2 Deprecation Warning
**Warning:** `the "listen ... http2" directive is deprecated, use the "http2" directive instead`

**Root Cause:** Modern nginx versions use a separate `http2 on;` directive instead of `listen 443 ssl http2;`

**Fix Applied:** Updated `nginx/conf.d/site.conf` lines 39-41 to use the new HTTP/2 syntax.

**File Changed:** `nginx/conf.d/site.conf`

---

### 3. ⚠️ ACTION REQUIRED: Database Schema Not Initialized
**Error:** `Table 'blog.posts' doesn't exist`

**Root Cause:** Database migrations have not been run. The web service has `RUN_MIGRATIONS: "0"` set in docker-compose.yml (line 85) to prevent automatic migrations on every container restart.

**Solution:** Run migrations manually using the dedicated migrate service.

## Deployment Steps for Production

### Step 1: Stop Running Services (if any)
```bash
docker compose down
```

### Step 2: Pull Latest Configuration Changes
```bash
git pull origin master  # or your branch name
```

### Step 3: Run Database Migrations
This **MUST** be done before starting the web service:

```bash
docker compose --profile ops run --rm migrate
```

**Expected Output:**
```
INFO  [alembic.runtime.migration] Context impl MySQLImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 001, initial_schema
INFO  [alembic.runtime.migration] Running upgrade 001 -> f12bf7d631ed, add_analytics_and_admin_session_models
INFO  [alembic.runtime.migration] Running upgrade f12bf7d631ed -> 9c4a2d9c7b01, fix_pageviews_columns
```

### Step 4: Start All Services
```bash
docker compose up -d
```

### Step 5: Verify Services are Running
```bash
docker compose ps
docker compose logs -f --tail=100
```

**Check for:**
- ✅ No nginx SSL errors
- ✅ No HTTP/2 deprecation warnings
- ✅ Database tables created successfully
- ✅ Content sync completed
- ✅ Gunicorn started

### Step 6: Test Endpoints
```bash
# Test health endpoint
curl http://localhost/health

# Test HTTPS (if SSL certs are configured)
curl https://supasuge.com/health
```

## Alternative: One-Command Deployment

Create this script to automate the deployment:

```bash
#!/usr/bin/env bash
# File: scripts/deploy-production.sh
set -euo pipefail

echo "==> Stopping services..."
docker compose down

echo "==> Running database migrations..."
docker compose --profile ops run --rm migrate

echo "==> Starting services..."
docker compose up -d

echo "==> Waiting for services to be healthy..."
sleep 5
docker compose ps

echo "==> Checking logs for errors..."
docker compose logs --tail=50

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Test with: curl http://localhost/health"
```

Make it executable:
```bash
chmod +x scripts/deploy-production.sh
./scripts/deploy-production.sh
```

## Troubleshooting

### If nginx fails to start:
```bash
# Check nginx configuration syntax
docker compose exec nginx nginx -t

# View nginx logs
docker compose logs nginx
```

### If database migrations fail:
```bash
# Check database connectivity
docker compose exec web python3 -c "from sqlalchemy import create_engine; import os; engine = create_engine(os.environ['DATABASE_URL']); engine.connect()"

# View migration status
docker compose --profile ops run --rm migrate alembic -c /app/alembic.ini current

# View migration history
docker compose --profile ops run --rm migrate alembic -c /app/alembic.ini history
```

### If content sync fails:
This is non-fatal and will be logged as a warning. The application will still start.
Check that content files exist in the `content/articles/` directory.

## Security Notes

After deployment:
1. ✅ Rotate all secrets in `.env` (they were previously committed to git)
2. ✅ Verify HSTS is working: Check response headers include `Strict-Transport-Security`
3. ✅ Test SSL configuration: https://www.ssllabs.com/ssltest/
4. ✅ Verify rate limiting is active
5. ✅ Check that admin endpoints require authentication

## Files Modified

1. `nginx/nginx.conf` - Fixed SSL cipher configuration
2. `nginx/conf.d/site.conf` - Updated HTTP/2 directive
3. `DEPLOYMENT_FIX.md` - This guide (NEW)

## Changes Summary

| File | Issue | Status |
|------|-------|--------|
| `nginx/nginx.conf` | OpenSSL 3.x incompatible ciphers | ✅ FIXED |
| `nginx/conf.d/site.conf` | Deprecated HTTP/2 syntax | ✅ FIXED |
| Database Schema | Missing tables (migrations not run) | ⚠️ ACTION REQUIRED |

---

**Next Steps:** Run the migration command above and restart services.
