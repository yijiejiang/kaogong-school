#!/usr/bin/env bash
# 一键启动考公私塾：后端 + 前端，Ctrl-C 同时停止。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
MODE="${MODE:-auto}"

info() { printf '\033[0;36m▸ %s\033[0m\n' "$*"; }
warn() { printf '\033[0;33m! %s\033[0m\n' "$*"; }
fail() { printf '\033[0;31m✗ %s\033[0m\n' "$*" >&2; }

need() {
  command -v "$1" >/dev/null 2>&1 || {
    fail "缺少 $1，请先安装：$2"
    exit 1
  }
}

port_busy() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

# ---------- 环境检查 ----------
need uv "https://docs.astral.sh/uv/"
if command -v pnpm >/dev/null 2>&1; then
  PM="pnpm"
elif command -v npm >/dev/null 2>&1; then
  PM="npm"
else
  fail "缺少 pnpm 或 npm"
  exit 1
fi

if [ ! -f backend/.env ]; then
  info "未找到 backend/.env，从示例复制"
  cp backend/.env.example backend/.env
  # 生成随机密钥
  if command -v openssl >/dev/null 2>&1; then
    SECRET="$(openssl rand -hex 32)"
    if [[ "$(uname)" == "Darwin" ]]; then
      sed -i '' "s|^APP_SECRET_KEY=.*|APP_SECRET_KEY=$SECRET|" backend/.env
    else
      sed -i "s|^APP_SECRET_KEY=.*|APP_SECRET_KEY=$SECRET|" backend/.env
    fi
  fi
  warn "已生成 backend/.env；如需真实模型，请填写 LLM_API_BASE / LLM_API_KEY / LLM_DEFAULT_MODEL"
fi

if [ ! -d frontend/node_modules ]; then
  info "安装前端依赖（首次会稍久）"
  (cd frontend && $PM install)
fi

if [ ! -d backend/.venv ]; then
  info "安装后端依赖"
  (cd backend && uv sync)
fi

# 端口占用检查
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if port_busy "$port"; then
    fail "端口 $port 已被占用："
    lsof -nP -iTCP:"$port" -sTCP:LISTEN | tail -n +2 | awk '{printf "    PID %s  %s\n", $2, $1}'
    if [ "$port" = "$BACKEND_PORT" ]; then
      fail "如果是之前留下的后端，先停掉再运行；或换端口：BACKEND_PORT=$((port+1)) FRONTEND_PORT=$((FRONTEND_PORT+1)) ./start.sh"
    else
      fail "或换端口：FRONTEND_PORT=$((port+1)) ./start.sh"
    fi
    exit 1
  fi
done

# ---------- 启动 ----------
PIDS=()
cleanup() {
  echo
  info "正在停止服务…"
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

if [ "$MODE" = "demo" ]; then
  info "后端（演示模式，无需 API Key）"
  (cd backend && MOCK_LLM=1 exec uv run uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload) &
else
  info "后端（真实模型）"
  (cd backend && exec uv run uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload) &
fi
PIDS+=($!)

info "前端"
if [ -x frontend/node_modules/.bin/next ]; then
  (cd frontend && exec ./node_modules/.bin/next dev -p "$FRONTEND_PORT") &
else
  (cd frontend && exec $PM run dev) &
fi
PIDS+=($!)

echo
info "等待后端就绪…"
for _ in $(seq 1 60); do
  if curl -s -m 2 "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -s -m 2 "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
  fail "后端没有在 60 秒内启动，查看上面的日志"
  cleanup
fi

info "等待前端就绪…"
for _ in $(seq 1 90); do
  if curl -s -m 2 -o /dev/null "http://localhost:$FRONTEND_PORT" 2>/dev/null; then
    break
  fi
  # 前端进程意外退出时直接报错
  kill -0 "${PIDS[1]}" 2>/dev/null || {
    fail "前端启动失败，查看上面的日志"
    cleanup
  }
  sleep 1
done

echo
printf '\033[0;32m✓ 启动完成\033[0m\n'
echo "  前端：http://localhost:$FRONTEND_PORT"
echo "  后端：http://127.0.0.1:$BACKEND_PORT"
echo "  文档：http://127.0.0.1:$BACKEND_PORT/docs"
echo
echo "按 Ctrl-C 同时停止前后端。"

wait
