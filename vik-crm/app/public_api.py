import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlmodel import Session

from .config import get_settings
from .crm import create_site_lead, notify_new_deal
from .db import get_session
from .models import FileRecord, Interaction, now

router = APIRouter(prefix="/api/public")
_hits: dict = defaultdict(list)
ALLOWED_EXT = {".pdf", ".dwg", ".dxf", ".xls", ".xlsx", ".doc", ".docx", ".zip", ".jpg", ".jpeg", ".png"}
MAX_FILES = 5


def _limited(ip: str, limit: int) -> bool:
    t = time.time()
    _hits[ip] = [x for x in _hits[ip] if t - x < 3600]
    if len(_hits[ip]) >= limit:
        return True
    _hits[ip].append(t)
    return False


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
    origins = [o.strip().rstrip("/") for o in s.public_site_origins.split(",") if o.strip()]
    if origins and request.headers.get("origin", "").rstrip("/") not in origins:
        raise HTTPException(status_code=403, detail="Origin")
    if website:
        return {"ok": True}
    ip = request.client.host if request.client else "?"
    if _limited(ip, s.public_rate_limit):
        raise HTTPException(status_code=429, detail="Слишком много обращений. Попробуйте позже.")
    if consent.lower() not in ("1", "true", "on", "yes"):
        raise HTTPException(status_code=422, detail="Нужно согласие на обработку персональных данных")
    uploads = [f for f in files if f and f.filename]
    if len(uploads) > MAX_FILES:
        raise HTTPException(status_code=422, detail=f"Не больше {MAX_FILES} файлов")
    for f in uploads:
        if Path(f.filename).suffix.lower() not in ALLOWED_EXT:
            raise HTTPException(status_code=422, detail="Тип файла не поддерживается")

    note = f"Согласие на обработку персональных данных получено {now():%d.%m.%Y %H:%M} UTC, версия текста: {s.consent_version}. Источник: {source}."
    if transcript.strip():
        note += f"\n\nДиалог с консультантом:\n{transcript.strip()}"
    deal = create_site_lead(session, name=name, contact=contact, task=task, direction=direction, service=service,
                            stage=stage, object_name=object, extra_note=note)
    limit = s.max_upload_mb * 1024 * 1024
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
                        raise HTTPException(status_code=413, detail=f"Файл больше {s.max_upload_mb} МБ")
                    out.write(chunk)
            session.add(FileRecord(deal_id=deal.id, filename=Path(f.filename).name, stored_name=target.name, size=size))
    except HTTPException:
        for p in saved:
            p.unlink(missing_ok=True)
        session.rollback()
        raise
    session.commit()
    notify_new_deal(deal)
    return {"ok": True}
