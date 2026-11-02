import logging
import os
import re
import time
from typing import Any, Callable, Dict, Optional, Tuple

import httpx
from sqlmodel import Session

from .db import get_engine
from .models import AuditLog, Deal, Estimate, Interaction, now
from .numwords import normalize
from .pricing import compute
from .stt import SttUnavailable, transcribe

log = logging.getLogger("vik.bot")
NUM = r"(-?\d+(?:[.,]\d+)?)"
HELP = (
    "Команды:\n"
    "смета 12 — выбрать расчёт\n"
    "итог — показать суммы\n"
    "мтр 1.25 / смр 1.4 — задать наценку\n"
    "+5% работам / +5% материалам / +5% всему — поднять наценку\n"
    "ндс 22 / лимит 8 — НДС и лимитированные затраты"
)
LIMITS = {"k_mtr": (0.5, 5.0), "k_smr": (0.5, 5.0), "vat": (0.0, 1.0), "lim_percent": (0.0, 50.0)}


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def allowed_chats() -> set:
    raw = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS") or os.getenv("TELEGRAM_CHAT_ID", "")
    return {x.strip() for x in raw.split(",") if x.strip()}


def _summary(est: Estimate) -> str:
    p = compute(est.base_mtr, est.base_smr, est.k_mtr, est.k_smr, est.vat, est.lim_percent)
    return (
        f"Расчёт №{est.id}: {est.title}\n"
        f"Наценка МТР ×{est.k_mtr:g}, СМР ×{est.k_smr:g}, НДС {est.vat * 100:g}%, лимитированные {est.lim_percent:g}%\n"
        f"ИТОГО {p.subtotal:,.2f} ₽, общая стоимость {p.total:,.2f} ₽".replace(",", " ")
    )


def _apply(est: Estimate, field: str, value: float) -> Optional[str]:
    lo, hi = LIMITS[field]
    if not lo <= value <= hi:
        return f"Значение вне допустимых пределов ({lo:g}–{hi:g})."
    setattr(est, field, round(value, 6))
    return None


def handle_text(session: Session, chat_id: str, text: str, state: Dict[str, Any]) -> str:
    t = text.strip().lower().replace("ё", "е").rstrip(".!,;?")
    if t in ("/start", "/help", "помощь"):
        return HELP
    m = re.fullmatch(r"/?смета\s+(\d+)", t)
    if m:
        est = session.get(Estimate, int(m.group(1)))
        if not est:
            return "Такого расчёта нет."
        state[chat_id] = est.id
        return _summary(est)
    est = session.get(Estimate, state[chat_id]) if chat_id in state else None
    if t in ("итог", "покажи", "показать"):
        return _summary(est) if est else "Сначала выберите расчёт: смета 12"
    change: Optional[Tuple[str, float, str]] = None
    m = re.fullmatch(rf"(мтр|смр|ндс|лимит)\s+{NUM}", t)
    if m:
        key = {"мтр": "k_mtr", "смр": "k_smr", "ндс": "vat", "лимит": "lim_percent"}[m.group(1)]
        val = _num(m.group(2))
        if key == "vat" and val > 1:
            val /= 100
        change = (key, val, f"{m.group(1)} = {m.group(2)}")
    else:
        m = re.fullmatch(rf"(?:добавь|прибавь|\+)?\s*{NUM}\s*%\s*(?:к\s+)?(работам|материалам|смр|мтр|всему|все)", t)
        if m:
            pct, target = _num(m.group(1)), m.group(2)
            if abs(pct) > 50:
                return "Слишком большая прибавка, максимум ±50%."
            fields = {"работам": ["k_smr"], "смр": ["k_smr"], "материалам": ["k_mtr"], "мтр": ["k_mtr"]}.get(target, ["k_mtr", "k_smr"])
            if not est:
                return "Сначала выберите расчёт: смета 12"
            for f in fields:
                err = _apply(est, f, getattr(est, f) * (1 + pct / 100))
                if err:
                    session.rollback()
                    return err
            change = None
            _record(session, est, f"{pct:+g}% к {target}")
            return _summary(est)
    if change:
        if not est:
            return "Сначала выберите расчёт: смета 12"
        err = _apply(est, change[0], change[1])
        if err:
            return err
        _record(session, est, change[2])
        return _summary(est)
    return "Не понял команду.\n" + HELP


