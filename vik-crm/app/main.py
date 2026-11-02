import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from . import api, public_api, routes, routes_extra, routes_letters
from .admin import mount_admin
from .config import get_settings
from .db import get_engine, init_db
from .web import BASE


class StripQueryFilter(logging.Filter):
    """Убирает query string из access-логов uvicorn: в /search?q=... могут быть имена, телефоны и email."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str) and "?" in args[2]:
            record.args = args[:2] + (args[2].split("?", 1)[0] + "?…",) + args[3:]
        return True


def install_log_filters() -> None:
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, StripQueryFilter) for f in access.filters):
        access.addFilter(StripQueryFilter())


def create_app() -> FastAPI:
    settings = get_settings()
    install_log_filters()
    init_db()  # создаёт недостающие таблицы при каждом старте (новые колонки так не добавляются, см. DEPLOY.md)
    app = FastAPI(title="ВиК CRM", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if settings.https_only:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if "text/html" in response.headers.get("content-type", ""):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.middleware("http")(public_api.public_cors)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        """Для healthcheck Docker и мониторинга: без авторизации и без данных, только проверка БД."""
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse({"status": "db_error"}, status_code=503)
        return {"status": "ok"}

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="vik_session",
        https_only=settings.https_only,
        same_site="lax",
        max_age=12 * 3600,
    )
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
    app.include_router(routes_extra.router)
    app.include_router(routes_letters.router)
    app.include_router(routes.router)
    app.include_router(api.router)
    app.include_router(public_api.router)
    mount_admin(app, settings.secret_key, https_only=settings.https_only)
    return app
