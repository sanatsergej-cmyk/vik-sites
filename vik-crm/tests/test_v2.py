import json

import httpx
from sqlmodel import Session, select

from .conftest import csrf_from, login, make_user


def _boss(client):
    make_user("boss@example.com", "correct-horse-1", "admin")
    login(client, "boss@example.com", "correct-horse-1")
    return csrf_from(client, "/companies")


def _deal(client, t, service="pipeline-install"):
    client.post("/companies", data={"name": "ООО Тест", "csrf": t})
    r = client.post("/deals", data={"title": "Склад", "company_id": 1, "service": service, "csrf": t}, follow_redirects=False)
    assert r.headers["location"] == "/deals/1"


def test_priority_service_marked_and_unknown_service_dropped(client):
    t = _boss(client)
    _deal(client, t)
    assert "приоритет" in client.get("/deals/1").text
    client.post("/deals", data={"title": "Другое", "company_id": 1, "service": "hacked", "csrf": t})
    from app.db import get_engine
    from app.models import Deal

    with Session(get_engine()) as s:
        assert s.get(Deal, 2).service == ""


def test_followup_task_created_once_and_closed_on_win(client):
    t = _boss(client)
    _deal(client, t)
    for _ in range(2):
        client.post("/deals/1/stage", data={"stage": "proposal_sent", "csrf": t})
    from app.db import get_engine
    from app.models import Task

    with Session(get_engine()) as s:
        tasks = s.exec(select(Task)).all()
        assert len(tasks) == 1 and tasks[0].auto and "Дожим" in tasks[0].title
    client.post("/deals/1/stage", data={"stage": "won", "csrf": t})
    with Session(get_engine()) as s:
        assert all(x.done for x in s.exec(select(Task)).all())


def test_board_move_and_pages(client):
    t = _boss(client)
    _deal(client, t)
    assert client.post("/deals/1/move", data={"stage": "negotiation", "csrf": t}).json() == {"ok": True, "stage": "negotiation"}
    assert client.post("/deals/1/move", data={"stage": "nope", "csrf": t}).status_code == 400
    assert client.post("/deals/1/move", data={"stage": "new"}).status_code == 403
    assert client.post("/deals/1/tasks", data={"title": "Позвонить", "days": "0", "csrf": t}, follow_redirects=False).status_code == 303
    for path in ("/", "/deals", "/deals?view=list", "/tasks", "/deals/1"):
        assert client.get(path).status_code == 200, path
    r = client.post("/tasks/1/done", data={"csrf": t, "next": "//evil.example"}, follow_redirects=False)
    assert r.headers["location"] == "/tasks"


def test_events_api_matches_dedupes_and_creates(client, monkeypatch):
    monkeypatch.setenv("EVENTS_API_TOKEN", "ev-token")
    t = _boss(client)
    _deal(client, t)
    client.post("/companies/1/contacts", data={"name": "Иван", "phone": "+7 (999) 111-22-33", "telegram": "@Ivan", "csrf": t})
    h = {"X-Events-Token": "ev-token"}
    call = {"channel": "phone", "kind": "call", "direction": "in", "phone": "89991112233", "text": "Звонок", "external_id": "c-1", "duration_sec": 95}
    assert client.post("/api/events", json=call, headers={"X-Events-Token": "bad"}).status_code == 401
    r = client.post("/api/events", json=call, headers=h)
    assert r.status_code == 201 and r.json() == {"deal_id": 1, "created": False, "duplicate": False}
    assert client.post("/api/events", json=call, headers=h).json()["duplicate"] is True
    tg = {"channel": "telegram", "direction": "in", "telegram": "ivan", "text": "Добрый день"}
    assert client.post("/api/events", json=tg, headers=h).json()["deal_id"] == 1
    new = {"channel": "email", "kind": "email", "direction": "in", "email": "new@firm.ru", "text": "Нужна смета"}
    r = client.post("/api/events", json=new, headers=h).json()
    assert r["created"] is True and r["deal_id"] == 2
    assert client.post("/api/events", json={"channel": "email", "text": "x"}, headers=h).status_code == 422
    assert "Запись" not in client.get("/deals/2").text
    assert "входящее" in client.get("/deals/1").text


def test_notify_has_no_personal_data(client, monkeypatch):
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://crm.example.ru")
    from app import notify as n

    assert n.notify("Тест", transport=httpx.MockTransport(handler)) is True
    assert sent[0] == {"chat_id": "42", "text": "Тест"}
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
    assert n.notify("Тест") is False


def test_lead_notification_text_is_depersonalized(client, monkeypatch):
    texts = []
    monkeypatch.setattr("app.crm.notify", lambda text, **kw: texts.append(text) or True)
    r = client.post(
        "/api/leads",
        json={"name": "Иван Петров", "contact": "+79990000000", "task": "Теплосеть", "direction": "teplosnabzhenie"},
        headers={"X-Lead-Token": "lead-token-123"},
    )
    assert r.status_code == 201
    assert texts and "Иван" not in texts[0] and "79990000000" not in texts[0] and "№1" in texts[0]


def test_obsidian_export_links(client, tmp_path):
    t = _boss(client)
    _deal(client, t)
    client.post("/deals/1/note", data={"body": "Договорились о выезде", "kind": "call", "csrf": t})
    from app.db import get_engine
    from app.obsidian import export_vault

    with Session(get_engine()) as s:
        count = export_vault(s, tmp_path / "vault")
    assert count >= 3
    deal_file = next((tmp_path / "vault" / "Сделки").glob("*.md")).read_text(encoding="utf-8")
    assert "[[ООО Тест (1)]]" in deal_file and "priority: true" in deal_file and "Договорились о выезде" in deal_file
    client_file = next((tmp_path / "vault" / "Клиенты").glob("*.md")).read_text(encoding="utf-8")
    assert "[[Сделка 1 — Склад]]" in client_file


def test_fgis_watch_detects_new_quarter(tmp_path):
    from app.fgis_watch import detect_new, fetch_periods

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["priceZoneId"] == "127"
        return httpx.Response(200, json=handler.data)

    handler.data = [{"id": 420, "name": "2 квартал 2026 г."}, {"id": 427, "name": "3 квартал 2026 г."}]
    state = tmp_path / "state.json"
    transport = httpx.MockTransport(handler)
    assert detect_new(state, fetch_periods(transport=transport)) == []
    assert detect_new(state, fetch_periods(transport=transport)) == []
    handler.data = handler.data + [{"id": 431, "name": "4 квартал 2026 г."}]
    assert detect_new(state, fetch_periods(transport=transport)) == [{"id": 431, "name": "4 квартал 2026 г."}]
    assert detect_new(state, fetch_periods(transport=transport)) == []
    handler.data = {"oops": 1}
    try:
        fetch_periods(transport=transport)
        assert False
    except ValueError:
        pass
