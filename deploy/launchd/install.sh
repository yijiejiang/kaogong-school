#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UV_BIN="$(command -v uv || true)"
if [[ -z "$UV_BIN" ]]; then
  echo "找不到 uv，请先安装：https://docs.astral.sh/uv/" >&2
  exit 1
fi

LABEL="com.kaogong.backend"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
TEMPLATE="$PROJECT_DIR/deploy/launchd/$LABEL.plist.template"
DOMAIN="gui/$(id -u)"

mkdir -p "$HOME/Library/LaunchAgents" "$PROJECT_DIR/backend/data/logs"

sed -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" \
    -e "s|__UV_BIN__|$UV_BIN|g" \
    -e "s|__HOME__|$HOME|g" \
    "$TEMPLATE" > "$PLIST"

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl enable "$DOMAIN/$LABEL"
launchctl kickstart -k "$DOMAIN/$LABEL"

echo "已安装并启动 $LABEL"
echo "  后端：http://127.0.0.1:8000"
echo "  日志：$PROJECT_DIR/backend/data/logs/backend.out.log"
echo "  卸载：make uninstall-service"
