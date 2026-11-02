# Выкладка закрытого стенда

1. На сервере: установить Caddy, создать папку `/srv/vik-site`, положить `deploy/Caddyfile` в `/etc/caddy/Caddyfile`, задать `SITE_DOMAIN`, перезапустить Caddy.
2. DNS: A-записи `домен` и `app.домен` на IP сервера (записи почты Яндекса не трогаем).
3. Локально: `DEPLOY_HOST=user@server ./deploy/deploy.sh`.
4. Проверить: `curl -sI https://домен/ | grep -i x-robots-tag` и `curl https://домен/robots.txt` (должен быть `Disallow: /`).
5. Заявки и консультант остаются в тестовом режиме, пока в сборке не включено `PUBLIC_FORM_ENABLED=1` и в CRM `PUBLIC_LEADS_ENABLED=1` (после юридических условий публикации).
