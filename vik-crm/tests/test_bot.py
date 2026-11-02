import json

import httpx
from sqlmodel import Session

from .conftest import csrf_from, login, make_user


def _estimate(client):
    make_user("boss@example.com", "correct-horse-1", "admin")
    login(client, "boss@example.com", "correct-horse-1")
    t = csrf_from(client, "/companies")
    client.post("/companies", data={"name": "ООО Тест", "csrf": t})
    client.post("/deals", data={"title": "Склад", "company_id": 1, "csrf": t})
    client.post("/deals/1/estimates", data={"title": "Расчёт 1", "csrf": t})
    client.post("/estimates/1", data={"title": "Расчёт 1", "status": "draft", "base_mtr": "1000", "base_smr": "1000",
                                      "k_mtr": "1.2", "k_smr": "1.356", "vat": "0.22", "lim_percent": "0", "csrf": t})


def test_commands(client):
    _estimate(client)
    from app.bot import handle_text
    from app.db import get_engine
    from app.models import Estimate

    state = {}
    with Session(get_engine()) as s:
        assert "выберите расчёт" in handle_text(s, "1", "+5% работам", state)
        assert "Расчёт №1" in handle_text(s, "1", "смета 1", state)
        out = handle_text(s, "1", "добавь 5% к работам", state)
        assert "СМР ×1.4238" in out
        assert "МТР ×1.2" in handle_text(s, "1", "мтр 1,2", state)
        assert "СМР ×1.5" in handle_text(s, "1", "смр 1.5", state)
        assert "НДС 22%" in handle_text(s, "1", "ндс 22", state)
        assert "вне допустимых" in handle_text(s, "1", "смр 9", state)
        assert "Слишком большая" in handle_text(s, "1", "+80% всему", state)
        assert "Не понял" in handle_text(s, "1", "сделай красиво", state)
        assert s.get(Estimate, 1).k_smr == 1.5
    assert "через Telegram" in client.get("/deals/1").text


def test_polling_authorized_and_voice(client, monkeypatch):
    _estimate(client)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/getUpdates"):
            return httpx.Response(200, json={"result": [
                {"update_id": 1, "message": {"chat": {"id": 42}, "text": "смета 1"}},
                {"update_id": 2, "message": {"chat": {"id": 999}, "text": "смр 4"}},
                {"update_id": 3, "message": {"chat": {"id": 42}, "voice": {"file_id": "x"}}},
                {"update_id": 4, "message": {"chat": {"id": 42}, "text": "мтр 1.25"}},
            ]})
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    from app import bot

    bot.run(transport=httpx.MockTransport(handler), once=True)
    assert [m["chat_id"] for m in sent] == ["42", "42", "42"]
    assert "Не удалось получить" in sent[1]["text"]
    assert "МТР ×1.25" in sent[2]["text"]


def _voice_handler(sent, updates):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/getUpdates"):
            return httpx.Response(200, json={"result": updates})
        if path.endswith("/getFile"):
            return httpx.Response(200, json={"result": {"file_path": "voice/1.oga"}})
        if "/file/bot" in path:
            return httpx.Response(200, content=b"OGGDATA")
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    return handler


def test_voice_requires_confirmation(client, monkeypatch):
    _estimate(client)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    sent = []
    phrases = iter(["Смета один", "Плюс пять процентов работам", "Плюс десять процентов материалам"])
    updates = [
        {"update_id": 1, "message": {"chat": {"id": 42}, "voice": {"file_id": "a"}}},
        {"update_id": 2, "message": {"chat": {"id": 42}, "voice": {"file_id": "b"}}},
        {"update_id": 3, "message": {"chat": {"id": 42}, "text": "нет"}},
        {"update_id": 4, "message": {"chat": {"id": 42}, "voice": {"file_id": "c"}}},
        {"update_id": 5, "message": {"chat": {"id": 42}, "text": "да"}},
    ]
    from app import bot
    from app.db import get_engine
    from app.models import Estimate

    bot.run(transport=httpx.MockTransport(_voice_handler(sent, updates)), once=True, transcriber=lambda audio: next(phrases))
    texts = [m["text"] for m in sent]
    assert "Расчёт №1" in texts[0]
    assert "Применить?" in texts[1] and "+ 5 % работам" in texts[1]
    assert texts[2] == "Отменено."
    assert "Применить?" in texts[3]
    assert "МТР ×1.32" in texts[4]
    with Session(get_engine()) as s:
        e = s.get(Estimate, 1)
        assert e.k_smr == 1.356 and e.k_mtr == 1.32


def test_voice_without_stt_installed(client, monkeypatch):
    _estimate(client)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "42")
    sent = []
    from app import bot

    updates = [{"update_id": 1, "message": {"chat": {"id": 42}, "voice": {"file_id": "a"}}}]
    bot.run(transport=httpx.MockTransport(_voice_handler(sent, updates)), once=True)
    assert "не настроено" in sent[0]["text"]
