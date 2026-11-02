import uuid
from pathlib import Path
from typing import Optional

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlmodel import Session, func, select

from . import catalog
from .analytics import dashboard_stats, spark
from .config import get_settings
from .crm import CLOSED, change_stage as crm_change_stage
from .db import get_session
from .kp import build_kp_xlsx
from .models import (
    AuditLog,
    Company,
    Contact,
    Deal,
    DealStage,
    Estimate,
    FileRecord,
    Interaction,
    Supplier,
    SupplierRequest,
    Task,
    User,
    now,
)
from .pricing import compute
from .security import (
    admin_only,
    clear_failures,
    csrf_check,
    current_user,
    register_failure,
    throttled,
    verify_password,
    writer,
)
from .web import back, render

router = APIRouter()

ALLOWED_EXT = {".pdf", ".dwg", ".dxf", ".xls", ".xlsx", ".doc", ".docx", ".zip", ".jpg", ".jpeg", ".png", ".txt", ".csv"}
REQUEST_STATUSES = {"draft", "approved", "sent", "answered"}


def get_or_404(session: Session, model, obj_id: int):
    obj = session.get(model, obj_id)
    if not obj:
        raise HTTPException(status_code=404)
    return obj


def audit(session: Session, user: Optional[User], action: str, entity: str = "", entity_id: Optional[int] = None) -> None:
    session.add(AuditLog(user_id=user.id if user else None, action=action, entity=entity, entity_id=entity_id))


def num(value: str, default: float = 0.0) -> float:
    try:
        return float(str(value).strip().replace(" ", "").replace(",", "."))
    except ValueError:
        return default


# ---------- auth ----------
@router.get("/login")
def login_form(request: Request):
    return render(request, "login.html")


@router.post("/login", dependencies=[Depends(csrf_check)])
def login(request: Request, email: str = Form(...), password: str = Form(...), session: Session = Depends(get_session)):
    email = email.strip().lower()
    key = f"{request.client.host if request.client else '?'}:{email}"
    if throttled(key):
        raise HTTPException(status_code=429, detail="Слишком много попыток. Подождите 15 минут.")
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not user.is_active or not verify_password(user.password_hash, password):
        register_failure(key)
        return render(request, "login.html", status_code=401, error="Неверный email или пароль")
    clear_failures(key)
    request.session.clear()
    request.session["uid"] = user.id
    audit(session, user, "login")
    session.commit()
    return back("/")


@router.post("/logout", dependencies=[Depends(csrf_check)])
def logout(request: Request):
    request.session.clear()
    return back("/login")


# ---------- dashboard ----------
@router.get("/")
def dashboard(request: Request, days: int = 30, user: User = Depends(current_user), session: Session = Depends(get_session)):
    days = days if days in (7, 30, 90) else 30
    stats = dashboard_stats(session, days)
    end_of_today = now().replace(hour=23, minute=59, second=59)
    tasks = session.exec(
        select(Task, Deal).join(Deal, Deal.id == Task.deal_id).where(Task.done == False, Task.due_at <= end_of_today).order_by(Task.due_at)  # noqa: E712
    ).all()
    return render(request, "dashboard.html", user, s=stats, tasks=tasks, now=now(), spark=spark)


