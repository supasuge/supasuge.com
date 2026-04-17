#!/bin/bash
set -euo pipefail

KEY_PATH="${KEY_PATH:-$HOME/.ssh/id_ed25519_blog_vps}"
REMOTE_USER="${REMOTE_USER:-appuser}"
REMOTE_HOST="${REMOTE_HOST:-supasuge.com}"
REMOTE_DEST="${REMOTE_DEST:-~/}"
SRC_DIR="${SRC_DIR:-/home/supasuge/Documents/Projects/supasuge.com}"

if [[ ! -f "$KEY_PATH" ]]; then
  echo "[transfer] Missing key: $KEY_PATH" >&2
  exit 1
fi

if [[ ! -d "$SRC_DIR" ]]; then
  echo "[transfer] Missing source dir: $SRC_DIR" >&2
  exit 1
fi

RAND="$(openssl rand -hex 2)"
FN="supasuge.com-${RAND}.tar.xz"

cd "$(dirname "$SRC_DIR")"

echo "[transfer] Creating archive: $FN"
tar -cJf "$FN" "$(basename "$SRC_DIR")"

# If you're using a passphrase key, ssh-agent is the correct way.
if [[ -n "${SSH_AUTH_SOCK:-}" ]]; then
  echo "[transfer] ssh-agent detected (good)."
else
  echo "[transfer] No SSH_AUTH_SOCK detected."
  echo "[transfer] If your key has a passphrase, run:"
  echo "  eval \"\$(ssh-agent -s)\""
  echo "  ssh-add \"$KEY_PATH\""
fi

echo "[transfer] Uploading..."
scp -P 2222 -i "$KEY_PATH" -o IdentitiesOnly=yes "$FN" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DEST}"

echo "[transfer] Done: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DEST}${FN}"
echo "[transfer] Remote extract example:"
echo "  tar -xJf ${FN}"
