from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlmodel import Session, select

from . import catalog
from .config import get_settings
from .crm import change_stage
from .db import get_session
from .letters import KINDS, SERVICE_TEXT, build_letter
from .models import Company, Contact, Deal, DealStage, Estimate, Interaction, User
from .pricing import compute
from .security import csrf_check, current_user, writer
from .web import back, render

router = APIRouter()


@router.get("/deals/{deal_id}/letter")
def letter_page(
    deal_id: int,
    request: Request,
    kind: str = "reply_kp",
    service: str = "",
    contact: str = "",
    estimate: str = "",
    reason: str = "",
    total: str = "",
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    deal = session.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404)
    company = session.get(Company, deal.company_id)
    contacts = session.exec(select(Contact).where(Contact.company_id == deal.company_id)).all()
    estimates = session.exec(select(Estimate).where(Estimate.deal_id == deal_id).order_by(Estimate.created_at.desc())).all()
    kind = kind if kind in KINDS else "reply_kp"
    if service == "general":
        service_id = ""
    elif service and service in SERVICE_TEXT:
        service_id = service
    else:
        service_id = deal.service if deal.service in SERVICE_TEXT else ""
    chosen = next((c for c in contacts if str(c.id) == contact), None) or next((c for c in contacts if c.is_primary), None) or (contacts[0] if contacts else None)
    est = next((e for e in estimates if str(e.id) == estimate), None) or (estimates[0] if estimates and kind in ("reply_kp", "followup") else None)
    s = get_settings()
    letter, error = None, ""
    if chosen and chosen.do_not_contact and kind == "offer":
        error = "Контакт в стоп-листе: первичные предложения ему не отправляем."
    else:
        try:
            letter = build_letter(
                kind, service_id,
                contact_name=(chosen.name if chosen else ""), object_name=deal.title, sender=user.name, company=s.legal_name,
                phone=s.company_phone, email=s.company_email, reason=reason,
                total=compute(est.base_mtr, est.base_smr, est.k_mtr, est.k_smr, est.vat, est.lim_percent).total if (est and total == "1") else None,
                kp_date=f"{est.updated_at:%d.%m.%Y}" if est else "",
            )
        except ValueError as e:
            error = str(e)
    to_email = chosen.email if chosen else ""
    mailto = ""
    if letter and to_email:
        mailto = f"mailto:{to_email}?subject={quote(letter.subject)}&body={quote(letter.body)}"
    return render(
        request, "letter.html", user, deal=deal, company=company, contacts=contacts, estimates=estimates, kinds=KINDS,
        kind=kind, service_id=service_id, chosen=chosen, est=est, reason=reason, total=total, letter=letter, error=error,
        to_email=to_email, mailto=mailto, service_options=[(k, v["topic"]) for k, v in SERVICE_TEXT.items() if k],
    )


@router.post("/deals/{deal_id}/letter/sent", dependencies=[Depends(csrf_check)])
def letter_sent(
    deal_id: int,
    kind: str = Form("reply_kp"),
    subject: str = Form(...),
    body: str = Form(...),
    to_email: str = Form(""),
    user: User = Depends(writer),
    session: Session = Depends(get_session),
):
    deal = session.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404)
    if "[УТОЧНИТЬ" in subject or "[УТОЧНИТЬ" in body:
        raise HTTPException(status_code=400, detail="В письме остались незаполненные места [УТОЧНИТЬ: …]")
    session.add(Interaction(
        deal_id=deal_id, kind="email", channel="email", direction="out",
        body=f"Письмо отправлено{(' на ' + to_email) if to_email else ''}\nТема: {subject}\n\n{body}", author_id=user.id,
    ))
    if kind == "reply_kp" and deal.stage in (DealStage.new, DealStage.qualified, DealStage.estimate):
        change_stage(session, deal, DealStage.proposal_sent, user.id)
    session.commit()
    return back(f"/deals/{deal_id}")


@router.post("/contacts/{contact_id}/dnc", dependencies=[Depends(csrf_check)])
def contact_dnc(contact_id: int, value: str = Form("1"), user: User = Depends(writer), session: Session = Depends(get_session)):
    c = session.get(Contact, contact_id)
    if not c:
        raise HTTPException(status_code=404)
    c.do_not_contact = value == "1"
    session.commit()
    return back(f"/companies/{c.company_id}")
