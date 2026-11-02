import secrets
import time
from collections import defaultdict
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, Form, HTTPException, Request
from sqlmodel import Session

from .db import get_session
from .models import Role, User

_ph = PasswordHasher()
_failures: dict = defaultdict(list)
MAX_FAILS, WINDOW = 5, 15 * 60


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Пароль должен быть не короче 10 символов")
    return _ph.hash(password)


def verify_password(hashed: str, password: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerificationError:
        return False


def throttled(key: str) -> bool:
    now = time.time()
    _failures[key] = [t for t in _failures[key] if now - t < WINDOW]
    return len(_failures[key]) >= MAX_FAILS


def register_failure(key: str) -> None:
    _failures[key].append(time.time())


def clear_failures(key: str) -> None:
    _failures.pop(key, None)


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf"] = token
    return token


async def csrf_check(request: Request, csrf: str = Form("")) -> None:
    expected = request.session.get("csrf", "")
    if not expected or not secrets.compare_digest(expected.encode(), csrf.encode()):
        raise HTTPException(status_code=403, detail="CSRF")


def _login_redirect() -> HTTPException:
    return HTTPException(status_code=303, headers={"Location": "/login"})


def current_user(request: Request, session: Session = Depends(get_session)) -> User:
    uid: Optional[int] = request.session.get("uid")
    user = session.get(User, uid) if uid else None
    if not user or not user.is_active:
        request.session.clear()
        raise _login_redirect()
    return user


def writer(user: User = Depends(current_user)) -> User:
    if user.role == Role.viewer:
        raise HTTPException(status_code=403, detail="Только просмотр")
    return user


def admin_only(user: User = Depends(current_user)) -> User:
    if user.role != Role.admin:
        raise HTTPException(status_code=403, detail="Только администратор")
    return user
