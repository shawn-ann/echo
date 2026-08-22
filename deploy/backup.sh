#!/usr/bin/env bash
# Echo 数据库每日备份：pg_dump 转储 + 保留最近 14 天。
# 用法：crontab -e 添加
#   0 3 * * * /opt/echo/deploy/backup.sh >> /var/log/echo-backup.log 2>&1
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/echo}"
DB_CONTAINER="${DB_CONTAINER:-echo-db-1}"
DB_USER="${DB_USER:-echo}"
DB_NAME="${DB_NAME:-echo}"
KEEP_DAYS="${KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="$BACKUP_DIR/echo-$STAMP.sql"

# pg_dump 通过容器内 pg_dump 工具执行（避免宿主机装客户端）
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" > "$FILE"

# 压缩
gzip -f "$FILE"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] backup written: $FILE.gz"

# 清理过期备份
find "$BACKUP_DIR" -name 'echo-*.sql.gz' -mtime +"$KEEP_DAYS" -delete
