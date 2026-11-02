import re

import pytest
from sqlmodel import Session, select

from .conftest import csrf_from, login, make_user

FULL = dict(contact_name="Анна", object_name="Склад, Домодедово", sender="Виталий", company="ООО «ВиК»", phone="+7 000 000-00-00", email="info@example.ru")
FORBIDDEN = ["гаранти", "скидк", "акци", "срочно", "потенциал", "собственный парк", "лучш", "№1", "быстрее всех"]


def _all():
    from app.letters import KINDS, SERVICE_TEXT

    for sid in SERVICE_TEXT:
        for kind in KINDS:
            yield sid, kind


@pytest.mark.parametrize("sid,kind", list(_all()))
def test_every_template_is_clean(sid, kind):
    from app.letters import build_letter

    letter = build_letter(kind, sid, reason="вы объявили закупку на монтаж кабельных линий", total=1234567.4, kp_date="30.10.2026", **FULL)
    text = (letter.subject + "\n" + letter.body)
    assert "[УТОЧНИТЬ" not in text and letter.warnings == []
    assert "Здравствуйте, Анна!" in text and "Склад, Домодедово" in text and text.rstrip().endswith("info@example.ru")
    low = text.lower()
    assert not [w for w in FORBIDDEN if w in low]
    if kind == "reply_kp":
        assert "1 234 567" in text and "во вложении" in text
    if kind == "offer":
        assert "больше не будем писать" in text


def test_priority_services_specifics():
    from app.letters import build_letter

    assert "траншеи" in build_letter("request_docs", "earthworks", **FULL).body
    assert "ТУ на теплоснабжение" in build_letter("request_docs", "itp-design", **FULL).body
    assert "сечение кабеля" in build_letter("request_docs", "cable-install", **FULL).body
    assert "диаметры" in build_letter("request_docs", "pipeline-install", **FULL).body
    assert "удалённо" in build_letter("reply_kp", "itp-design", **FULL).body


def test_offer_needs_reason_and_missing_facts_are_flagged():
    from app.letters import build_letter

    with pytest.raises(ValueError):
        build_letter("offer", "earthworks", **FULL)
    with pytest.raises(ValueError):
        build_letter("unknown", "earthworks", **FULL)
    letter = build_letter("request_docs", "earthworks", object_name="Склад")
    assert set(letter.warnings) == {"имя адресата", "ваше имя", "телефон"}
    assert letter.body.count("[УТОЧНИТЬ") == 3


def _setup(client):
    make_user("boss@example.com", "correct-horse-1", "admin")
    login(client, "boss@example.com", "correct-horse-1")
    t = csrf_from(client, "/companies")
    client.post("/quick", data={"company": "ООО Север", "contact_name": "Анна", "email": "anna@north.ru", "service": "cable-install", "title": "Кабель, Подольск", "csrf": t})
    return t


def test_letter_pages_and_logging(client):
    t = _setup(client)
    page = client.get("/deals/1/letter?kind=request_docs")
    assert page.status_code == 200 and "сечение кабеля" in page.text and "Здравствуйте, Анна!" in page.text
    assert "Нужно заполнить" in page.text
    assert "нужен конкретный повод" in client.get("/deals/1/letter?kind=offer").text
    ok = client.get("/deals/1/letter?kind=offer&reason=вы+объявили+закупку")
    assert "вы объявили закупку" in ok.text and "ст. 18 38-ФЗ" in ok.text
    for path in ("/deals/1/letter?kind=followup", "/deals/1/letter?kind=reply_kp&service=smr", "/deals/1/letter?kind=bogus", "/deals/1"):
        assert client.get(path).status_code == 200, path

    bad = client.post("/deals/1/letter/sent", data={"kind": "reply_kp", "subject": "Тема", "body": "Привет, [УТОЧНИТЬ: телефон]", "csrf": t})
    assert bad.status_code == 400
    client.post("/deals/1/letter/sent", data={"kind": "reply_kp", "subject": "КП", "body": "Текст письма", "to_email": "anna@north.ru", "csrf": t})
    from app.db import get_engine
    from app.models import DealStage, Deal, Interaction, Task

    with Session(get_engine()) as s:
        assert s.get(Deal, 1).stage == DealStage.proposal_sent
        mails = [i for i in s.exec(select(Interaction)).all() if i.channel == "email" and i.direction == "out"]
        assert len(mails) == 1 and "Тема: КП" in mails[0].body and "anna@north.ru" in mails[0].body
        assert any("Дожим" in x.title for x in s.exec(select(Task)).all())
    assert client.post("/deals/1/letter/sent", data={"kind": "reply_kp", "subject": "x", "body": "y"}).status_code == 403


def test_stop_list_blocks_offer(client):
    t = _setup(client)
    client.post("/contacts/1/dnc", data={"value": "1", "csrf": t})
    page = client.get("/deals/1/letter?kind=offer&reason=повод").text
    assert "стоп-листе" in page
    assert "Не писать" not in client.get("/companies/1").text or "Снять" in client.get("/companies/1").text
    client.post("/contacts/1/dnc", data={"value": "0", "csrf": t})
    assert "стоп-листе" not in client.get("/deals/1/letter?kind=offer&reason=повод").text
