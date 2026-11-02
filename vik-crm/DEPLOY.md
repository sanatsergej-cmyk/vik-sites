# Выкладка ВиК CRM на VPS (Ubuntu + Docker + Caddy)

Схема: CRM работает в одном Docker-контейнере и слушает только `127.0.0.1:8000`. Снаружи её видно через Caddy:

- `https://app.vikmsk.ru` — интерфейс CRM и админка `/admin` (вход по логину и паролю);
- `https://vikmsk.ru/api/public/*`, `https://gold.vikmsk.ru/api/public/*`, `https://kp.vikmsk.ru/api/public/*`, `https://indigo.vikmsk.ru/api/public/*` — приём заявок с сайтов. Caddy каждого сайта проксирует этот путь в CRM, поэтому браузер шлёт заявку на свой же домен.

База — SQLite, файлы заявок — там же, в Docker-томе `crmdata` (`/srv/data` в контейнере). Контейнер работает от непривилегированного пользователя (uid 10001), с файловой системой только для чтения (кроме тома и `/tmp`), без capabilities, с healthcheck `GET /healthz`.

> **Юридическое условие.** Пока не отправлено уведомление в Роскомнадзор об обработке персональных данных и юрист не утвердил политику обработки ПДн и текст согласия, публичный приём заявок держим выключенным: `PUBLIC_LEADS_ENABLED=0`. Включать только на время теста (раздел 8) и сразу выключать обратно.

---

## 1. Что подготовить

- VPS с Ubuntu 22.04 или 24.04, доступ по SSH с правами sudo.
- DNS: A-запись `app.vikmsk.ru` на IP сервера (записи сайтов `vikmsk.ru`, `gold`, `kp`, `indigo` — как в `vik-site/deploy/README.md`; почтовые записи не трогаем).
- Открытые порты: 22, 80, 443. Порт 8000 наружу **не** открываем.

```bash
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable
```

## 2. Docker и Caddy

```bash
# Docker Engine + compose plugin (официальный репозиторий Docker)
sudo apt-get update && sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Caddy (официальный репозиторий Caddy)
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update && sudo apt-get install -y caddy
```

## 3. Код

```bash
sudo mkdir -p /opt && cd /opt
sudo git clone https://github.com/sanatsergej-cmyk/vik-sites.git
cd /opt/vik-sites/vik-crm
```

## 4. Файл `.env`

```bash
sudo cp .env.example .env
sudo chmod 600 .env
sudo nano .env
```

Секреты задаёт владелец прямо на сервере. В репозиторий, чаты и письма они не попадают; `.env` в `.gitignore` и `.dockerignore`.

| Переменная | Кто и как задаёт | Значение |
|---|---|---|
| `SECRET_KEY` | владелец, генерирует на сервере: `python3 -c "import secrets;print(secrets.token_urlsafe(48))"` | обязательна, не короче 32 символов; без неё CRM не стартует. Смена ключа разлогинит всех |
| `HTTPS_ONLY` | оставить | `1` (cookie только по HTTPS, HSTS) |
| `PUBLIC_BASE_URL` | оставить | `https://app.vikmsk.ru` (ссылки в уведомлениях) |
| `TELEGRAM_BOT_TOKEN` | владелец: бот в @BotFather → `/newbot` → токен | пусто = уведомлений нет |
| `TELEGRAM_CHAT_ID` | владелец: id чата/группы сотрудников (написать боту, затем `https://api.telegram.org/bot<токен>/getUpdates` → `chat.id`) | куда приходят «Новая заявка №N, ссылка» (без имён и телефонов) |
| `TELEGRAM_ALLOWED_CHAT_IDS` | владелец, если включает бота пересчёта наценок | id через запятую |
| `PUBLIC_LEADS_ENABLED` | владелец | **`0`** до выполнения юридических условий |
| `PUBLIC_SITE_ORIGINS` | оставить | `https://vikmsk.ru,https://gold.vikmsk.ru,https://kp.vikmsk.ru,https://indigo.vikmsk.ru`. Пусто = приём закрыт для всех |
| `CONSENT_VERSION` | владелец после утверждения юристом | версия/дата текста согласия, например `2026-11-15`; пишется в каждую заявку |
| `PUBLIC_RATE_LIMIT_PER_HOUR`, `PUBLIC_MAX_UPLOAD_MB`, `MAX_UPLOAD_MB` | по желанию | 10 заявок/час с IP; 10 МБ на файл заявки (до 5 файлов); 25 МБ на файл сотрудника |
| `LEAD_API_TOKEN`, `EVENTS_API_TOKEN` | владелец, только если подключает интеграции (генерация как у `SECRET_KEY`) | пусто = `/api/leads` и `/api/events` выключены |
| `COMPANY_LEGAL_NAME`, `COMPANY_REQUISITES`, `COMPANY_PHONE`, `COMPANY_EMAIL` | владелец после регистрации юрлица | шапка КП и подпись в письмах |

`DATABASE_URL`, `STORAGE_DIR`, `BACKUP_DIR` и `FORWARDED_ALLOW_IPS` задаёт `docker-compose.yml`, в `.env` их менять не нужно.

## 5. Запуск

```bash
cd /opt/vik-sites/vik-crm
sudo docker compose up -d --build
sudo docker compose ps            # app должен быть в состоянии healthy (через ~20 секунд)
curl -s http://127.0.0.1:8000/healthz   # {"status":"ok"}
```

Таблицы БД создаются автоматически при старте. Первый администратор (пароль вводится интерактивно, не короче 10 символов):

```bash
sudo docker compose exec app python -m app.cli create-user ВАШ_EMAIL --name "Имя" --role admin
```

Остальных сотрудников так же, с `--role manager` или `--role viewer`.

