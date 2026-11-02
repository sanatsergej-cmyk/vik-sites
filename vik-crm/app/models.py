from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.utcnow()


class Role(str, Enum):
    admin = "admin"
    manager = "manager"
    viewer = "viewer"


class DealStage(str, Enum):
    new = "new"
    qualified = "qualified"
    estimate = "estimate"
    proposal_sent = "proposal_sent"
    negotiation = "negotiation"
    won = "won"
    lost = "lost"


STAGE_PROBABILITY = {
    "new": 0.10,
    "qualified": 0.25,
    "estimate": 0.40,
    "proposal_sent": 0.55,
    "negotiation": 0.75,
    "won": 1.0,
    "lost": 0.0,
}

STAGE_LABELS = {
    "new": "Новая",
    "qualified": "Квалифицирована",
    "estimate": "Расчёт",
    "proposal_sent": "КП отправлено",
    "negotiation": "Переговоры",
    "won": "Выиграна",
    "lost": "Проиграна",
}


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str = ""
    password_hash: str
    role: Role = Role.manager
    is_active: bool = True
    created_at: datetime = Field(default_factory=now)


class Company(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    inn: str = ""
    okved: str = ""
    site: str = ""
    city: str = ""
    source: str = "manual"
    notes: str = ""
    created_at: datetime = Field(default_factory=now)


class Contact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    name: str = ""
    position: str = ""
    phone: str = ""
    email: str = ""
    telegram: str = ""
    is_primary: bool = False
    do_not_contact: bool = False


class Deal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    company_id: int = Field(foreign_key="company.id", index=True)
    stage: DealStage = DealStage.new
    source: str = "manual"
    service: str = ""
    direction: str = ""
    amount_expected: Optional[float] = None
    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")
    lost_reason: str = ""
    closed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Interaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    deal_id: int = Field(foreign_key="deal.id", index=True)
    kind: str = "note"
    channel: str = ""
    direction: str = ""
    external_id: str = Field(default="", index=True)
    duration_sec: Optional[int] = None
    recording_url: str = ""
    body: str
    author_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=now)


class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    deal_id: int = Field(foreign_key="deal.id", index=True)
    title: str
    due_at: datetime
    done: bool = False
    done_at: Optional[datetime] = None
    auto: bool = False
    notified: bool = False
    assignee_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=now)


class Estimate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    deal_id: int = Field(foreign_key="deal.id", index=True)
    title: str
    status: str = "draft"
    base_mtr: float = 0.0
    base_smr: float = 0.0
    k_mtr: float = 1.20
    k_smr: float = 1.356
    vat: float = 0.22
    lim_percent: float = 0.0
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class FileRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    deal_id: int = Field(foreign_key="deal.id", index=True)
    estimate_id: Optional[int] = Field(default=None, foreign_key="estimate.id")
    filename: str
    stored_name: str
    size: int = 0
    uploaded_by: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=now)


class Supplier(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = ""
    categories: str = ""
    contact: str = ""
    notes: str = ""


class SupplierRequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    deal_id: int = Field(foreign_key="deal.id", index=True)
    supplier_id: int = Field(foreign_key="supplier.id")
    position: str
    body: str
    status: str = "draft"
    created_at: datetime = Field(default_factory=now)


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = None
    action: str
    entity: str = ""
    entity_id: Optional[int] = None
    created_at: datetime = Field(default_factory=now)
