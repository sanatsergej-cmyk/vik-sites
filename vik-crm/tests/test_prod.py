"""Проверки готовности к продакшену: cookie, CSRF, healthcheck, CORS/Origin, валидация, файлы, логи, бэкап."""
import logging
import sqlite3

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from tests.conftest import csrf_from, make_user

PROD_ORIGINS = "https://gold.vikmsk.ru,https://kp.vikmsk.ru,https://indigo.vikmsk.ru,https://vikmsk.ru"
H = {"Origin": "https://kp.vikmsk.ru"}
BASE = {"name": "Иван", "contact": "+7 (999) 000-00-00", "task": "Нужна теплосеть", "consent": "1"}


def _cookie(resp, name):
    for header in resp.headers.get_list("set-cookie"):
        if header.startswith(name + "="):
            return header.lower()
    raise AssertionError(f"нет cookie {name}")


@pytest.fixture()
def https_client(env, monkeypatch):
    monkeypatch.setenv("HTTPS_ONLY", "1")
    from app.main import create_app

    return TestClient(create_app(), base_url="https://testserver")


@pytest.fixture()
def pub(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_LEADS_ENABLED", "1")
    monkeypatch.setenv("PUBLIC_SITE_ORIGINS", PROD_ORIGINS)
    from app import public_api

    public_api._hits.clear()
    return client


def _deals():
    from app.db import get_engine
    from app.models import Deal

    with Session(get_engine()) as s:
        return s.exec(select(Deal)).all()


# ---------- секреты и cookie ----------
def test_secret_key_required(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "short")
    from app.config import get_settings

    with pytest.raises(RuntimeError):
        get_settings()


def test_session_cookie_secure_when_https_only(https_client):
    make_user("a@vik.ru", "password-123", "admin")
    token = csrf_from(https_client)
    r = https_client.post("/login", data={"email": "a@vik.ru", "password": "password-123", "csrf": token},
                          follow_redirects=False)
    assert r.status_code == 303
    c = _cookie(r, "vik_session")
    assert "secure" in c and "httponly" in c and "samesite=lax" in c
    assert r.headers["strict-transport-security"].startswith("max-age=")


def test_admin_cookie_secure_strict_and_throttled(https_client):
    make_user("root@vik.ru", "password-123", "admin")
    ok = https_client.post("/admin/login", data={"username": "root@vik.ru", "password": "password-123"},
                           follow_redirects=False)
    assert ok.status_code in (302, 303)
    c = _cookie(ok, "vik_admin")
    assert "secure" in c and "httponly" in c and "samesite=strict" in c

    from app import security

    security._failures.clear()
    for _ in range(5):
        bad = https_client.post("/admin/login", data={"username": "root@vik.ru", "password": "wrong-pass"},
                                follow_redirects=False)
        assert bad.status_code == 400
    blocked = https_client.post("/admin/login", data={"username": "root@vik.ru", "password": "password-123"},
                                follow_redirects=False)
    assert blocked.status_code == 400
    security._failures.clear()


def test_admin_requires_login(client):
    r = client.get("/admin/", follow_redirects=False)
    assert r.status_code in (302, 303) and "/admin/login" in r.headers["location"]


def test_every_html_post_route_has_csrf(client):
    from app.security import csrf_check

    missing = []
    for route in client.app.routes:
        methods = getattr(route, "methods", set()) or set()
        if "POST" not in methods or route.path.startswith("/api/"):
            continue
        deps = [d.call for d in route.dependant.dependencies]
        if csrf_check not in deps:
            missing.append(route.path)
    assert missing == []


# ---------- healthcheck ----------
def test_healthz_without_login(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert "set-cookie" not in r.headers


# ---------- Origin и CORS ----------
def test_public_closed_when_origins_empty(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_LEADS_ENABLED", "1")
    monkeypatch.setenv("PUBLIC_SITE_ORIGINS", "")
    assert client.post("/api/public/lead", data=BASE, headers=H).status_code == 403
    assert _deals() == []


@pytest.mark.parametrize("origin", PROD_ORIGINS.split(","))
def test_public_accepts_all_site_origins(pub, origin):
    r = pub.post("/api/public/lead", data=BASE, headers={"Origin": origin})
    assert r.status_code == 201
    assert r.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in r.headers


def test_public_rejects_foreign_origin_and_preflight(pub):
    evil = {"Origin": "https://evil.example"}
    r = pub.post("/api/public/lead", data=BASE, headers=evil)
    assert r.status_code == 403 and "access-control-allow-origin" not in r.headers
    pre = pub.options("/api/public/lead", headers={**evil, "Access-Control-Request-Method": "POST"})
    assert pre.status_code == 403 and "access-control-allow-origin" not in pre.headers
    ok = pub.options("/api/public/lead", headers={**H, "Access-Control-Request-Method": "POST"})
    assert ok.status_code == 204 and ok.headers["access-control-allow-origin"] == H["Origin"]
    assert _deals() == []


# ---------- валидация контакта ----------
@pytest.mark.parametrize("value,expected", [
    ("+7 (999) 000-00-00", "+7 (999) 000-00-00"),
    ("89990000000", "89990000000"),
    ("Ivan@Example.RU", "ivan@example.ru"),
    ("@vik_client", "@vik_client"),
])
def test_normalize_contact_ok(value, expected):
    from app.validators import normalize_contact

    assert normalize_contact(value) == expected


@pytest.mark.parametrize("value", ["12345", "привет мир", "ivan@", "a@b", "@ab", "+7 999 000 00 00 00 00 00", "<script>"])
def test_normalize_contact_bad(value):
    from app.validators import normalize_contact

    with pytest.raises(ValueError):
        normalize_contact(value)


def test_public_rejects_bad_contact(pub):
    assert pub.post("/api/public/lead", data={**BASE, "contact": "12345"}, headers=H).status_code == 422
    assert pub.post("/api/public/lead", data={**BASE, "contact": "ivan@mail"}, headers=H).status_code == 422
    assert _deals() == []


def test_token_api_rejects_bad_contact(client):
    payload = {"contact": "abc", "task": "Нужна теплосеть"}
    assert client.post("/api/leads", json=payload, headers={"X-Lead-Token": "lead-token-123"}).status_code == 422


# ---------- файлы ----------
def test_public_rejects_spoofed_file(pub, tmp_path):
    r = pub.post("/api/public/lead", data=BASE, headers=H,
                 files=[("files", ("tu.pdf", b"MZ\x90\x00binary", "application/pdf"))])
    assert r.status_code == 422
    assert _deals() == []
    assert not any((tmp_path / "files").glob("*")) if (tmp_path / "files").exists() else True


def test_public_accepts_real_types(pub):
    files = [
        ("files", ("plan.dwg", b"AC1032" + b"\x00" * 10, "application/octet-stream")),
        ("files", ("smeta.xlsx", b"PK\x03\x04rest", "application/octet-stream")),
        ("files", ("photo.jpg", b"\xff\xd8\xff\xe0data", "image/jpeg")),
        ("files", ("plan.dxf", b"0\nSECTION\n2\nHEADER\n", "application/dxf")),
    ]
    assert pub.post("/api/public/lead", data=BASE, headers=H, files=files).status_code == 201


def test_public_upload_size_limit(pub, monkeypatch, tmp_path):
    monkeypatch.setenv("PUBLIC_MAX_UPLOAD_MB", "1")
    big = b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10)
    r = pub.post("/api/public/lead", data=BASE, headers=H, files=[("files", ("big.pdf", big, "application/pdf"))])
    assert r.status_code == 413
    assert _deals() == []
    assert list((tmp_path / "files").glob("*")) == []


# ---------- логи без персональных данных ----------
def test_access_log_drops_query_string():
    from app.main import StripQueryFilter

    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                            ("1.2.3.4:5", "GET", "/search?q=%2B79990000000", "1.1", 200), None)
    StripQueryFilter().filter(rec)
    assert "7999" not in rec.getMessage() and "/search?" in rec.getMessage()


def test_lead_does_not_log_personal_data(pub, caplog):
    caplog.set_level(logging.DEBUG)
    assert pub.post("/api/public/lead", data=BASE, headers=H).status_code == 201
    assert "Иван" not in caplog.text and "999" not in caplog.text


# ---------- бэкап ----------
def test_backup_sqlite_and_files(client, tmp_path):
    from app.backup import run_backup

    (tmp_path / "files").mkdir(exist_ok=True)
    (tmp_path / "files" / "a.pdf").write_bytes(b"%PDF-1.4")
    make_user("b@vik.ru", "password-123", "manager")
    dest = tmp_path / "backups"
    dest.mkdir()
    (dest / "crm-20000101-000000.db").write_bytes(b"old")
    (dest / "files-20000101-000000.tar.gz").write_bytes(b"old")
    made = run_backup(dest, keep=1)
    assert len(made) == 2 and all(p.exists() for p in made)
    assert sorted(x.name for x in dest.iterdir()) == sorted(p.name for p in made)  # без -wal/-shm и старых копий
    assert not (dest / "crm-20000101-000000.db").exists() and not (dest / "files-20000101-000000.tar.gz").exists()
    with sqlite3.connect(str(made[0])) as con:
        assert con.execute("select email from user").fetchone()[0] == "b@vik.ru"
    import tarfile

    with tarfile.open(made[1]) as tar:
        assert "files/a.pdf" in tar.getnames()


def test_backup_refuses_non_sqlite(monkeypatch):
    from app.backup import sqlite_path

    with pytest.raises(RuntimeError):
        sqlite_path("postgresql+psycopg://crm:x@db/crm")
