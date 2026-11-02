from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from sqlmodel import Session, select

from .db import get_engine
from .models import (
    AuditLog,
    Company,
    Contact,
    Deal,
    Estimate,
    FileRecord,
    Interaction,
    Role,
    Supplier,
    SupplierRequest,
    User,
)
from .security import clear_failures, register_failure, throttled, verify_password


class AdminAuth(AuthenticationBackend):
    """Вход в /admin только для активных администраторов.

    У SQLAdmin своя сессия: по умолчанию cookie без Secure и SameSite=lax, а формы админки без CSRF-токена.
    Поэтому отдельная cookie vik_admin: Secure при HTTPS_ONLY=1, HttpOnly, SameSite=strict (браузер не отправит
    её с чужого сайта), короткий срок жизни. Неудачные входы ограничиваются так же, как в основном интерфейсе.
    """

    def __init__(self, secret_key: str, https_only: bool = True) -> None:
        self.middlewares = [
            Middleware(
                SessionMiddleware,
                secret_key=secret_key,
                session_cookie="vik_admin",
                https_only=https_only,
                same_site="strict",
                max_age=4 * 3600,
                path="/admin",
            )
        ]

    async def login(self, request) -> bool:
        form = await request.form()
        email = str(form.get("username", "")).strip().lower()
        password = str(form.get("password", ""))
        key = f"admin:{request.client.host if request.client else '?'}:{email}"
        if throttled(key):
            return False
        with Session(get_engine()) as s:
            user = s.exec(select(User).where(User.email == email)).first()
            if not user or not user.is_active or user.role != Role.admin or not verify_password(user.password_hash, password):
                register_failure(key)
                return False
            clear_failures(key)
            request.session.clear()
            request.session["admin_uid"] = user.id
        return True

    async def logout(self, request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request) -> bool:
        uid = request.session.get("admin_uid")
        if not uid:
            return False
        with Session(get_engine()) as s:
            user = s.get(User, uid)
            return bool(user and user.is_active and user.role == Role.admin)


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.name, User.role, User.is_active]
    form_excluded_columns = [User.password_hash]
    can_create = False
    can_delete = False


class CompanyAdmin(ModelView, model=Company):
    column_list = [Company.id, Company.name, Company.inn, Company.source, Company.created_at]
    column_searchable_list = [Company.name, Company.inn]


class ContactAdmin(ModelView, model=Contact):
    column_list = [Contact.id, Contact.company_id, Contact.name, Contact.phone, Contact.email]


class DealAdmin(ModelView, model=Deal):
    column_list = [Deal.id, Deal.title, Deal.stage, Deal.source, Deal.service, Deal.updated_at]
    column_searchable_list = [Deal.title]


class InteractionAdmin(ModelView, model=Interaction):
    column_list = [Interaction.id, Interaction.deal_id, Interaction.kind, Interaction.created_at]


class EstimateAdmin(ModelView, model=Estimate):
    column_list = [Estimate.id, Estimate.deal_id, Estimate.title, Estimate.status, Estimate.updated_at]


class FileAdmin(ModelView, model=FileRecord):
    column_list = [FileRecord.id, FileRecord.deal_id, FileRecord.filename, FileRecord.size, FileRecord.created_at]
    can_create = False
    can_edit = False


class SupplierAdmin(ModelView, model=Supplier):
    column_list = [Supplier.id, Supplier.name, Supplier.email, Supplier.categories]
    column_searchable_list = [Supplier.name, Supplier.categories]


class SupplierRequestAdmin(ModelView, model=SupplierRequest):
    column_list = [SupplierRequest.id, SupplierRequest.deal_id, SupplierRequest.supplier_id, SupplierRequest.status]


class AuditAdmin(ModelView, model=AuditLog):
    column_list = [AuditLog.id, AuditLog.user_id, AuditLog.action, AuditLog.entity, AuditLog.created_at]
    can_create = False
    can_edit = False
    can_delete = False


def mount_admin(app: FastAPI, secret_key: str, https_only: bool = True) -> None:
    backend = AdminAuth(secret_key=secret_key, https_only=https_only)
    admin = Admin(app, get_engine(), authentication_backend=backend, title="ВиК CRM — админка")
    for view in (
        UserAdmin, CompanyAdmin, ContactAdmin, DealAdmin, InteractionAdmin,
        EstimateAdmin, FileAdmin, SupplierAdmin, SupplierRequestAdmin, AuditAdmin,
    ):
        admin.add_view(view)
