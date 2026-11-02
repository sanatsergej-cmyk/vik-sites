import json
from pathlib import Path
from typing import List, Optional

import httpx

PERIODS_URL = "https://fgiscs.minstroyrf.ru/api/EstimatedPrice/Periods"


def fetch_periods(zone_id: int = 127, transport: Optional[httpx.BaseTransport] = None) -> List[dict]:
    with httpx.Client(timeout=30, transport=transport) as client:
        r = client.get(PERIODS_URL, params={"priceZoneId": zone_id})
        r.raise_for_status()
        data = r.json()
    if not isinstance(data, list) or not all(isinstance(x, dict) and "id" in x and "name" in x for x in data):
        raise ValueError("Неожиданный формат ответа ФГИС ЦС: нужен список объектов с id и name")
    return data


def detect_new(state_path: Path, periods: List[dict]) -> List[dict]:
    """Первый запуск сохраняет базу и ничего не сообщает. Дальше возвращает периоды, которых раньше не было."""
    state_path = Path(state_path)
    current = {str(p["id"]): p["name"] for p in periods}
    if not state_path.exists():
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(current, ensure_ascii=False, indent=1), encoding="utf-8")
        return []
    known = json.loads(state_path.read_text(encoding="utf-8"))
    new = [{"id": int(i), "name": n} for i, n in current.items() if i not in known]
    if new:
        state_path.write_text(json.dumps({**known, **current}, ensure_ascii=False, indent=1), encoding="utf-8")
    return new
