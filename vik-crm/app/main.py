from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import api, public_api, routes, routes_extra, routes_letters
from .admin import mount_admin
from .config import get_settings
from .db import init_db
from .web import BASE


def create_app() -> FastAPI:
    settings = get_settings()
    init_db()
    app = FastAPI(title="ВиК CRM", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if "text/html" in response.headers.get("content-type", ""):
            response.headers["Cache-Control"] = "no-store"
        return response

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
    mount_admin(app, settings.secret_key)
    return app
