from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from .config import Settings
from .models import Deal, Estimate
from .pricing import compute

MONEY = '# ##0.00 "₽"'


def build_kp_xlsx(settings: Settings, deal: Deal, est: Estimate, internal: bool = False) -> bytes:
    """Минимальное КП из итоговых блоков расчёта (без построчной сметы)."""
    p = compute(est.base_mtr, est.base_smr, est.k_mtr, est.k_smr, est.vat, est.lim_percent)
    wb = Workbook()
    ws = wb.active
    ws.title = "КП"
    bold = Font(bold=True)
    ws.append(["Коммерческое предложение"])
    ws["A1"].font = Font(bold=True, size=14)
    if settings.legal_name:
        ws.append([settings.legal_name])
    for line in settings.requisites.split("|") if settings.requisites else []:
        ws.append([line.strip()])
    ws.append([f"Объект: {deal.title}"])
    ws.append([f"Расчёт: {est.title}"])
    ws.append([])
    ws.append(["Наименование", f"Сумма с НДС {round(est.vat * 100)}%"])
    ws[ws.max_row][0].font = bold
    ws[ws.max_row][1].font = bold
    rows = [
        ("Материалы (МТР)", p.mtr_with_vat),
        ("Строительно-монтажные работы (СМР)", p.smr_with_vat),
        ("ИТОГО", p.subtotal),
        (f"Лимитированные затраты ({est.lim_percent:g}% от ИТОГО)", p.limited),
        ("Общая стоимость", p.total),
    ]
    for name, value in rows:
        ws.append([name, value])
        ws.cell(row=ws.max_row, column=2).number_format = MONEY
    for name in ("ИТОГО", "Общая стоимость"):
        for r in ws.iter_rows(min_row=1, max_row=ws.max_row):
            if r[0].value == name:
                r[0].font = bold
                r[1].font = bold
    ws.column_dimensions["A"].width = 56
    ws.column_dimensions["B"].width = 24
    ws["A1"].alignment = Alignment(horizontal="left")

    if internal:
        wi = wb.create_sheet("ВНУТР")
        wi.append(["Внутренний лист. Заказчику не передавать."])
        wi["A1"].font = bold
        wi.append(["База МТР без НДС", est.base_mtr])
        wi.append(["База СМР без НДС", est.base_smr])
        wi.append(["Наценка МТР", est.k_mtr])
        wi.append(["Наценка СМР", est.k_smr])
        wi.append(["НДС", est.vat])
        wi.append(["Лимитированные, % от ИТОГО", est.lim_percent])
        wi.append(["МТР после наценки без НДС", p.mtr_net])
        wi.append(["СМР после наценки без НДС", p.smr_net])
        wi.column_dimensions["A"].width = 38
        wi.column_dimensions["B"].width = 20

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
