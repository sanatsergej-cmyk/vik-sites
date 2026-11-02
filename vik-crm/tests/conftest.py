import re

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/crm.db")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "files"))
    monkeypatch.setenv("HTTPS_ONLY", "0")
    monkeypatch.setenv("LEAD_API_TOKEN", "lead-token-123")
    from app import db

    db.reset_engine()
    yield
    db.reset_engine()


@pytest.fixture()
def client(env):
    from app.main import create_app

    return TestClient(create_app())


def make_user(email, password, role):
    from app.db import get_engine
    from app.models import Role, User
    from app.security import hash_password

    with Session(get_engine()) as s:
        s.add(User(email=email, name=email, password_hash=hash_password(password), role=Role(role)))
        s.commit()


def csrf_from(client, path="/login"):
    html = client.get(path).text
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def login(client, email, password):
    token = csrf_from(client)
    return client.post("/login", data={"email": email, "password": password, "csrf": token}, follow_redirects=False)
