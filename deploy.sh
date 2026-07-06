#!/usr/bin/env bash
# Sync the hpilo custom component to the Home Assistant host and optionally
# restart HA core so the change is picked up.
#
# Restart uses the HA Core REST API (not the supervisor `ha` CLI, which isn't
# reachable from this SSH add-on without disabling protection mode). Configure
# your host and a long-lived access token in a local .env file next to this
# script (see .env.example):
#   HA_HOST=192.168.1.19
#   HA_TOKEN=eyJhbGciOi...
# Generate the token in HA: your profile -> Security -> Long-lived access tokens.
#
# Usage:
#   ./deploy.sh            # sync files only
#   ./deploy.sh --restart  # sync files, then restart HA core

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "${SCRIPT_DIR}/.env" ]]; then
  # shellcheck disable=SC1091
  source "${SCRIPT_DIR}/.env"
fi

if [[ -z "${HA_HOST:-}" ]]; then
  echo "Error: HA_HOST is not set. Create ${SCRIPT_DIR}/.env with HA_HOST=<your HA IP/hostname> (see .env.example)." >&2
  exit 1
fi

HA_PORT="${HA_PORT:-8123}"
REMOTE_DIR="/config/custom_components/hpilo"
LOCAL_DIR="${SCRIPT_DIR}/custom_components/hpilo"

echo "Syncing ${LOCAL_DIR} -> ${HA_HOST}:${REMOTE_DIR}"
rsync -av --delete \
  --rsync-path="sudo rsync" \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "${LOCAL_DIR}/" "${HA_HOST}:${REMOTE_DIR}/"

if [[ "${1:-}" == "--restart" ]]; then
  if [[ -z "${HA_TOKEN:-}" ]]; then
    echo "Error: HA_TOKEN is not set. Create ${SCRIPT_DIR}/.env with HA_TOKEN=<long-lived access token>." >&2
    exit 1
  fi
  echo "Restarting Home Assistant core via REST API on ${HA_HOST}:${HA_PORT}..."
  http_code=$(curl -sS -o /dev/null -w '%{http_code}' \
    -X POST \
    -H "Authorization: Bearer ${HA_TOKEN}" \
    -H "Content-Type: application/json" \
    "http://${HA_HOST}:${HA_PORT}/api/services/homeassistant/restart")
  if [[ "${http_code}" != "200" ]]; then
    echo "Error: restart request failed (HTTP ${http_code})" >&2
    exit 1
  fi
  echo "Restart triggered."
else
  echo "Done. Restart Home Assistant to load changes (Settings -> System -> Restart),"
  echo "or re-run this script with --restart (requires HA_TOKEN in ${SCRIPT_DIR}/.env)."
fi
