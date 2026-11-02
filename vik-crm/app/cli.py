import argparse
import getpass
import os
import sys
from pathlib import Path

from sqlmodel import Session, select

from .db import get_engine, init_db
from .models import Role, User
from .crm import due_task_notifications
from .fgis_watch import detect_new, fetch_periods
from .notify import notify
from .obsidian import export_vault
from .security import hash_password


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    create = sub.add_parser("create-user", help="создать пользователя (пароль вводится интерактивно)")
    create.add_argument("email")
    create.add_argument("--name", default="")
    create.add_argument("--role", choices=[r.value for r in Role], default="manager")
    sub.add_parser("notify-due", help="уведомить в Telegram о наступивших задачах (запускать по cron)")
    obs = sub.add_parser("export-obsidian", help="выгрузить клиентов и сделки в markdown для Obsidian")
    obs.add_argument("out_dir")
    sub.add_parser("run-bot", help="запустить Telegram-бота пересчёта наценок (long polling)")
    fg = sub.add_parser("check-fgis", help="проверить, не вышел ли новый квартал в ФГИС ЦС (запускать по cron)")
    fg.add_argument("--zone", type=int, default=127)
    fg.add_argument("--state", default="./data/fgis_periods.json")
    bk = sub.add_parser("backup", help="резервная копия SQLite и файлов (запускать по cron, см. scripts/backup.sh)")
    bk.add_argument("--out", default=os.getenv("BACKUP_DIR", "./data/backups"))
    bk.add_argument("--keep", type=int, default=int(os.getenv("BACKUP_KEEP", "7")))
    args = parser.parse_args()

    init_db()
    if args.cmd == "backup":
        from .backup import run_backup

        try:
            for path in run_backup(Path(args.out), keep=args.keep):
                print(path)
        except RuntimeError as e:
            print(e, file=sys.stderr)
            return 1
        return 0
    if args.cmd == "run-bot":
        from .bot import run

        run()
        return 0
    if args.cmd == "notify-due":
        with Session(get_engine()) as s:
            print(f"Отправлено уведомлений: {due_task_notifications(s)}")
        return 0
    if args.cmd == "export-obsidian":
        with Session(get_engine()) as s:
            print(f"Файлов: {export_vault(s, Path(args.out_dir))}")
        return 0
    if args.cmd == "check-fgis":
        new = detect_new(Path(args.state), fetch_periods(args.zone))
        for p in new:
            print(f"Новый период ФГИС ЦС: {p['name']} (id {p['id']})")
            notify(f"ФГИС ЦС: опубликован новый период «{p['name']}». Нужно обновить базу цен и проверить расчёты.")
        if not new:
            print("Новых периодов нет")
        return 0
    password = getpass.getpass("Пароль (не короче 10 символов): ")
    if password != getpass.getpass("Повторите пароль: "):
        print("Пароли не совпадают", file=sys.stderr)
        return 1
    try:
        hashed = hash_password(password)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    email = args.email.strip().lower()
    with Session(get_engine()) as s:
        if s.exec(select(User).where(User.email == email)).first():
            print("Пользователь уже существует", file=sys.stderr)
            return 1
        s.add(User(email=email, name=args.name, password_hash=hashed, role=Role(args.role)))
        s.commit()
    print(f"Создан {email} ({args.role})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
