from datetime import timedelta

from sqlmodel import Session, select

from .conftest import csrf_from, login, make_user


def _boss(client):
    make_user("boss@example.com", "correct-horse-1", "admin")
    login(client, "boss@example.com", "correct-horse-1")
    return csrf_from(client, "/companies")


def test_analytics_numbers(client):
    from app.analytics import dashboard_stats, spark
    from app.db import get_engine
    from app.models import Company, Deal, DealStage, Interaction, Task, now

    n = now()
    with Session(get_engine()) as s:
        c = Company(name="ООО А")
        s.add(c)
        s.flush()
        def deal(title, stage, amount, service="", created=None, closed=None, lost="", updated=None):
            d = Deal(title=title, company_id=c.id, stage=stage, amount_expected=amount, service=service, source="site",
                     created_at=created or n, updated_at=updated or n, closed_at=closed, lost_reason=lost)
            s.add(d)
            s.flush()
            return d
        deal("новая", DealStage.new, 1000, "earthworks")
        deal("кп", DealStage.proposal_sent, 2000, "pipeline-install")
        w1 = deal("выиграна 1", DealStage.won, 5000, created=n - timedelta(days=10), closed=n - timedelta(days=2))
        deal("выиграна 2", DealStage.won, 1000, created=n - timedelta(days=20), closed=n - timedelta(days=1))
        deal("проиграна", DealStage.lost, 700, closed=n - timedelta(days=3), lost="дорого")
        old = deal("зависла", DealStage.estimate, 0, updated=n - timedelta(days=9))
        s.add(Task(deal_id=2, title="Дожим", due_at=n - timedelta(days=1)))
        s.add(Interaction(deal_id=1, kind="call", channel="phone", direction="in", body="звонок"))
        s.commit()
        st = dashboard_stats(s, 30, at=n)
    assert st["open_count"] == 3 and st["pipeline"] == 3000
    assert round(st["weighted"], 2) == 1000 * 0.10 + 2000 * 0.55 + 0
    assert st["won_count"] == 2 and st["lost_count"] == 1 and round(st["win_rate"], 3) == round(2 / 3, 3)
    assert round(st["avg_cycle"], 1) == round((8 + 19) / 2, 1)
    assert st["lost_reasons"] == [("дорого", 1)]
    assert st["overdue_count"] == 1 and st["overdue"][0].deal_id == 2
    assert [d.title for d in st["waiting"]] == ["новая"]
    assert [d.title for d in st["stuck"]] == ["зависла"]
    assert st["priority_open"] == 2
    assert sum(st["weekly"]) == 6 - 0 and len(st["weekly"]) == 12
    assert any(x["priority"] and x["id"] == "earthworks" for x in st["by_service"])
    assert spark([0, 5, 10]).count(",") == 3 and spark([]) == ""


def test_dashboard_search_quick_edit_csv(client):
    t = _boss(client)
    r = client.post("/quick", data={"company": "ООО Север", "contact_name": "Анна", "phone": "+7 (999) 123-45-67",
                                    "service": "cable-install", "title": "=HYPERLINK(\"x\")", "amount": "1 500 000", "note": "Звонили", "csrf": t},
                    follow_redirects=False)
    assert r.headers["location"] == "/deals/1"
    again = client.post("/quick", data={"phone": "89991234567", "title": "Повтор", "csrf": t}, follow_redirects=False)
    assert again.headers["location"] == "/deals/2?reused=1"
    from app.db import get_engine
    from app.models import Company, Deal

    with Session(get_engine()) as s:
        assert len(s.exec(select(Company)).all()) == 1
        assert s.get(Deal, 1).amount_expected == 1_500_000 and s.get(Deal, 1).service == "cable-install"
    assert client.post("/quick", data={"csrf": t}).status_code == 422

    for path in ("/", "/?days=7", "/?days=90", "/?days=999", "/quick", "/deals?prio=1", "/deals?owner=1", "/deals/1", "/deals/2"):
        assert client.get(path).status_code == 200, path
    assert "Контакт уже был в базе" in client.get("/deals/2?reused=1").text

    found = client.get("/search?q=123-45").text
    assert "Анна" in found
    assert "Север" in client.get("/search?q=север").text
    assert "минимум 2" in client.get("/search?q=a").text

    client.post("/deals/1/edit", data={"title": "Кабель 10 кВ", "service": "pipeline-install", "amount_expected": "2 000 000", "owner_id": "1", "csrf": t})
    with Session(get_engine()) as s:
        d = s.get(Deal, 1)
        assert d.title == "Кабель 10 кВ" and d.service == "pipeline-install" and d.amount_expected == 2_000_000 and d.owner_id == 1

    client.post("/deals/2/edit", data={"title": "+cmd|calc", "csrf": t})
    csv_text = client.get("/deals.csv").content.decode("utf-8-sig")
    assert "'+cmd|calc" in csv_text and "приоритет" in csv_text.splitlines()[0] or "приоритет" in csv_text


def test_estimate_sent_moves_deal_and_won_sets_closed_at(client):
    t = _boss(client)
    client.post("/quick", data={"company": "ООО Юг", "title": "Склад", "csrf": t})
    client.post("/deals/1/estimates", data={"title": "Расчёт", "csrf": t})
    base = {"title": "Расчёт", "base_mtr": "1000", "base_smr": "1000", "k_mtr": "1.2", "k_smr": "1.356", "vat": "0.22", "lim_percent": "0", "csrf": t}
    client.post("/estimates/1", data={**base, "status": "sent"})
    from app.db import get_engine
    from app.models import Deal, DealStage, Interaction, Task

    with Session(get_engine()) as s:
        d = s.get(Deal, 1)
        assert d.stage == DealStage.proposal_sent
        assert any("Дожим" in x.title for x in s.exec(select(Task)).all())
        assert any("КП отправлено" in i.body for i in s.exec(select(Interaction)).all())
    client.post("/estimates/1", data={**base, "status": "sent"})
    with Session(get_engine()) as s:
        assert len([i for i in s.exec(select(Interaction)).all() if "КП отправлено" in i.body]) == 1
    client.post("/deals/1/stage", data={"stage": "won", "csrf": t})
    with Session(get_engine()) as s:
        assert s.get(Deal, 1).closed_at is not None
    client.post("/deals/1/stage", data={"stage": "negotiation", "csrf": t})
    with Session(get_engine()) as s:
        assert s.get(Deal, 1).closed_at is None
