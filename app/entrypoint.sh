#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[entrypoint]${NC} $1"; }
log_success() { echo -e "${GREEN}[entrypoint]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[entrypoint]${NC} $1"; }
log_error() { echo -e "${RED}[entrypoint]${NC} $1"; }

cd /app

if [[ ! -f /app/alembic.ini ]]; then
  log_error "alembic.ini not found at /app/alembic.ini"
  log_info "Contents of /app:"
  ls -la /app/ | head -50
  exit 1
fi

if [[ ! -f /app/app.py ]]; then
  log_error "app.py not found at /app/app.py"
  exit 1
fi

wait_for_db() {
  # SQLite is file-based and doesn't require a connection wait
  log_info "Using SQLite database - no connection wait needed"
  return 0
}

run_migrations() {
  if [[ "${RUN_MIGRATIONS:-1}" != "1" ]]; then
    log_info "Skipping migrations (RUN_MIGRATIONS=0)"
    return 0
  fi

  log_info "Running Alembic migrations..."
  set +e
  out="$(alembic -c /app/alembic.ini upgrade head 2>&1)"
  rc=$?
  set -e

  if [[ $rc -ne 0 ]]; then
    log_error "Migration failed! Alembic output:"
    echo "$out"
    exit 1
  fi

  log_success "Migrations completed successfully"
}

run_content_sync() {
  if [[ "${RUN_CONTENT_SYNC:-0}" != "1" ]]; then
    log_info "Skipping content sync (RUN_CONTENT_SYNC=0)"
    return 0
  fi

  log_info "Running one-shot content sync..."
  set +e
  python3 - <<'PYTHON'
import sys
sys.path.insert(0, '/app')

from app import create_app
from config import Config
from content_sync import sync_content
from models import db

app = create_app()
cfg = Config()

with app.app_context():
    result = sync_content(cfg.CONTENT_DIR, db.session)
    print(f"Content sync result: {result}")
PYTHON
  rc=$?
  set -e

  if [[ $rc -ne 0 ]]; then
    log_warn "Content sync failed (non-fatal, continuing...)"
  else
    log_success "Content sync completed"
  fi
}

start_gunicorn() {
  log_info "Starting Gunicorn WSGI server..."

  local workers="${GUNICORN_WORKERS:-2}"
  local threads="${GUNICORN_THREADS:-4}"
  local bind="${BIND:-0.0.0.0:8000}"
  local log_level="${LOG_LEVEL:-info}"

  log_info "Configuration:"
  log_info "  Workers: $workers"
  log_info "  Threads: $threads"
  log_info "  Bind: $bind"
  log_info "  Log Level: $log_level"

  exec gunicorn \
    --config /app/gunicorn.conf.py \
    --bind "$bind" \
    --workers "$workers" \
    --threads "$threads" \
    --log-level "$log_level" \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    "wsgi:app"
}

main() {
  log_info "========================================="
  log_info "Starting supasuge.com Flask Application"
  log_info "========================================="

  if ! wait_for_db; then
    log_error "Cannot proceed without database connection"
    exit 1
  fi

  run_migrations
  run_content_sync
  start_gunicorn
}

main "$@"
