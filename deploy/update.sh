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

echo "==> 拉取 origin/master"
git fetch origin master
git reset --hard origin/master
echo "==> 当前提交: $(git log --oneline -1)"

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
