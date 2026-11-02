from pathlib import Path
from typing import Iterator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().database_url
        args = {}
        if url.startswith("sqlite"):
            args["check_same_thread"] = False
            args["timeout"] = 30
            path = url.split("sqlite:///", 1)[-1]
            if path and path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, connect_args=args)
        if url.startswith("sqlite"):
            event.listen(_engine, "connect", _sqlite_pragmas)
    return _engine


def _sqlite_pragmas(dbapi_conn, _record) -> None:
    """WAL: чтение не блокируется записью, онлайн-бэкап не останавливает работу."""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=30000")
    cur.close()


def reset_engine() -> None:
    global _engine
    _engine = None


def init_db() -> None:
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
