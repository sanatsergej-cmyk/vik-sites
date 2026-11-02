import logging
import os
from typing import Optional

import httpx

log = logging.getLogger("vik.notify")


def notify(text: str, transport: Optional[httpx.BaseTransport] = None) -> bool:
    """Отправляет уведомление сотруднику в Telegram. Только обезличенный текст: без имён, телефонов и файлов."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False
    try:
        with httpx.Client(timeout=10, transport=transport) as client:
            r = client.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": text})
        return r.status_code == 200
    except httpx.HTTPError as e:
        log.warning("telegram notify failed: %s", type(e).__name__)
        return False


def deal_link(deal_id: int) -> str:
    base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    return f"{base}/deals/{deal_id}" if base else f"/deals/{deal_id}"
