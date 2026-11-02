import pytest
from sqlmodel import Session, select


@pytest.fixture()
def pub(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_LEADS_ENABLED", "1")
    monkeypatch.setenv("PUBLIC_SITE_ORIGINS", "https://site.example")
    return client


H = {"Origin": "https://site.example"}
BASE = {"name": "Иван", "contact": "+79990000000", "task": "Нужна теплосеть", "direction": "teplosnabzhenie",
        "service": "pipeline-install", "consent": "1", "source": "consultant", "transcript": "Клиент: привет"}


def test_disabled_by_default(client):
    assert client.post("/api/public/lead", data=BASE).status_code == 404


def test_validations(pub):
    assert pub.post("/api/public/lead", data=BASE).status_code == 403
    assert pub.post("/api/public/lead", data={**BASE, "consent": ""}, headers=H).status_code == 422
    assert pub.post("/api/public/lead", data={**BASE, "contact": "ab"}, headers=H).status_code == 422
    r = pub.post("/api/public/lead", data={**BASE, "website": "http://spam"}, headers=H)
    assert r.status_code == 201
    from app.db import get_engine
    from app.models import Deal

    with Session(get_engine()) as s:
        assert s.exec(select(Deal)).all() == []


def test_success_files_and_depersonalized_notice(pub, monkeypatch):
    texts = []
    monkeypatch.setattr("app.crm.notify", lambda text, **kw: texts.append(text) or True)
    r = pub.post("/api/public/lead", data=BASE, headers=H, files=[("files", ("tu.pdf", b"%PDF-1.4", "application/pdf"))])
    assert r.status_code == 201 and r.json() == {"ok": True}
    from app.db import get_engine
    from app.models import Deal, FileRecord, Interaction, Task

    with Session(get_engine()) as s:
        deal = s.exec(select(Deal)).one()
        assert deal.source == "site" and deal.service == "pipeline-install"
        body = " ".join(i.body for i in s.exec(select(Interaction)).all())
        assert "Согласие на обработку" in body and "Диалог с консультантом" in body and "версия текста: draft" in body
        assert s.exec(select(FileRecord)).one().filename == "tu.pdf"
        assert any("Ответить на заявку" in t.title for t in s.exec(select(Task)).all())
    assert texts and "Иван" not in texts[0] and "7999" not in texts[0]


def test_bad_files_and_rate_limit(pub, monkeypatch):
    bad = pub.post("/api/public/lead", data=BASE, headers=H, files=[("files", ("a.exe", b"MZ", "application/octet-stream"))])
    assert bad.status_code == 422
    many = [("files", (f"f{i}.pdf", b"x", "application/pdf")) for i in range(6)]
    assert pub.post("/api/public/lead", data=BASE, headers=H, files=many).status_code == 422
    monkeypatch.setenv("PUBLIC_RATE_LIMIT_PER_HOUR", "2")
    from app import public_api

    public_api._hits.clear()
    codes = [pub.post("/api/public/lead", data=BASE, headers=H).status_code for _ in range(3)]
    assert codes == [201, 201, 429]
