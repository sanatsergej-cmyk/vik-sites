FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
# Непривилегированный пользователь; /srv/data — точка монтирования тома (БД, файлы, бэкапы)
RUN useradd -r -u 10001 -d /srv -s /usr/sbin/nologin crm \
    && mkdir -p /srv/data/files /srv/data/backups \
    && chown -R crm:crm /srv/data && chmod 700 /srv/data
USER crm
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"]
# --proxy-headers + FORWARDED_ALLOW_IPS (задаётся в docker-compose.yml): реальный IP посетителя из X-Forwarded-For от Caddy
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