def _record(session: Session, est: Estimate, what: str) -> None:
    est.updated_at = now()
    session.add(AuditLog(action=f"estimate.telegram: {what}", entity="estimate", entity_id=est.id))
    if session.get(Deal, est.deal_id):
        session.add(Interaction(deal_id=est.deal_id, kind="note", channel="telegram", body=f"Наценка изменена через Telegram: {what}"))
    session.commit()


def _send(client: httpx.Client, token: str, chat_id: str, text: str) -> None:
    client.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": text})


def _is_readonly(cmd: str) -> bool:
    return cmd in ("итог", "покажи", "показать") or re.fullmatch(r"/?смета\s+\d+", cmd) is not None


def _voice_to_text(client: httpx.Client, token: str, file_id: str, transcriber: Callable[[bytes], str]) -> str:
    path = client.get(f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id}).json()["result"]["file_path"]
    audio = client.get(f"https://api.telegram.org/file/bot{token}/{path}").content
    return transcriber(audio)


def process_update(
    client: httpx.Client, token: str, update: dict, state: Dict[str, Any], allow: set,
    transcriber: Optional[Callable[[bytes], str]] = None,
) -> None:
    msg = update.get("message") or {}
    chat_id = str((msg.get("chat") or {}).get("id", ""))
    if not chat_id or chat_id not in allow:
        return
    voice = msg.get("voice") or msg.get("audio")
    if voice:
        try:
            heard = _voice_to_text(client, token, voice["file_id"], transcriber or transcribe)
        except SttUnavailable:
            _send(client, token, chat_id, "Распознавание речи не настроено на сервере. Напишите текстом, например: +5% работам")
            return
        except (httpx.HTTPError, KeyError, ValueError):
            _send(client, token, chat_id, "Не удалось получить или распознать голосовое. Напишите текстом.")
            return
        cmd = normalize(heard)
        if not cmd:
            _send(client, token, chat_id, "Ничего не расслышал. Повторите или напишите текстом.")
            return
        if _is_readonly(cmd):
            with Session(get_engine()) as session:
                reply = handle_text(session, chat_id, cmd, state)
            _send(client, token, chat_id, f"Распознал: «{heard}»\n{reply}")
        else:
            state[f"pending:{chat_id}"] = cmd
            _send(client, token, chat_id, f"Распознал: «{heard}». Выполню: «{cmd}». Применить? Ответьте «да» или «нет».")
        return
    text = msg.get("text")
    if not text:
        return
    answer = text.strip().lower().rstrip(".!")
    pending = state.get(f"pending:{chat_id}")
    if pending and answer in ("да", "нет"):
        state.pop(f"pending:{chat_id}", None)
        if answer == "нет":
            _send(client, token, chat_id, "Отменено.")
            return
        text = pending
    with Session(get_engine()) as session:
        reply = handle_text(session, chat_id, text, state)
    _send(client, token, chat_id, reply)


def run(transport: Optional[httpx.BaseTransport] = None, once: bool = False, transcriber: Optional[Callable[[bytes], str]] = None) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    allow = allowed_chats()
    if not token or not allow:
        raise RuntimeError("Нужны TELEGRAM_BOT_TOKEN и TELEGRAM_ALLOWED_CHAT_IDS (или TELEGRAM_CHAT_ID)")
    state: Dict[str, Any] = {}
    offset = 0
    with httpx.Client(timeout=45, transport=transport) as client:
        while True:
            try:
                r = client.get(f"https://api.telegram.org/bot{token}/getUpdates", params={"timeout": 30, "offset": offset})
                for upd in r.json().get("result", []):
                    offset = upd["update_id"] + 1
                    process_update(client, token, upd, state, allow, transcriber)
            except (httpx.HTTPError, ValueError) as e:
                log.warning("bot poll failed: %s", type(e).__name__)
                if once:
                    return
                time.sleep(5)
            if once:
                return
