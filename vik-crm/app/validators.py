"""Проверки входных данных публичных заявок: контакт (телефон, email, Telegram) и содержимое файлов."""
import re

_EMAIL = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]{2,}$")
_TELEGRAM = re.compile(r"^@[A-Za-z0-9_]{5,32}$")
_PHONE_CHARS = re.compile(r"^\+?[\d\s()\-]{7,25}$")


def normalize_contact(value: str) -> str:
    """Возвращает очищенный контакт или ValueError. Принимает телефон (10-15 цифр), email или @username Telegram."""
    v = (value or "").strip()
    if "@" in v and not v.startswith("@"):
        if len(v) <= 200 and _EMAIL.match(v):
            return v.lower()
        raise ValueError("Проверьте email")
    if v.startswith("@"):
        if _TELEGRAM.match(v):
            return v
        raise ValueError("Проверьте имя пользователя Telegram")
    digits = re.sub(r"\D", "", v)
    if _PHONE_CHARS.match(v) and 10 <= len(digits) <= 15:
        return v
    raise ValueError("Укажите телефон, email или @username в Telegram")


_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ZIP = (b"PK\x03\x04", b"PK\x05\x06")
SIGNATURES = {
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".zip": _ZIP,
    ".docx": _ZIP,
    ".xlsx": _ZIP,
    ".doc": (_OLE,),
    ".xls": (_OLE,),
    ".dwg": (b"AC1",),
}


def content_matches(ext: str, head: bytes) -> bool:
    """Сверяет первые байты файла с заявленным расширением, чтобы под .pdf не прислали исполняемый файл."""
    ext = ext.lower()
    if ext == ".dxf":
        return head.startswith(b"AutoCAD Binary DXF") or (bool(head) and b"\x00" not in head)
    sigs = SIGNATURES.get(ext)
    return bool(sigs) and any(head.startswith(s) for s in sigs)