# ---------- companies ----------
@router.get("/companies")
def companies(request: Request, q: str = "", user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = session.exec(select(Company).order_by(Company.created_at.desc())).all()
    if q:
        needle = q.strip().casefold()
        rows = [c for c in rows if needle in c.name.casefold() or needle in (c.inn or "").casefold()]
    return render(request, "companies.html", user, items=rows[:200], q=q)


@router.post("/companies", dependencies=[Depends(csrf_check)])
def company_create(
    name: str = Form(...),
    inn: str = Form(""),
    okved: str = Form(""),
    site: str = Form(""),
    city: str = Form(""),
    notes: str = Form(""),
    user: User = Depends(writer),
    session: Session = Depends(get_session),
):
    company = Company(name=name.strip(), inn=inn.strip(), okved=okved.strip(), site=site.strip(), city=city.strip(), notes=notes)
    session.add(company)
    session.flush()
    audit(session, user, "company.create", "company", company.id)
    session.commit()
    return back(f"/companies/{company.id}")


@router.get("/companies/{company_id}")
def company_detail(company_id: int, request: Request, user: User = Depends(current_user), session: Session = Depends(get_session)):
    company = get_or_404(session, Company, company_id)
    contacts = session.exec(select(Contact).where(Contact.company_id == company_id)).all()
    deals = session.exec(select(Deal).where(Deal.company_id == company_id).order_by(Deal.created_at.desc())).all()
    return render(request, "company.html", user, company=company, contacts=contacts, deals=deals)


@router.post("/companies/{company_id}/contacts", dependencies=[Depends(csrf_check)])
def contact_create(
    company_id: int,
    name: str = Form(""),
    position: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    telegram: str = Form(""),
    user: User = Depends(writer),
    session: Session = Depends(get_session),
):
    get_or_404(session, Company, company_id)
    session.add(Contact(company_id=company_id, name=name, position=position, phone=phone, email=email, telegram=telegram))
    session.commit()
    return back(f"/companies/{company_id}")


# ---------- deals ----------
@router.get("/deals")
def deals(
    request: Request, stage: str = "", view: str = "board", owner: str = "", prio: str = "",
    user: User = Depends(current_user), session: Session = Depends(get_session),
):
    stmt = select(Deal, Company).join(Company, Company.id == Deal.company_id).order_by(Deal.updated_at.desc())
    if stage in {s.value for s in DealStage}:
        stmt = stmt.where(Deal.stage == DealStage(stage))
        view = "list"
    if owner.isdigit():
        stmt = stmt.where(Deal.owner_id == int(owner))
    rows = session.exec(stmt.limit(500)).all()
    if prio == "1":
        rows = [(d, c) for d, c in rows if catalog.is_priority(d.service)]
    columns = {st.value: [] for st in DealStage}
    for deal, company in rows:
        columns[deal.stage.value].append((deal, company))
    sums = {k: sum(d.amount_expected or 0 for d, _ in v) for k, v in columns.items()}
    next_task = {}
    for t in session.exec(select(Task).where(Task.done == False).order_by(Task.due_at)).all():  # noqa: E712
        next_task.setdefault(t.deal_id, t)
    companies_list = session.exec(select(Company).order_by(Company.name)).all()
    owners = session.exec(select(User).where(User.is_active == True)).all()  # noqa: E712
    return render(
        request, "deals.html", user, items=rows, columns=columns, sums=sums, stage=stage, view=view, owner=owner, prio=prio,
        companies=companies_list, owners=owners, next_task=next_task, now=now(),
    )


@router.post("/deals", dependencies=[Depends(csrf_check)])
def deal_create(
    title: str = Form(...),
    company_id: int = Form(...),
    service: str = Form(""),
    direction: str = Form(""),
    amount_expected: str = Form(""),
    user: User = Depends(writer),
    session: Session = Depends(get_session),
):
    get_or_404(session, Company, company_id)
    deal = Deal(
        title=title.strip(),
        company_id=company_id,
        service=service if service in catalog.BY_ID else "",
        direction=direction,
        amount_expected=num(amount_expected) if amount_expected.strip() else None,
        owner_id=user.id,
    )
    session.add(deal)
    session.flush()
    audit(session, user, "deal.create", "deal", deal.id)
    session.commit()
    return back(f"/deals/{deal.id}")


@router.get("/deals/{deal_id}")
def deal_detail(deal_id: int, request: Request, user: User = Depends(current_user), session: Session = Depends(get_session)):
    deal = get_or_404(session, Deal, deal_id)
    company = session.get(Company, deal.company_id)
    contacts = session.exec(select(Contact).where(Contact.company_id == deal.company_id)).all()
    notes = session.exec(select(Interaction).where(Interaction.deal_id == deal_id).order_by(Interaction.created_at.desc())).all()
    files = session.exec(select(FileRecord).where(FileRecord.deal_id == deal_id).order_by(FileRecord.created_at.desc())).all()
    estimates = session.exec(select(Estimate).where(Estimate.deal_id == deal_id).order_by(Estimate.created_at.desc())).all()
    totals = {e.id: compute(e.base_mtr, e.base_smr, e.k_mtr, e.k_smr, e.vat, e.lim_percent).total for e in estimates}
    requests = session.exec(
        select(SupplierRequest, Supplier).join(Supplier, Supplier.id == SupplierRequest.supplier_id).where(SupplierRequest.deal_id == deal_id)
    ).all()
    suppliers = session.exec(select(Supplier).order_by(Supplier.name)).all()
    tasks = session.exec(select(Task).where(Task.deal_id == deal_id).order_by(Task.done, Task.due_at)).all()
    owners = session.exec(select(User).where(User.is_active == True)).all()  # noqa: E712
    return render(
        request, "deal.html", user, tasks=tasks, now=now(), owners=owners, reused=request.query_params.get("reused") == "1",
        deal=deal, company=company, contacts=contacts, notes=notes, files=files,
        estimates=estimates, totals=totals, requests=requests, suppliers=suppliers,
    )


@router.post("/deals/{deal_id}/stage", dependencies=[Depends(csrf_check)])
def deal_stage(
    deal_id: int,
    stage: str = Form(...),
    lost_reason: str = Form(""),
    user: User = Depends(writer),
    session: Session = Depends(get_session),
):
    deal = get_or_404(session, Deal, deal_id)
    try:
        new_stage = DealStage(stage)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неизвестная стадия")
    crm_change_stage(session, deal, new_stage, user.id, lost_reason)
    session.commit()
    return back(f"/deals/{deal_id}")


@router.post("/deals/{deal_id}/move", dependencies=[Depends(csrf_check)])
def deal_move(deal_id: int, stage: str = Form(...), user: User = Depends(writer), session: Session = Depends(get_session)):
    deal = get_or_404(session, Deal, deal_id)
    try:
        new_stage = DealStage(stage)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неизвестная стадия")
    crm_change_stage(session, deal, new_stage, user.id)
    session.commit()
    return {"ok": True, "stage": new_stage.value}


@router.post("/deals/{deal_id}/tasks", dependencies=[Depends(csrf_check)])
def task_create(
    deal_id: int,
    title: str = Form(...),
    days: str = Form("1"),
    user: User = Depends(writer),
    session: Session = Depends(get_session),
):
    deal = get_or_404(session, Deal, deal_id)
    session.add(Task(deal_id=deal_id, title=title.strip(), due_at=now() + timedelta(days=max(int(num(days, 1)), 0)), assignee_id=user.id))
    deal.updated_at = now()
    session.commit()
    return back(f"/deals/{deal_id}")


@router.post("/tasks/{task_id}/done", dependencies=[Depends(csrf_check)])
def task_done(task_id: int, next: str = Form("/tasks"), user: User = Depends(writer), session: Session = Depends(get_session)):
    task = get_or_404(session, Task, task_id)
    task.done, task.done_at = True, now()
    session.commit()
    return back(next if next.startswith("/") and not next.startswith("//") else "/tasks")


@router.get("/tasks")
def tasks_page(request: Request, user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = session.exec(
        select(Task, Deal).join(Deal, Deal.id == Task.deal_id).where(Task.done == False).order_by(Task.due_at)  # noqa: E712
    ).all()
    return render(request, "tasks.html", user, rows=rows, now=now())


@router.post("/deals/{deal_id}/note", dependencies=[Depends(csrf_check)])
def deal_note(
    deal_id: int,
    body: str = Form(...),
    kind: str = Form("note"),
    user: User = Depends(writer),
    session: Session = Depends(get_session),
):
    deal = get_or_404(session, Deal, deal_id)
    if kind not in {"note", "call", "email", "meeting"}:
        kind = "note"
    session.add(Interaction(deal_id=deal_id, kind=kind, body=body.strip(), author_id=user.id))
    deal.updated_at = now()
    session.commit()
    return back(f"/deals/{deal_id}")


# ---------- files ----------
@router.post("/deals/{deal_id}/files", dependencies=[Depends(csrf_check)])
async def file_upload(
    deal_id: int,
    file: UploadFile = File(...),
    estimate_id: str = Form(""),
    user: User = Depends(writer),
    session: Session = Depends(get_session),
):
    settings = get_settings()
    get_or_404(session, Deal, deal_id)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Тип файла не разрешён: {ext or 'без расширения'}")
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"
    target = settings.storage_dir / stored
    limit, size = settings.max_upload_mb * 1024 * 1024, 0
    try:
        with open(target, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(status_code=413, detail=f"Файл больше {settings.max_upload_mb} МБ")
                out.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    rec = FileRecord(
        deal_id=deal_id,
        estimate_id=int(estimate_id) if estimate_id.isdigit() else None,
        filename=Path(file.filename or stored).name,
        stored_name=stored,
        size=size,
        uploaded_by=user.id,
    )
    session.add(rec)
    audit(session, user, "file.upload", "deal", deal_id)
    session.commit()
    return back(f"/estimates/{rec.estimate_id}" if rec.estimate_id else f"/deals/{deal_id}")


@router.get("/files/{file_id}")
def file_download(file_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
    rec = get_or_404(session, FileRecord, file_id)
    path = get_settings().storage_dir / rec.stored_name
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path, filename=rec.filename, media_type="application/octet-stream")


# ---------- estimates ----------
@router.post("/deals/{deal_id}/estimates", dependencies=[Depends(csrf_check)])
def estimate_create(deal_id: int, title: str = Form(...), user: User = Depends(writer), session: Session = Depends(get_session)):
    get_or_404(session, Deal, deal_id)
    s = get_settings()
    est = Estimate(deal_id=deal_id, title=title.strip(), k_mtr=s.k_mtr, k_smr=s.k_smr, vat=s.vat)
    session.add(est)
    session.flush()
    audit(session, user, "estimate.create", "estimate", est.id)
    session.commit()
    return back(f"/estimates/{est.id}")


@router.get("/estimates/{est_id}")
def estimate_detail(est_id: int, request: Request, user: User = Depends(current_user), session: Session = Depends(get_session)):
    est = get_or_404(session, Estimate, est_id)
    deal = session.get(Deal, est.deal_id)
    files = session.exec(select(FileRecord).where(FileRecord.estimate_id == est_id)).all()
    p = compute(est.base_mtr, est.base_smr, est.k_mtr, est.k_smr, est.vat, est.lim_percent)
    return render(request, "estimate.html", user, est=est, deal=deal, files=files, p=p)


@router.post("/estimates/{est_id}", dependencies=[Depends(csrf_check)])
def estimate_update(
    est_id: int,
    title: str = Form(...),
    status: str = Form("draft"),
    base_mtr: str = Form("0"),
    base_smr: str = Form("0"),
    k_mtr: str = Form("1"),
    k_smr: str = Form("1"),
    vat: str = Form("0.22"),
    lim_percent: str = Form("0"),
    user: User = Depends(writer),
    session: Session = Depends(get_session),
):
    est = get_or_404(session, Estimate, est_id)
    was_sent = est.status == "sent"
    est.title = title.strip()
    est.status = status if status in {"draft", "final", "sent"} else "draft"
    est.base_mtr, est.base_smr = max(num(base_mtr), 0), max(num(base_smr), 0)
    est.k_mtr, est.k_smr = max(num(k_mtr, 1), 0), max(num(k_smr, 1), 0)
    est.vat, est.lim_percent = min(max(num(vat, 0.22), 0), 1), max(num(lim_percent), 0)
    est.updated_at = now()
    audit(session, user, "estimate.update", "estimate", est_id)
    if est.status == "sent" and not was_sent:
        deal = session.get(Deal, est.deal_id)
        if deal and deal.stage in (DealStage.new, DealStage.qualified, DealStage.estimate):
            crm_change_stage(session, deal, DealStage.proposal_sent, user.id)
        session.add(Interaction(deal_id=est.deal_id, kind="email", channel="email", direction="out", body=f"КП отправлено заказчику: {est.title}", author_id=user.id))
    session.commit()
    return back(f"/estimates/{est_id}")


def _xlsx(content: bytes, name: str) -> Response:
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{name}"},
    )


@router.get("/estimates/{est_id}/kp.xlsx")
def kp_download(est_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
    est = get_or_404(session, Estimate, est_id)
    deal = get_or_404(session, Deal, est.deal_id)
    return _xlsx(build_kp_xlsx(get_settings(), deal, est), f"KP_{est.id}.xlsx")


@router.get("/estimates/{est_id}/kp-internal.xlsx")
def kp_internal_download(est_id: int, user: User = Depends(admin_only), session: Session = Depends(get_session)):
    est = get_or_404(session, Estimate, est_id)
    deal = get_or_404(session, Deal, est.deal_id)
    return _xlsx(build_kp_xlsx(get_settings(), deal, est, internal=True), f"KP_{est.id}_internal.xlsx")


# ---------- suppliers ----------
@router.get("/suppliers")
def suppliers(request: Request, user: User = Depends(current_user), session: Session = Depends(get_session)):
    return render(request, "suppliers.html", user, items=session.exec(select(Supplier).order_by(Supplier.name)).all())


@router.post("/suppliers", dependencies=[Depends(csrf_check)])
def supplier_create(
    name: str = Form(...),
    email: str = Form(""),
    categories: str = Form(""),
    contact: str = Form(""),
    notes: str = Form(""),
    user: User = Depends(writer),
    session: Session = Depends(get_session),
):
    session.add(Supplier(name=name.strip(), email=email.strip(), categories=categories, contact=contact, notes=notes))
    session.commit()
    return back("/suppliers")


@router.post("/deals/{deal_id}/supplier-requests", dependencies=[Depends(csrf_check)])
def request_create(
    deal_id: int,
    supplier_id: int = Form(...),
    position: str = Form(...),
    user: User = Depends(writer),
    session: Session = Depends(get_session),
):
    s = get_settings()
    deal = get_or_404(session, Deal, deal_id)
    supplier = get_or_404(session, Supplier, supplier_id)
    sender = s.legal_name or "ВиК"
    body = (
        f"Здравствуйте!\n\n"
        f"Просим предоставить коммерческое предложение (стоимость и сроки поставки) по позиции:\n{position.strip()}\n\n"
        f"Объект: {deal.title}\n\n"
        f"{s.request_contact}\n\n"
        f"Это письмо сформировано автоматически системой {sender}."
    )
    req = SupplierRequest(deal_id=deal_id, supplier_id=supplier.id, position=position.strip(), body=body)
    session.add(req)
    audit(session, user, "supplier_request.create", "deal", deal_id)
    session.commit()
    return back(f"/deals/{deal_id}")


@router.post("/supplier-requests/{req_id}/status", dependencies=[Depends(csrf_check)])
def request_status(req_id: int, status: str = Form(...), user: User = Depends(writer), session: Session = Depends(get_session)):
    req = get_or_404(session, SupplierRequest, req_id)
    if status not in REQUEST_STATUSES:
        raise HTTPException(status_code=400)
    req.status = status
    session.commit()
    return back(f"/deals/{req.deal_id}")
