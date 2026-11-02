#!/usr/bin/env bash
# Сборка и выкладка трёх вариантов на поддомены (gold / kp / indigo). Секреты сюда не вписываем.
# Использование: DEPLOY_HOST=user@server ./deploy-variants.sh [v1|v2|v3 ...]   (без аргументов — все три)
set -euo pipefail
: "${DEPLOY_HOST:?задайте DEPLOY_HOST, например user@1.2.3.4}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export ENABLE_PUBLIC_INDEXING=0 PUBLIC_FORM_ENABLED="${PUBLIC_FORM_ENABLED:-0}"

build_one() {
  local name="$1" dir="$2" target="$3"
  echo "== $name: сборка в $dir"
  ( cd "$dir" && npx astro build )
  grep -q "Disallow: /" "$dir/dist/robots.txt" || { echo "$name: robots.txt не закрыт от индексации"; exit 1; }
  rsync -az --delete "$dir/dist/" "$DEPLOY_HOST:$target/"
  echo "== $name: выложен в $DEPLOY_HOST:$target"
}

( cd "$ROOT/vik-site" && node scripts/check-content.mjs >/dev/null ) || { echo "Проверка текстов нашла ошибки"; exit 1; }
set -- "${@:-v1 v2 v3}"
for v in $@; do
  case "$v" in
    v1) build_one "V1 Золото" "$ROOT/vik-site" /srv/vik-v1 ;;
    v2) build_one "V2 Прогрессив" "$ROOT/vik-variants/v2-kp" /srv/vik-v2 ;;
    v3) build_one "V3 Индиго" "$ROOT/vik-variants/v3-indigo" /srv/vik-v3 ;;
    *) echo "неизвестный вариант: $v"; exit 1 ;;
  esac
done
