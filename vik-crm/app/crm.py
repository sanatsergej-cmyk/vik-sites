import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlmodel import Session, select

from . import catalog
from .models import Company, Contact, Deal, DealStage, Interaction, Task, now
from .notify import deal_link, notify

FOLLOWUP_RULES = {
    DealStage.estimate: (1, "Закончить расчёт и отправить КП"),
    DealStage.proposal_sent: (3, "Дожим по КП: уточнить, получено ли КП, ответить на вопросы"),
    DealStage.negotiation: (2, "Follow-up по переговорам: зафиксировать следующий шаг"),
}
CLOSED = (DealStage.won, DealStage.lost)


def add_auto_task(session: Session, deal: Deal, days: int, title: str) -> None:
    exists = session.exec(select(Task).where(Task.deal_id == deal.id, Task.title == title, Task.done == False)).first()  # noqa: E712
    if not exists:
        session.add(Task(deal_id=deal.id, title=title, due_at=now() + timedelta(days=days), auto=True, assignee_id=deal.owner_id))


def change_stage(session: Session, deal: Deal, stage: DealStage, user_id: Optional[int], lost_reason: str = "") -> None:
    deal.stage = stage
    deal.lost_reason = lost_reason if stage == DealStage.lost else ""
    deal.updated_at = now()
    deal.closed_at = now() if stage in CLOSED else None
    session.add(Interaction(deal_id=deal.id, kind="stage", body=f"Стадия: {stage.value}", author_id=user_id))
    if stage in CLOSED:
        for t in session.exec(select(Task).where(Task.deal_id == deal.id, Task.done == False)).all():  # noqa: E712
            t.done, t.done_at = True, now()
    elif stage in FOLLOWUP_RULES:
        days, title = FOLLOWUP_RULES[stage]
        add_auto_task(session, deal, days, title)


def norm_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits[-10:] if len(digits) >= 10 else digits


def norm_tg(value: str) -> str:
    return (value or "").strip().lstrip("@").lower()


def find_contact(session: Session, phone: str = "", email: str = "", telegram: str = "") -> Optional[Contact]:
    p, e, t = norm_phone(phone), (email or "").strip().lower(), norm_tg(telegram)
    for c in session.exec(select(Contact)).all():
        if p and norm_phone(c.phone) == p:
            return c
        if e and c.email.strip().lower() == e:
            return c
        if t and norm_tg(c.telegram) == t:
            return c
    return None


def register_event(
    session: Session,
    *,
    channel: str,
    direction: str,
    kind: str,
    text: str,
    phone: str = "",
    email: str = "",
    telegram: str = "",
    external_id: str = "",
    duration_sec: Optional[int] = None,
    recording_url: str = "",
) -> Tuple[Deal, bool, bool]:
    """Единая точка входа для звонков, писем и сообщений. Возвращает (сделка, создана_ли_сделка, дубликат)."""
    if external_id:
        dup = session.exec(select(Interaction).where(Interaction.external_id == external_id, Interaction.channel == channel)).first()
        if dup:
            return session.get(Deal, dup.deal_id), False, True
    contact = find_contact(session, phone, email, telegram)
    created = False
    deal: Optional[Deal] = None
    if contact:
        deals = session.exec(select(Deal).where(Deal.company_id == contact.company_id).order_by(Deal.updated_at.desc())).all()
        deal = next((d for d in deals if d.stage not in CLOSED), None)
        company_id = contact.company_id
    else:
        ident = phone or email or telegram or "неизвестный контакт"
        company = Company(name=f"Новый контакт ({ident})", source=channel)
        session.add(company)
        session.flush()
        session.add(Contact(company_id=company.id, phone=phone, email=email, telegram=telegram, is_primary=True))
        company_id = company.id
    if deal is None:
        deal = Deal(title=f"Входящее обращение ({channel})", company_id=company_id, source=channel)
        session.add(deal)
        session.flush()
        created = True
        if direction == "in":
            add_auto_task(session, deal, 0, "Ответить на входящее обращение")
    session.add(
        Interaction(
            deal_id=deal.id, kind=kind, channel=channel, direction=direction, body=text,
            external_id=external_id, duration_sec=duration_sec, recording_url=recording_url,
        )
    )
    deal.updated_at = now()
    session.flush()
    return deal, created, False


def notify_new_deal(deal: Deal) -> None:
    notify(f"Новая заявка №{deal.id} ({deal.source}). Открыть в CRM: {deal_link(deal.id)}")


def due_task_notifications(session: Session) -> int:
    """Вызывается по cron на сервере: один раз уведомляет о задачах, срок которых наступил."""
    sent = 0
    for t in session.exec(select(Task).where(Task.done == False, Task.notified == False, Task.due_at <= now())).all():  # noqa: E712
        if notify(f"Задача по сделке №{t.deal_id}: {t.title}. Открыть: {deal_link(t.deal_id)}"):
            t.notified = True
            sent += 1
    session.commit()
    return sent


def create_site_lead(
    session: Session, *, name: str, contact: str, task: str, direction: str = "", service: str = "",
    stage: str = "", object_name: str = "", extra_note: str = "",
) -> Deal:
    """Заявка с сайта: компания, контакт, сделка и первая запись в истории."""
    company = Company(name=name.strip() or "Заявка с сайта", source="site")
    session.add(company)
    session.flush()
    is_email = "@" in contact
    is_tg = contact.strip().startswith("@")
    session.add(Contact(
        company_id=company.id, name=name.strip(),
        email=contact.strip() if is_email else "", telegram=contact.strip() if is_tg and not is_email else "",
        phone="" if (is_email or is_tg) else contact.strip(), is_primary=True,
    ))
    deal = Deal(
        title=object_name.strip() or f"Заявка с сайта: {direction or 'без направления'}",
        company_id=company.id, source="site", service=service if service in catalog.BY_ID else "", direction=direction,
    )
    session.add(deal)
    session.flush()
    session.add(Interaction(deal_id=deal.id, kind="note", channel="site", direction="in",
                            body=f"Заявка с сайта. Стадия: {stage or '—'}.\n{task}" + (f"\n\n{extra_note}" if extra_note else "")))
    add_auto_task(session, deal, 0, "Ответить на заявку с сайта")
    return deal
