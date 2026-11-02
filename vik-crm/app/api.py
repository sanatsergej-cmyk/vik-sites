import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from .config import get_settings
from .db import get_session
from .crm import create_site_lead, notify_new_deal, register_event
from .models import Company, Contact, Deal, Interaction

router = APIRouter()


class LeadIn(BaseModel):
    name: str = Field("", max_length=200)
    contact: str = Field(..., min_length=3, max_length=200)
    task: str = Field(..., min_length=3, max_length=5000)
    direction: str = Field("", max_length=64)
    service: str = Field("", max_length=64)
    stage: str = Field("", max_length=64)
    object: str = Field("", max_length=300)


@router.post("/api/leads", status_code=201)
def create_lead(payload: LeadIn, x_lead_token: str = Header(""), session: Session = Depends(get_session)):
    token = get_settings().lead_api_token
    if not token:
        raise HTTPException(status_code=404)
    if not secrets.compare_digest(x_lead_token.encode(), token.encode()):
        raise HTTPException(status_code=401)
    deal = create_site_lead(session, name=payload.name, contact=payload.contact, task=payload.task, direction=payload.direction,
                            service=payload.service, stage=payload.stage, object_name=payload.object)
    session.commit()
    notify_new_deal(deal)
    return {"deal_id": deal.id}


class EventIn(BaseModel):
    channel: str = Field(..., pattern="^(phone|email|telegram|max|whatsapp|site|meeting)$")
    direction: str = Field("in", pattern="^(in|out)$")
    kind: str = Field("message", pattern="^(call|email|message|meeting)$")
    text: str = Field("", max_length=10000)
    phone: str = Field("", max_length=40)
    email: str = Field("", max_length=200)
    telegram: str = Field("", max_length=100)
    external_id: str = Field("", max_length=200)
    duration_sec: Optional[int] = Field(None, ge=0, le=86400)
    recording_url: str = Field("", max_length=1000)


@router.post("/api/events", status_code=201)
def create_event(payload: EventIn, x_events_token: str = Header(""), session: Session = Depends(get_session)):
    """Приём событий из телефонии, почты и мессенджеров. Привязка по телефону, email или Telegram."""
    token = get_settings().events_api_token
    if not token:
        raise HTTPException(status_code=404)
    if not secrets.compare_digest(x_events_token.encode(), token.encode()):
        raise HTTPException(status_code=401)
    if not (payload.phone or payload.email or payload.telegram):
        raise HTTPException(status_code=422, detail="Нужен phone, email или telegram")
    deal, created, duplicate = register_event(
        session, channel=payload.channel, direction=payload.direction, kind=payload.kind, text=payload.text,
        phone=payload.phone, email=payload.email, telegram=payload.telegram, external_id=payload.external_id,
        duration_sec=payload.duration_sec, recording_url=payload.recording_url,
    )
    session.commit()
    if created:
        notify_new_deal(deal)
    return {"deal_id": deal.id, "created": created, "duplicate": duplicate}
