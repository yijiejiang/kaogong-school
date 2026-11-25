#!/usr/bin/env bash
# 后端健康检查与重启。
#
#   ./doctor.sh            检查后端；不健康则提示该怎么做
#   ./doctor.sh restart    后端无响应时重启它（前端不动）
#   ./doctor.sh restart --force   无论是否健康都重启
#
# 判断依据：
#   有响应   → 后端活着，可能只是忙，不要乱重启
#   无响应   → 进程卡死（历史上出现过 OCR 子进程持锁不释放），重启即可恢复
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8000}"
HEALTH_URL="http://127.0.0.1:${BACKEND_PORT}/api/health"
TIMEOUT="${DOCTOR_TIMEOUT:-5}"

info() { printf '\033[0;36m▸ %s\033[0m\n' "$*"; }
ok() { printf '\033[0;32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[0;33m! %s\033[0m\n' "$*"; }
fail() { printf '\033[0;31m✗ %s\033[0m\n' "$*" >&2; }

backend_pids() {
  # --reload 下有四层：uv run → uvicorn(父) → uvicorn(子) → spawn_main(真正干活)。
  # 题面命令里带 "uvicorn app.main" 的只有前两层，真正的 worker 是 multiprocessing
  # 启动的，所以从「监听端口的进程」出发遍历整棵树，才能把 worker 也包含进来。
  local listener
  listener="$(lsof -nP -iTCP:"${BACKEND_PORT}" -sTCP:LISTEN -t 2>/dev/null | head -1)"
  [ -z "$listener" ] && return 0

  # 向上找到最顶层的 uv / uvicorn 启动进程
  local root="$listener" parent
  while :; do
    parent="$(ps -o ppid= -p "$root" 2>/dev/null | tr -d ' ')"
    [ -z "$parent" ] || [ "$parent" = "1" ] && break
    ps -o command= -p "$parent" 2>/dev/null | grep -qE "uv run uvicorn|uvicorn app\.main" || break
    root="$parent"
  done

  # 向下收集所有后代
  _walk_tree "$root"
}

_walk_tree() {
  local pid="$1" child
  echo "$pid"
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    _walk_tree "$child"
  done
}

# 返回 0 健康，1 无响应，2 端口空着（没在跑）
check_health() {
  local body
  if body="$(curl -s -m "$TIMEOUT" "$HEALTH_URL" 2>/dev/null)" && [ -n "$body" ]; then
    case "$body" in
    *'"status":"ok"'*)
      ok "后端健康：$body"
      return 0
      ;;
    *)
      warn "后端有响应但状态异常：$body"
      return 0
      ;;
    esac
  fi
  if [ -z "$(backend_pids)" ]; then
    fail "后端没有在 ${BACKEND_PORT} 端口运行"
    return 2
  fi
  fail "后端进程还在，但 ${TIMEOUT}s 内没有任何响应（卡死）"
  return 1
}

stop_backend() {
  local pids
  pids="$(backend_pids)"
  [ -z "$pids" ] && return 0
  info "停止后端进程：$(echo "$pids" | tr '\n' ' ')"
  echo "$pids" | xargs kill -TERM 2>/dev/null || true
  for _ in $(seq 1 10); do
    [ -z "$(backend_pids)" ] && return 0
    sleep 1
  done
  warn "进程没有响应 TERM，强制结束"
  echo "$pids" | xargs kill -9 2>/dev/null || true
  sleep 1
}

clean_stale_journal() {
  # WAL 模式下不再有 -journal；万一还留着旧文件，说明上次异常退出
  if [ -f backend/data/app.db-journal ]; then
    warn "发现上次遗留的回滚日志，移走备份：/tmp/app.db-journal.bak"
    mv backend/data/app.db-journal /tmp/app.db-journal.bak
  fi
}

start_backend() {
  info "启动后端（日志：/tmp/kaogong-backend.log）"
  # 完全脱离当前 shell：不这样写的话子 shell 会一直持有 stdout，
  # 脚本会停在启动那一步等它，看起来像卡死。
  (
    cd backend
    exec nohup uv run uvicorn app.main:app \
      --host 127.0.0.1 --port "$BACKEND_PORT" --reload \
      >/tmp/kaogong-backend.log 2>&1 </dev/null
  ) &
  disown 2>/dev/null || true
  for _ in $(seq 1 60); do
    if curl -s -m 2 "$HEALTH_URL" >/dev/null 2>&1; then
      ok "后端已就绪：$HEALTH_URL"
      return 0
    fi
    sleep 1
  done
  fail "后端 60 秒内没有启动，查看 /tmp/kaogong-backend.log"
  tail -20 /tmp/kaogong-backend.log 2>/dev/null
  return 1
}

ACTION="${1:-check}"
FORCE=0
[ "${2:-}" = "--force" ] && FORCE=1

case "$ACTION" in
check)
  check_health
  status=$?
  if [ "$status" -eq 1 ]; then
    echo
    info "运行 ./doctor.sh restart 重启后端"
  elif [ "$status" -eq 2 ]; then
    echo
    info "运行 ./doctor.sh restart 启动后端"
  fi
  exit 0
  ;;
restart)
  if [ "$FORCE" -eq 1 ]; then
    info "按要求强制重启"
    stop_backend
  else
    check_health
    if [ $? -eq 0 ]; then
      warn "后端是健康的，不做重启。确实要重启请加 --force"
      exit 0
    fi
    stop_backend
  fi
  clean_stale_journal
  start_backend
  ;;
*)
  fail "未知操作：$ACTION（可用：check / restart）"
  exit 1
  ;;
esac
