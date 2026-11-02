from io import BytesIO

from openpyxl import load_workbook
from sqlmodel import Session, select

from .conftest import csrf_from, login, make_user


def test_requires_login(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert client.get("/login").headers["x-robots-tag"] == "noindex, nofollow"


def test_login_ok_and_wrong_password(client):
    make_user("boss@example.com", "correct-horse-1", "admin")
    assert login(client, "boss@example.com", "wrong-password").status_code == 401
    assert login(client, "boss@example.com", "correct-horse-1").status_code == 303
    assert client.get("/").status_code == 200


def test_csrf_required(client):
    make_user("boss@example.com", "correct-horse-1", "admin")
    login(client, "boss@example.com", "correct-horse-1")
    assert client.post("/companies", data={"name": "ООО Тест"}).status_code == 403


def _setup_deal(client):
    make_user("boss@example.com", "correct-horse-1", "admin")
    login(client, "boss@example.com", "correct-horse-1")
    t = csrf_from(client, "/companies")
    r = client.post("/companies", data={"name": "ООО Тест", "csrf": t}, follow_redirects=False)
    assert r.status_code == 303
    r = client.post("/deals", data={"title": "Склад", "company_id": 1, "csrf": t}, follow_redirects=False)
    assert r.headers["location"] == "/deals/1"
    return t


def test_estimate_and_kp(client):
    t = _setup_deal(client)
    r = client.post("/deals/1/estimates", data={"title": "Расчёт 1", "csrf": t}, follow_redirects=False)
    assert r.headers["location"] == "/estimates/1"
    client.post(
        "/estimates/1",
        data={"title": "Расчёт 1", "status": "final", "base_mtr": "1 000", "base_smr": "1000,00", "k_mtr": "1.2",
              "k_smr": "1.356", "vat": "0.22", "lim_percent": "8", "csrf": t},
    )
    r = client.get("/estimates/1/kp.xlsx")
    assert r.status_code == 200
    ws = load_workbook(BytesIO(r.content))["КП"]
    values = {row[0].value: row[1].value for row in ws.iter_rows() if row[0].value}
    assert values["Общая стоимость"] == 3367.79
    assert "ВНУТР" not in load_workbook(BytesIO(r.content)).sheetnames
    internal = client.get("/estimates/1/kp-internal.xlsx")
    assert "ВНУТР" in load_workbook(BytesIO(internal.content)).sheetnames


def test_viewer_is_read_only_and_not_admin(client):
    _setup_deal(client)
    make_user("viewer@example.com", "viewer-pass-123", "viewer")
    client.post("/logout", data={"csrf": csrf_from(client, "/companies")})
    login(client, "viewer@example.com", "viewer-pass-123")
    t = csrf_from(client, "/companies")
    assert client.post("/companies", data={"name": "X", "csrf": t}).status_code == 403
    assert client.get("/estimates/1/kp-internal.xlsx").status_code in (403, 404)


def test_upload_rules(client):
    t = _setup_deal(client)
    bad = client.post("/deals/1/files", data={"csrf": t}, files={"file": ("virus.exe", b"MZ")})
    assert bad.status_code == 400
    ok = client.post("/deals/1/files", data={"csrf": t}, files={"file": ("tu.pdf", b"%PDF-1.4 test")}, follow_redirects=False)
    assert ok.status_code == 303
    dl = client.get("/files/1")
    assert dl.status_code == 200 and dl.content.startswith(b"%PDF")


def test_lead_api(client):
    payload = {"name": "Иван", "contact": "+79990000000", "task": "Нужна теплосеть", "direction": "teplosnabzhenie"}
    assert client.post("/api/leads", json=payload, headers={"X-Lead-Token": "nope"}).status_code == 401
    r = client.post("/api/leads", json=payload, headers={"X-Lead-Token": "lead-token-123"})
    assert r.status_code == 201
    from app.db import get_engine
    from app.models import Deal

    with Session(get_engine()) as s:
        deal = s.exec(select(Deal)).first()
        assert deal.source == "site" and deal.direction == "teplosnabzhenie"


def test_pages_render(client):
    t = _setup_deal(client)
    client.post("/suppliers", data={"name": "Ридан", "email": "sales@example.com", "csrf": t})
    client.post("/deals/1/estimates", data={"title": "Расчёт 1", "csrf": t})
    client.post("/deals/1/supplier-requests", data={"supplier_id": 1, "position": "Насос Wilo", "csrf": t})
    client.post("/deals/1/note", data={"body": "Позвонил", "kind": "call", "csrf": t})
    for path in ("/", "/companies", "/companies/1", "/deals", "/deals?stage=new", "/deals/1", "/estimates/1", "/suppliers"):
        r = client.get(path)
        assert r.status_code == 200, path
    deal_page = client.get("/deals/1").text
    assert "Это письмо сформировано автоматически" in deal_page
    assert client.get("/admin/", follow_redirects=False).status_code in (302, 303, 307)
