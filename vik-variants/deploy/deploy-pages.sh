#!/usr/bin/env bash
# Публикация собранных сайтов на GitHub Pages (публичные репозитории только с готовым dist).
# Использование: ./deploy-pages.sh [chooser|v1|v2|v3 ...]  (без аргументов — все)
# MODE=subpath (по умолчанию, пока нет DNS): адреса https://OWNER.github.io/<repo>/, пути переписываются rebase.py.
# MODE=domain: свои домены vikmsk.ru / gold. / kp. / indigo. (нужны DNS-записи CNAME на OWNER.github.io).
set -euo pipefail
OWNER="${GH_OWNER:-sanatsergej-cmyk}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
MODE="${MODE:-subpath}"
HERE="$(cd "$(dirname "$0")" && pwd)"
export ENABLE_PUBLIC_INDEXING=0 PUBLIC_FORM_ENABLED="${PUBLIC_FORM_ENABLED:-0}"

publish() { # name srcdir repo domain build(0/1)
  local name="$1" dir="$2" repo="$3" domain="$4" build="$5"
  echo "== $name → $repo ($domain)"
  if [ "$build" = 1 ]; then ( cd "$dir" && npx astro build >/dev/null ) && dir="$dir/dist"; fi
  rm -rf "$TMP/$repo" && mkdir -p "$TMP/$repo" && cp -R "$dir/." "$TMP/$repo/"
  touch "$TMP/$repo/.nojekyll"
  if [ "$MODE" = domain ]; then echo "$domain" > "$TMP/$repo/CNAME"; url="https://$domain/"
  else python3 "$HERE/rebase.py" "$TMP/$repo" "/$repo"; url="https://$OWNER.github.io/$repo/"
    [ "$repo" = vik-chooser ] && sed -i '' -e "s#https://gold.vikmsk.ru/#https://$OWNER.github.io/vik-gold/#; s#https://kp.vikmsk.ru/#https://$OWNER.github.io/vik-kp/#; s#https://indigo.vikmsk.ru/#https://$OWNER.github.io/vik-indigo/#" "$TMP/$repo/index.html"
  fi
  gh repo view "$OWNER/$repo" >/dev/null 2>&1 || gh repo create "$OWNER/$repo" --public --description "ВиК: закрытый стенд ($name), noindex" >/dev/null
  ( cd "$TMP/$repo" && git init -q -b main && git add -A && git -c user.name=deploy -c user.email=deploy@local commit -qm "deploy $(date +%F_%H%M)" \
    && git push -q --force "https://github.com/$OWNER/$repo.git" main )
  gh api -X POST "repos/$OWNER/$repo/pages" -f "source[branch]=main" -f "source[path]=/" >/dev/null 2>&1 || true
  if [ "$MODE" = domain ]; then gh api -X PUT "repos/$OWNER/$repo/pages" -f "cname=$domain" >/dev/null 2>&1 || true
  else gh api -X PUT "repos/$OWNER/$repo/pages" -F "cname=" >/dev/null 2>&1 || gh api -X PUT "repos/$OWNER/$repo/pages" --input - <<<'{"cname":null}' >/dev/null 2>&1 || true; fi
  echo "   готово: $url"
}

( cd "$ROOT/vik-site" && node scripts/check-content.mjs >/dev/null ) || { echo "Проверка текстов нашла ошибки"; exit 1; }
set -- "${@:-chooser v1 v2 v3}"
for v in $@; do
  case "$v" in
    chooser) publish "выбор" "$ROOT/vik-variants/chooser" vik-chooser vikmsk.ru 0 ;;
    v1) publish "Золото" "$ROOT/vik-site" vik-gold gold.vikmsk.ru 1 ;;
    v2) publish "Прогрессив" "$ROOT/vik-variants/v2-kp" vik-kp kp.vikmsk.ru 1 ;;
    v3) publish "Индиго" "$ROOT/vik-variants/v3-indigo" vik-indigo indigo.vikmsk.ru 1 ;;
  esac
done
rm -rf "$TMP"
