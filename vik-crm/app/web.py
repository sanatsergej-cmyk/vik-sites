from pathlib import Path

from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from . import catalog
from .models import STAGE_LABELS
from .security import csrf_token

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))


def _dt(value) -> str:
    return value.strftime("%d.%m.%Y %H:%M") if value else ""


def _money(value) -> str:
    if value is None:
        return ""
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


templates.env.filters["dt"] = _dt
def _money0(value) -> str:
    return f"{value:,.0f}".replace(",", " ") + " ₽" if value is not None else ""


templates.env.filters["money"] = _money
templates.env.filters["money0"] = _money0
templates.env.globals["csrf"] = csrf_token
templates.env.globals["STAGES"] = STAGE_LABELS


def render(request: Request, name: str, user=None, status_code: int = 200, **ctx):
    return templates.TemplateResponse(request, name, {"user": user, **ctx}, status_code=status_code)


def back(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


templates.env.globals["SERVICES"] = catalog.SERVICES
templates.env.filters["service_label"] = catalog.label
templates.env.globals["is_priority"] = catalog.is_priority
