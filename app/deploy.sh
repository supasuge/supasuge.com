#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -x ./scripts/sitectl.sh ]]; then
  echo "[deploy] missing ./scripts/sitectl.sh or not executable"
  exit 1
fi

exec ./scripts/sitectl.sh up
