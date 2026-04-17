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

if [[ ! -f /app/app.py ]]; then
  log_error "app.py not found at /app/app.py"
  exit 1
fi

run_migrations() {
  if [[ "${RUN_MIGRATIONS:-0}" != "1" ]]; then
    log_info "Skipping external Alembic step (app bootstrap still reconciles SQLite schema/content)"
    return 0
  fi

  if [[ ! -f /app/alembic.ini ]]; then
    log_warn "alembic.ini not found, skipping migrations"
    return 0
  fi

  log_info "Running Alembic migrations..."
  set +e
  out="$(uv run --no-sync alembic -c /app/alembic.ini upgrade head 2>&1)"
  rc=$?
  set -e

  if [[ $rc -ne 0 ]]; then
    log_error "Migration failed! Alembic output:"
    echo "$out"
    exit 1
  fi

  log_success "Migrations completed successfully"
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

  exec uv run --no-sync gunicorn \
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

  run_migrations
  start_gunicorn
}

main "$@"
