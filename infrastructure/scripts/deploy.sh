#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${IMAGE_TAG:-latest}"
TARGET_HOST="${TARGET_HOST:-localhost}"
TARGET_PATH="${TARGET_PATH:-/opt/rtml}"

ssh "$TARGET_HOST" "mkdir -p '$TARGET_PATH'"
scp docker-compose.yml "$TARGET_HOST:$TARGET_PATH/docker-compose.yml"
ssh "$TARGET_HOST" "cd '$TARGET_PATH' && docker compose pull && docker compose up -d --remove-orphans"
