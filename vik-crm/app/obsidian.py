import re
from pathlib import Path

from sqlmodel import Session, select

from . import catalog
from .models import STAGE_LABELS, Company, Contact, Deal, Estimate, Interaction, Supplier, Task
from .pricing import compute

_BAD = re.compile(r'[\\/:*?"<>|#^\[\]]')


def safe(name: str) -> str:
    cleaned = _BAD.sub(" ", name).strip()
    return re.sub(r"\s+", " ", cleaned)[:80] or "без названия"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def export_vault(session: Session, out: Path) -> int:
    """Выгружает клиентов, сделки и поставщиков в markdown с [[ссылками]] для графа Obsidian. Файлы клиентов не копируются."""
    out = Path(out)
    count = 0
    companies = {c.id: c for c in session.exec(select(Company)).all()}
    deals = session.exec(select(Deal).order_by(Deal.id)).all()
    deal_name = lambda d: f"Сделка {d.id} — {safe(d.title)}"  # noqa: E731
    company_name = lambda c: f"{safe(c.name)} ({c.id})"  # noqa: E731

    for c in companies.values():
        contacts = session.exec(select(Contact).where(Contact.company_id == c.id)).all()
        mine = [d for d in deals if d.company_id == c.id]
        lines = [
            "---", "type: client", f"inn: {c.inn}", f"okved: {c.okved}", f"source: {c.source}", "---",
            f"# {c.name}", "", c.notes, "", "## Контакты",
        ]
        lines += [f"- {k.name} {k.position} {k.phone} {k.email} {k.telegram}".rstrip() for k in contacts] or ["- нет"]
        lines += ["", "## Сделки"] + ([f"- [[{deal_name(d)}]]" for d in mine] or ["- нет"])
        _write(out / "Клиенты" / f"{company_name(c)}.md", "\n".join(lines) + "\n")
        count += 1

    for d in deals:
        c = companies.get(d.company_id)
        items = session.exec(select(Interaction).where(Interaction.deal_id == d.id).order_by(Interaction.created_at)).all()
        tasks = session.exec(select(Task).where(Task.deal_id == d.id)).all()
        ests = session.exec(select(Estimate).where(Estimate.deal_id == d.id)).all()
        lines = [
            "---", "type: deal", f"stage: {d.stage.value}", f"service: {d.service}",
            f"priority: {str(catalog.is_priority(d.service)).lower()}", f"source: {d.source}", "---",
            f"# {d.title}", "",
            f"Клиент: [[{company_name(c)}]]" if c else "Клиент: —",
            f"Стадия: {STAGE_LABELS[d.stage.value]}", f"Услуга: {catalog.label(d.service) if d.service else '—'}", "",
            "## Расчёты",
        ]
        for e in ests:
            lines.append(f"- {e.title}: {compute(e.base_mtr, e.base_smr, e.k_mtr, e.k_smr, e.vat, e.lim_percent).total:,.2f} ₽ ({e.status})")
        if not ests:
            lines.append("- нет")
        lines += ["", "## Задачи"] + ([f"- [{'x' if t.done else ' '}] {t.title} до {t.due_at:%d.%m.%Y}" for t in tasks] or ["- нет"])
        lines += ["", "## История"]
        for i in items:
            tag = f"{i.channel or i.kind}{' ' + i.direction if i.direction else ''}"
            lines.append(f"- {i.created_at:%d.%m.%Y %H:%M} · {tag}: {i.body}")
        _write(out / "Сделки" / f"{deal_name(d)}.md", "\n".join(lines) + "\n")
        count += 1

    for s in session.exec(select(Supplier)).all():
        _write(out / "Поставщики" / f"{safe(s.name)}.md", f"---\ntype: supplier\n---\n# {s.name}\n\n{s.categories}\n{s.contact}\n{s.notes}\n")
        count += 1

    _write(out / "ВиК CRM.md", "# ВиК CRM\n\n- Клиенты\n- Сделки\n- Поставщики\n\nГраф связей: клиент → сделки.\n")
    return count + 1
