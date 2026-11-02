import csv
import io
import re
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import Response
from sqlmodel import Session, select

from . import catalog
from .crm import find_contact, norm_phone, notify_new_deal
from .db import get_session
from .models import Company, Contact, Deal, Estimate, Interaction, Task, User, now
from .security import csrf_check, current_user, writer
from .web import back, render

router = APIRouter()


def _csv_safe(value) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/search")
def search(request: Request, q: str = "", user: User = Depends(current_user), session: Session = Depends(get_session)):
    q = q.strip()
    res = {"companies": [], "contacts": [], "deals": [], "estimates": []}
    if len(q) >= 2:
        needle = q.casefold()
        has = lambda *vals: any(needle in (v or "").casefold() for v in vals)  # noqa: E731
        res["companies"] = [c for c in session.exec(select(Company)).all() if has(c.name, c.inn)][:20]
        res["deals"] = [d for d in session.exec(select(Deal)).all() if has(d.title)][:20]
        res["estimates"] = [e for e in session.exec(select(Estimate)).all() if has(e.title)][:20]
        digits = norm_phone(q)
        for c in session.exec(select(Contact)).all():
            if has(c.name, c.email, c.telegram) or (len(digits) >= 4 and digits in norm_phone(c.phone)):
                res["contacts"].append(c)
        res["contacts"] = res["contacts"][:20]
    companies = {c.id: c for c in session.exec(select(Company)).all()}
    return render(request, "search.html", user, q=q, res=res, companies=companies)


@router.get("/quick")
def quick_form(request: Request, user: User = Depends(writer)):
    return render(request, "quick.html", user)


@router.post("/quick", dependencies=[Depends(csrf_check)])
def quick_create(
    request: Request,
    company: str = Form(""),
    contact_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    telegram: str = Form(""),
    service: str = Form(""),
    title: str = Form(""),
    amount: str = Form(""),
    note: str = Form(""),
    user: User = Depends(writer),
    session: Session = Depends(get_session),
):
    if not (company.strip() or phone.strip() or email.strip() or telegram.strip()):
        return render(request, "quick.html", user, status_code=422, error="Укажите компанию или хотя бы один контакт (телефон, email, Telegram).")
    existing = find_contact(session, phone, email, telegram)
    if existing:
        company_id, reused = existing.company_id, True
    else:
        reused = False
        row = None
        if company.strip():
            wanted = company.strip().casefold()
            row = next((c for c in session.exec(select(Company)).all() if c.name.casefold() == wanted), None)
        if row is None:
            row = Company(name=company.strip() or f"Новый контакт ({phone or email or telegram})", source="manual")
            session.add(row)
            session.flush()
        company_id = row.id
        if contact_name.strip() or phone.strip() or email.strip() or telegram.strip():
            session.add(Contact(company_id=company_id, name=contact_name.strip(), phone=phone.strip(), email=email.strip(), telegram=telegram.strip(), is_primary=True))
    try:
        value: Optional[float] = float(amount.replace(" ", "").replace(",", ".")) if amount.strip() else None
    except ValueError:
        value = None
    deal = Deal(
        title=title.strip() or f"Сделка: {catalog.label(service) if service in catalog.BY_ID else 'новый запрос'}",
        company_id=company_id,
        service=service if service in catalog.BY_ID else "",
        amount_expected=value,
        owner_id=user.id,
        source="manual",
    )
    session.add(deal)
    session.flush()
    if note.strip():
        session.add(Interaction(deal_id=deal.id, kind="note", body=note.strip(), author_id=user.id))
    session.commit()
    notify_new_deal(deal)
    return back(f"/deals/{deal.id}" + ("?reused=1" if reused else ""))


@router.post("/deals/{deal_id}/edit", dependencies=[Depends(csrf_check)])
def deal_edit(
    deal_id: int,
    title: str = Form(...),
    service: str = Form(""),
    direction: str = Form(""),
    amount_expected: str = Form(""),
    owner_id: str = Form(""),
    user: User = Depends(writer),
    session: Session = Depends(get_session),
):
    deal = session.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404)
    deal.title = title.strip() or deal.title
    deal.service = service if service in catalog.BY_ID else ""
    deal.direction = direction.strip()
    try:
        deal.amount_expected = float(amount_expected.replace(" ", "").replace(",", ".")) if amount_expected.strip() else None
    except ValueError:
        pass
    if owner_id.isdigit() and session.get(User, int(owner_id)):
        deal.owner_id = int(owner_id)
    deal.updated_at = now()
    session.commit()
    return back(f"/deals/{deal_id}")


@router.get("/deals.csv")
def deals_csv(user: User = Depends(current_user), session: Session = Depends(get_session)):
    companies = {c.id: c.name for c in session.exec(select(Company)).all()}
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["id", "сделка", "клиент", "стадия", "вид работ", "приоритет", "сумма", "источник", "создана", "обновлена"])
    for d in session.exec(select(Deal).order_by(Deal.id)).all():
        w.writerow([
            d.id, _csv_safe(d.title), _csv_safe(companies.get(d.company_id, "")), d.stage.value,
            _csv_safe(catalog.label(d.service) if d.service else ""), "да" if catalog.is_priority(d.service) else "",
            d.amount_expected if d.amount_expected is not None else "", _csv_safe(d.source),
            f"{d.created_at:%Y-%m-%d %H:%M}", f"{d.updated_at:%Y-%m-%d %H:%M}",
        ])
    return Response(
        "﻿" + out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=deals.csv"},
    )
