"""Резервная копия SQLite (онлайн, через backup API) и папки с файлами заявок."""
import os
import sqlite3
import tarfile
from datetime import datetime
from pathlib import Path
from typing import List

from .config import get_settings


def sqlite_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise RuntimeError("Бэкап командой backup только для SQLite. Для PostgreSQL используйте pg_dump.")
    path = database_url.split("sqlite:///", 1)[1]
    if not path or path == ":memory:":
        raise RuntimeError("База в памяти, бэкапить нечего")
    return Path(path)


def _rotate(dest: Path, pattern: str, keep: int) -> None:
    for old in sorted(dest.glob(pattern))[:-keep] if keep > 0 else []:
        old.unlink()


def run_backup(dest: Path, keep: int = 7) -> List[Path]:
    """Делает crm-ГГГГММДД-ЧЧММСС.db (с проверкой целостности) и files-….tar.gz, хранит последние keep штук."""
    s = get_settings()
    src = sqlite_path(s.database_url)
    if not src.is_file():
        raise RuntimeError(f"Файл базы не найден: {src}")
    dest.mkdir(parents=True, exist_ok=True)
    os.chmod(dest, 0o700)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    db_out = dest / f"crm-{ts}.db"
    source, target = sqlite3.connect(str(src)), sqlite3.connect(str(db_out))
    try:
        source.backup(target)
        target.execute("PRAGMA journal_mode=DELETE")  # копия одним файлом, без -wal/-shm
        ok = target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        target.close()
        source.close()
    for suffix in ("-wal", "-shm"):  # копия уже в режиме DELETE и закрыта; старый SQLite на macOS оставляет пустой -shm
        Path(f"{db_out}{suffix}").unlink(missing_ok=True)
    if not ok:
        db_out.unlink(missing_ok=True)
        raise RuntimeError("Проверка целостности копии не прошла")
    os.chmod(db_out, 0o600)
    made = [db_out]
    files_out = dest / f"files-{ts}.tar.gz"
    with tarfile.open(files_out, "w:gz") as tar:
        if s.storage_dir.is_dir():
            tar.add(str(s.storage_dir), arcname="files")
    os.chmod(files_out, 0o600)
    made.append(files_out)
    _rotate(dest, "crm-*.db", keep)
    _rotate(dest, "files-*.tar.gz", keep)
    return made