Необязательно — Telegram-бот пересчёта наценок: `sudo docker compose --profile bot up -d`.

## 6. Caddy

Блок для CRM добавить в `/etc/caddy/Caddyfile` (рядом с блоками сайтов из `vik-site/deploy/Caddyfile` и `vik-variants/deploy/Caddyfile.variants`):

```caddy
app.vikmsk.ru {
	encode zstd gzip
	request_body {
		max_size 30MB
	}
	header {
		X-Robots-Tag "noindex, nofollow, noarchive"
		-Server
	}
	reverse_proxy 127.0.0.1:8000
}
```

В блоках сайтов путь заявок уже проксируется в CRM. Добавьте ограничение размера тела запроса (5 файлов по 10 МБ плюс текст):

```caddy
	handle /api/public/* {
		request_body {
			max_size 60MB
		}
		reverse_proxy 127.0.0.1:8000
	}
```

Caddy передаёт IP посетителя в `X-Forwarded-For`; CRM ему доверяет (`FORWARDED_ALLOW_IPS=*` безопасно, потому что порт 8000 открыт только на localhost). Это нужно, чтобы лимит заявок считался по посетителю, а не один на всех.

```bash
sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy
```

Сертификаты Caddy выпустит сам, когда DNS указывает на сервер.

## 7. Проверка после выкладки

```bash
curl -sI https://app.vikmsk.ru/login | grep -Ei 'strict-transport|x-frame|x-robots'
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://vikmsk.ru/api/public/lead   # 404, пока приём выключен
```

В браузере: вход на `https://app.vikmsk.ru`, cookie `vik_session` с флагами Secure, HttpOnly, SameSite=Lax; админка `https://app.vikmsk.ru/admin` — только для роли admin, cookie `vik_admin` (Secure, HttpOnly, SameSite=Strict). После 5 неверных паролей вход блокируется на 15 минут.

## 8. Приём заявок с сайтов

Нужно два переключателя: в CRM `PUBLIC_LEADS_ENABLED=1` и в сборке сайта `PUBLIC_FORM_ENABLED=1` (см. `vik-site/deploy/README.md`).

**Тест до выполнения юридических условий** (на 10–15 минут, только свои тестовые данные):

```bash
sudo sed -i 's/^PUBLIC_LEADS_ENABLED=.*/PUBLIC_LEADS_ENABLED=1/' .env && sudo docker compose up -d
# отправить тестовую заявку с сайта, проверить сделку в CRM и уведомление в Telegram
sudo sed -i 's/^PUBLIC_LEADS_ENABLED=.*/PUBLIC_LEADS_ENABLED=0/' .env && sudo docker compose up -d
```

Тестовые сделки удалить в админке.

**Постоянное включение** — только когда: уведомление в Роскомнадзор подано, политика обработки ПДн и текст согласия утверждены юристом и опубликованы на сайтах, `CONSENT_VERSION` выставлена на версию утверждённого текста.

Что проверяет CRM у каждой заявки: Origin из `PUBLIC_SITE_ORIGINS` (чужие адреса — 403, CORS-заголовки только для своих), honeypot-поле, лимит заявок с IP в час, отметку согласия, контакт (телефон 10–15 цифр, email или `@username` Telegram), до 5 файлов с разрешёнными расширениями, у которых содержимое совпадает с типом (под видом `.pdf` не пройдёт исполняемый файл), размер каждого файла.

## 9. Бэкапы

`scripts/backup.sh` делает онлайн-копию SQLite (без остановки, с проверкой целостности) и архив файлов, забирает их из тома в `/var/backups/vik-crm` (права 600) и удаляет копии старше 30 дней.

```bash
sudo /opt/vik-sites/vik-crm/scripts/backup.sh          # проверить вручную
sudo cp /opt/vik-sites/vik-crm/scripts/cron.example /etc/cron.d/vik-crm
sudo chmod 644 /etc/cron.d/vik-crm                     # бэкап в 03:30, напоминания, проверка ФГИС
```

Копия на том же сервере не спасает от потери сервера: задайте `BACKUP_REMOTE` (rsync на другую площадку) в строке cron или копируйте `/var/backups/vik-crm` в хранилище в РФ. В бэкапах персональные данные, хранить их нужно с теми же мерами защиты.

**Восстановление** (пример для копии `20261102-033000`):

```bash
cd /opt/vik-sites/vik-crm
sudo docker compose stop app
sudo install -d -m 755 /tmp/vik-restore
sudo install -m 644 /var/backups/vik-crm/crm-20261102-033000.db /var/backups/vik-crm/files-20261102-033000.tar.gz /tmp/vik-restore/
sudo docker compose run --rm --no-deps -v /tmp/vik-restore:/restore:ro app sh -c \
  'cp /restore/crm-20261102-033000.db /srv/data/crm.db && rm -f /srv/data/crm.db-wal /srv/data/crm.db-shm && tar -xzf /restore/files-20261102-033000.tar.gz -C /srv/data'
sudo rm -r /tmp/vik-restore
sudo docker compose up -d
```

## 10. Обновление

```bash
cd /opt/vik-sites/vik-crm
sudo ./scripts/backup.sh
sudo git pull
sudo docker compose up -d --build
sudo docker compose ps
```

При старте создаются только новые таблицы. Новые колонки в существующих таблицах так не добавляются (миграций alembic пока нет): если в обновлении меняется схема, это будет отдельно указано в описании изменений вместе с командой миграции.

## 11. Логи

```bash
sudo docker compose logs -f app
```

В логах нет персональных данных: из access-лога убирается query string (поиск по телефону или имени не попадает в журнал), ошибки Telegram пишутся только типом исключения, в Telegram уходит только номер заявки и ссылка. Docker хранит до 5 файлов логов по 10 МБ.
