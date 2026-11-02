#!/usr/bin/env bash
# Резервная копия ВиК CRM: SQLite (онлайн, без остановки) + файлы заявок.
# Запуск на сервере из любой папки: /opt/vik-sites/vik-crm/scripts/backup.sh
# Переменные: BACKUP_HOST_DIR (куда класть на хосте), BACKUP_KEEP_DAYS (сколько дней хранить),
#             BACKUP_REMOTE (необязательно: rsync-адрес второй площадки, например user@backup-host:/srv/vik-crm/)
set -euo pipefail
cd "$(dirname "$0")/.."

DEST="${BACKUP_HOST_DIR:-/var/backups/vik-crm}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"
umask 077
mkdir -p "$DEST"

# 1. Копия внутри тома (контейнер хранит последние 3), команда печатает пути созданных файлов
paths=$(docker compose exec -T app python -m app.cli backup --keep 3)

# 2. Забираем на хост
for p in $paths; do
  docker compose cp "app:$p" "$DEST/"
done

# 3. Целостность копии проверяет сама команда backup (PRAGMA integrity_check), иначе скрипт падает на шаге 1
latest_db="$DEST/$(basename "$(echo "$paths" | grep 'crm-.*\.db$')")"
test -s "$latest_db"

# 4. Ротация на хосте
find "$DEST" -maxdepth 1 -type f \( -name 'crm-*.db' -o -name 'files-*.tar.gz' \) -mtime +"$KEEP_DAYS" -delete

# 5. Вторая площадка (копия на том же сервере не спасает от потери сервера)
if [ -n "${BACKUP_REMOTE:-}" ]; then
  rsync -a "$DEST/" "$BACKUP_REMOTE"
fi

echo "$(date -Is) backup ok: $latest_db"
