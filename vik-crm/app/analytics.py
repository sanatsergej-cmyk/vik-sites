from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlmodel import Session, select

from . import catalog
from .models import STAGE_LABELS, STAGE_PROBABILITY, Company, Deal, DealStage, Interaction, Task, now

CLOSED = (DealStage.won, DealStage.lost)
OPEN_STAGES = [s for s in DealStage if s not in CLOSED]
STUCK_DAYS = 7


def spark(values: List[int], width: int = 160, height: int = 40) -> str:
    """Точки для SVG-линии: значения масштабируются в рамку width x height."""
    if not values:
        return ""
    top = max(values) or 1
    step = width / max(len(values) - 1, 1)
    return " ".join(f"{i * step:.1f},{height - (v / top) * (height - 4) - 2:.1f}" for i, v in enumerate(values))


def dashboard_stats(session: Session, days: int = 30, at: Optional[datetime] = None) -> Dict:
    n = at or now()
    since = n - timedelta(days=days)
    deals = session.exec(select(Deal)).all()
    companies = {c.id: c.name for c in session.exec(select(Company)).all()}
    open_deals = [d for d in deals if d.stage not in CLOSED]
    amount = lambda d: d.amount_expected or 0.0  # noqa: E731

    won = [d for d in deals if d.stage == DealStage.won and d.closed_at and d.closed_at >= since]
    lost = [d for d in deals if d.stage == DealStage.lost and d.closed_at and d.closed_at >= since]
    decided = len(won) + len(lost)
    cycle_days = [(d.closed_at - d.created_at).total_seconds() / 86400 for d in won]

    week0 = (n - timedelta(days=n.weekday())).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(weeks=11)
    weekly = [0] * 12
    for d in deals:
        idx = (d.created_at - week0).days // 7
        if 0 <= idx < 12:
            weekly[idx] += 1

    funnel = []
    for st in OPEN_STAGES + [DealStage.won]:
        items = [d for d in deals if d.stage == st and (st != DealStage.won or (d.closed_at and d.closed_at >= since))]
        funnel.append({"key": st.value, "label": STAGE_LABELS[st.value], "count": len(items), "sum": sum(amount(d) for d in items)})

    in_period = [d for d in deals if d.created_at >= since]
    by_source = Counter(d.source or "—" for d in in_period).most_common()
    svc = Counter(d.service or "" for d in in_period)
    by_service = [
        {"id": k, "label": catalog.label(k) if k else "не указано", "count": v, "priority": catalog.is_priority(k)}
        for k, v in svc.most_common()
    ]
    lost_reasons = Counter((d.lost_reason or "не указана") for d in lost).most_common()

    open_tasks = session.exec(select(Task).where(Task.done == False)).all()  # noqa: E712
    overdue = sorted((t for t in open_tasks if t.due_at < n), key=lambda t: t.due_at)
    deals_by_id = {d.id: d for d in deals}
    with_task = {t.deal_id for t in open_tasks}
    last_inter: Dict[int, Interaction] = {}
    for i in session.exec(select(Interaction).where(Interaction.kind != "stage").order_by(Interaction.created_at)).all():
        last_inter[i.deal_id] = i

    return {
        "days": days,
        "companies": companies,
        "deals_by_id": deals_by_id,
        "open_count": len(open_deals),
        "pipeline": sum(amount(d) for d in open_deals),
        "weighted": sum(amount(d) * STAGE_PROBABILITY[d.stage.value] for d in open_deals),
        "priority_open": sum(1 for d in open_deals if catalog.is_priority(d.service)),
        "new_period": len(in_period),
        "won_count": len(won),
        "won_sum": sum(amount(d) for d in won),
        "lost_count": len(lost),
        "win_rate": (len(won) / decided) if decided else None,
        "avg_cycle": (sum(cycle_days) / len(cycle_days)) if cycle_days else None,
        "weekly": weekly,
        "funnel": funnel,
        "funnel_max": max([f["count"] for f in funnel] + [1]),
        "by_source": by_source,
        "by_service": by_service,
        "lost_reasons": lost_reasons,
        "overdue": overdue[:8],
        "overdue_count": len(overdue),
        "no_next": [d for d in open_deals if d.id not in with_task][:8],
        "no_next_count": sum(1 for d in open_deals if d.id not in with_task),
        "stuck": sorted((d for d in open_deals if d.updated_at < n - timedelta(days=STUCK_DAYS)), key=lambda d: d.updated_at)[:8],
        "waiting": [d for d in open_deals if d.id in last_inter and last_inter[d.id].direction == "in"][:8],
    }
