#!/usr/bin/env bash
# 服务器本地构建并重启（不使用 GitHub Actions / ACR）。
# 用法：在服务器上执行
#   /root/echo/deploy/update.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  echo "缺少 $ROOT_DIR/.env，请先按 deploy/.env.example 配置" >&2
  exit 1
fi

if [ -s "$HOME/.ssh/echo_deploy_key" ]; then
  export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/echo_deploy_key -o IdentitiesOnly=yes"
fi

RESUME_MARKER="--after-self-update"

echo "==> 拉取 origin/master"
git fetch origin master
# 修复部分旧 clone 缺失的远程跟踪引用，让 origin/master 也可用。
git update-ref refs/remotes/origin/master FETCH_HEAD
git reset --hard FETCH_HEAD
echo "==> 当前提交: $(git log --oneline -1)"

# 脚本自身可能也在这个提交里更新了；重新执行一次新版本，避免旧逻辑继续运行。
if [ "${1:-}" != "$RESUME_MARKER" ]; then
  exec "$ROOT_DIR/deploy/update.sh" "$RESUME_MARKER"
fi

COMPOSE=(
  docker compose
  --env-file "$ROOT_DIR/.env"
  -f "$ROOT_DIR/deploy/docker-compose.prod.yml"
  -f "$ROOT_DIR/deploy/docker-compose.build.yml"
)

echo "==> 构建 api / web 镜像"
"${COMPOSE[@]}" build api web

echo "==> 重启服务"
"${COMPOSE[@]}" up -d --remove-orphans
"${COMPOSE[@]}" ps

echo "==> 清理悬空镜像"
docker image prune -f

echo "==> 更新完成"
