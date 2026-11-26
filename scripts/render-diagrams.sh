#!/usr/bin/env bash
# 把 docs/diagrams/ 下的 .mmd 重新渲染成 PNG 和 SVG。
#
#   ./scripts/render-diagrams.sh          渲染全部
#   ./scripts/render-diagrams.sh agents   只渲染 agents
#
# 改了 .mmd 之后一定要跑一次，否则仓库里的图片还是旧的，和源码对不上。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIAGRAM_DIR="$ROOT/docs/diagrams"

info() { printf '\033[0;36m▸ %s\033[0m\n' "$*"; }
ok() { printf '\033[0;32m✓ %s\033[0m\n' "$*"; }
fail() { printf '\033[0;31m✗ %s\033[0m\n' "$*" >&2; }

[ -d "$DIAGRAM_DIR" ] || {
  fail "找不到 $DIAGRAM_DIR"
  exit 1
}

if ! command -v npx >/dev/null 2>&1; then
  fail "缺少 npx，请先安装 Node.js"
  exit 1
fi

# 只渲染指定的图；没给参数就渲染全部
if [ $# -gt 0 ]; then
  sources=()
  for name in "$@"; do
    file="$DIAGRAM_DIR/${name%.mmd}.mmd"
    [ -f "$file" ] || {
      fail "没有这张图：$(basename "$file")"
      exit 1
    }
    sources+=("$file")
  done
else
  sources=("$DIAGRAM_DIR"/*.mmd)
fi

# mermaid-cli 首次调用要下载，走 npx 缓存
MMDC="npx --yes @mermaid-js/mermaid-cli"

for source in "${sources[@]}"; do
  name="$(basename "$source" .mmd)"
  info "渲染 $name"
  # 总览图节点多，放大两倍避免文字挤在一起
  scale=1
  [ "$name" = "overview" ] && scale=2

  $MMDC -i "$source" -o "$DIAGRAM_DIR/$name.png" -b white -s "$scale" >/dev/null
  $MMDC -i "$source" -o "$DIAGRAM_DIR/$name.svg" -b white >/dev/null
  ok "$name.png / $name.svg"
done

echo
ok "完成，共 ${#sources[@]} 张"
