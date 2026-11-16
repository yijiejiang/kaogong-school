#!/usr/bin/env bash
set -euo pipefail

LABEL="com.kaogong.backend"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
rm -f "$PLIST"
echo "已停止并移除 $LABEL"
