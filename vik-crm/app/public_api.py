import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlmodel import Session

from .config import get_settings
from .crm import create_site_lead, notify_new_deal
from .db import get_session
from .models import FileRecord, now
from .validators import content_matches, normalize_contact

router = APIRouter(prefix="/api/public")
_hits: dict = defaultdict(list)
ALLOWED_EXT = {".pdf", ".dwg", ".dxf", ".xls", ".xlsx", ".doc", ".docx", ".zip", ".jpg", ".jpeg", ".png"}
MAX_FILES = 5
_MAX_TRACKED_IPS = 10000


def _limited(ip: str, limit: int) -> bool:
    t = time.time()
    if len(_hits) > _MAX_TRACKED_IPS:
        for key in [k for k, v in _hits.items() if not v or t - v[-1] >= 3600]:
            _hits.pop(key, None)
    _hits[ip] = [x for x in _hits[ip] if t - x < 3600]
    if len(_hits[ip]) >= limit:
        return True
    _hits[ip].append(t)
    return False


def _origin_allowed(request: Request) -> bool:
    """Пустой список разрешённых адресов = приём закрыт (fail closed)."""
    return request.headers.get("origin", "").rstrip("/") in get_settings().public_origins


async def public_cors(request: Request, call_next):
    """CORS только для /api/public/*: заголовки получают лишь адреса из PUBLIC_SITE_ORIGINS, без cookie."""
    if not request.url.path.startswith("/api/public/"):
        return await call_next(request)
    origin = request.headers.get("origin", "").rstrip("/")
    allowed = bool(origin) and _origin_allowed(request)
    if request.method == "OPTIONS":
        response = Response(status_code=204 if allowed else 403)
    else:
        response = await call_next(request)
    response.headers["Vary"] = "Origin"
    if allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Max-Age"] = "600"
    return response


@router.post("/lead", status_code=201)
async def public_lead(
    request: Request,
    name: str = Form("", max_length=200),
    contact: str = Form(..., min_length=3, max_length=200),
    task: str = Form(..., min_length=3, max_length=5000),
    direction: str = Form("", max_length=64),
    service: str = Form("", max_length=64),
    stage: str = Form("", max_length=64),
    object: str = Form("", max_length=300),
    consent: str = Form(""),
    source: str = Form("form", max_length=20),
    transcript: str = Form("", max_length=20000),
    website: str = Form(""),
    files: List[UploadFile] = File(default=[]),
    session: Session = Depends(get_session),
):
    s = get_settings()
    if not s.public_leads_enabled:
        raise HTTPException(status_code=404)
    if not _origin_allowed(request):
        raise HTTPException(status_code=403, detail="Origin")
    if website:
        return {"ok": True}
    ip = request.client.host if request.client else "?"
    if _limited(ip, s.public_rate_limit):
        raise HTTPException(status_code=429, detail="Слишком много обращений. Попробуйте позже.")
    if consent.lower() not in ("1", "true", "on", "yes"):
        raise HTTPException(status_code=422, detail="Нужно согласие на обработку персональных данных")
    try:
        contact = normalize_contact(contact)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    uploads = [f for f in files if f and f.filename]
    if len(uploads) > MAX_FILES:
        raise HTTPException(status_code=422, detail=f"Не больше {MAX_FILES} файлов")
    for f in uploads:
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXT:
            raise HTTPException(status_code=422, detail="Тип файла не поддерживается")
        head = await f.read(512)
        await f.seek(0)
        if not content_matches(ext, head):
            raise HTTPException(status_code=422, detail="Содержимое файла не соответствует его типу")

    note = f"Согласие на обработку персональных данных получено {now():%d.%m.%Y %H:%M} UTC, версия текста: {s.consent_version}. Источник: {source}."
    if transcript.strip():
        note += f"\n\nДиалог с консультантом:\n{transcript.strip()}"
    deal = create_site_lead(session, name=name, contact=contact, task=task, direction=direction, service=service,
                            stage=stage, object_name=object, extra_note=note)
    limit = s.public_max_upload_mb * 1024 * 1024
    s.storage_dir.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []
    try:
        for f in uploads:
            ext = Path(f.filename).suffix.lower()
            target = s.storage_dir / f"{uuid.uuid4().hex}{ext}"
            size = 0
            with open(target, "wb") as out:
                saved.append(target)
                while chunk := await f.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        raise HTTPException(status_code=413, detail=f"Файл больше {s.public_max_upload_mb} МБ")
                    out.write(chunk)
            session.add(FileRecord(deal_id=deal.id, filename=Path(f.filename).name[:255], stored_name=target.name, size=size))
    except HTTPException:
        for p in saved:
            p.unlink(missing_ok=True)
        session.rollback()
        raise
    session.commit()
    notify_new_deal(deal)
    return {"ok": True}
