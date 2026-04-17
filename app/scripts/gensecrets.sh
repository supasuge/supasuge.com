#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
ENV_EXAMPLE="${ROOT_DIR}/.env.example"

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "[gensecrets] missing command: $1" >&2; exit 1; }; }

need_cmd python3
need_cmd sed

gen_hex() { python3 -c "import secrets; print(secrets.token_hex($1))"; }

# Read key from .env (first match)
get_kv() {
  local key="$1"
  [[ -f "$ENV_FILE" ]] || return 0
  # shellcheck disable=SC2002
  cat "$ENV_FILE" | sed -n "s/^${key}=//p" | head -n 1
}

# Set key=value (replace if exists, append if missing)
set_kv() {
  local key="$1"
  local val="$2"
  if [[ -f "$ENV_FILE" ]] && grep -qE "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    printf "%s=%s\n" "$key" "$val" >> "$ENV_FILE"
  fi
}

# True if key missing or empty in file
is_missing_or_empty() {
  local key="$1"
  local v
  v="$(get_kv "$key" || true)"
  [[ -z "${v:-}" ]]
}

prompt_if_missing() {
  local key="$1"
  local prompt="$2"
  local default="${3:-}"
  if is_missing_or_empty "$key"; then
    local v=""
    if [[ -n "$default" ]]; then
      read -r -p "$prompt [$default]: " v
      v="${v:-$default}"
    else
      read -r -p "$prompt: " v
    fi
    v="$(echo -n "$v" | sed 's/^ *//; s/ *$//')"
    if [[ -z "$v" ]]; then
      echo "[gensecrets] $key is required." >&2
      exit 1
    fi
    set_kv "$key" "$v"
  fi
}

ensure_env_file() {
  if [[ -f "$ENV_FILE" ]]; then
    return 0
  fi
  if [[ -f "$ENV_EXAMPLE" ]]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo "[gensecrets] created .env from .env.example"
  else
    touch "$ENV_FILE"
    echo "[gensecrets] created blank .env (no .env.example found)"
  fi
}

main() {
  ensure_env_file
  chmod 600 "$ENV_FILE" || true

  # Prompt for non-secret required fields if missing
  prompt_if_missing "DOMAIN" "Enter DOMAIN (e.g., supasuge.com)" ""
  local domain
  domain="$(get_kv "DOMAIN" | sed 's/^"//; s/"$//')"

  prompt_if_missing "CERTBOT_EMAIL" "Enter CERTBOT_EMAIL (Let's Encrypt notifications)" ""

  # Nice-to-have derived defaults
  if is_missing_or_empty "SITE_URL"; then
    set_kv "SITE_URL" "https://${domain}"
  fi
  if is_missing_or_empty "ROOT_URL"; then
    set_kv "ROOT_URL" "https://${domain}/"
  fi
  if is_missing_or_empty "ALLOWED_HOSTS"; then
    set_kv "ALLOWED_HOSTS" "${domain},www.${domain}"
  fi

  # Generate secrets only if empty
  if is_missing_or_empty "SECRET_KEY"; then
    set_kv "SECRET_KEY" "$(gen_hex 32)"     # 64 hex chars
  fi
  if is_missing_or_empty "ANALYTICS_SALT"; then
    set_kv "ANALYTICS_SALT" "$(gen_hex 24)" # 48 hex chars
  fi

  echo "[gensecrets] updated: $ENV_FILE"
  echo "[gensecrets] permissions: 600"
}

main "$@"
