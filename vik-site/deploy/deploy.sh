#!/usr/bin/env bash
# Сборка и выкладка статического сайта на VPS. Секреты сюда не вписываем.
# Использование: DEPLOY_HOST=user@server DEPLOY_PATH=/srv/vik-site ./deploy/deploy.sh
set -euo pipefail
: "${DEPLOY_HOST:?задайте DEPLOY_HOST, например user@1.2.3.4}"
DEPLOY_PATH="${DEPLOY_PATH:-/srv/vik-site}"
cd "$(dirname "$0")/.."

# Закрытый режим: индексация выключена, форма и консультант в тестовом режиме, пока не включены переменные
export ENABLE_PUBLIC_INDEXING="${ENABLE_PUBLIC_INDEXING:-0}"
export PUBLIC_FORM_ENABLED="${PUBLIC_FORM_ENABLED:-0}"

node scripts/check-content.mjs >/dev/null || { echo "Проверка текстов нашла ошибки: node scripts/check-content.mjs"; exit 1; }
npm run build
grep -q "Disallow: /" dist/robots.txt || { [ "$ENABLE_PUBLIC_INDEXING" = "1" ] || { echo "robots.txt не закрыт от индексации"; exit 1; }; }
rsync -az --delete dist/ "$DEPLOY_HOST:$DEPLOY_PATH/"
echo "Готово: $DEPLOY_HOST:$DEPLOY_PATH (индексация: $ENABLE_PUBLIC_INDEXING, форма: $PUBLIC_FORM_ENABLED)"
