#!/usr/bin/env bash
set -euo pipefail

TARGET_HOST="${TARGET_HOST:-localhost}"
TARGET_PATH="${TARGET_PATH:-/opt/rtml}"

ssh "$TARGET_HOST" "cd '$TARGET_PATH' && docker compose down && docker compose up -d"
