from dataclasses import dataclass


@dataclass(frozen=True)
class PriceBreakdown:
    mtr_net: float
    smr_net: float
    mtr_with_vat: float
    smr_with_vat: float
    subtotal: float
    limited: float
    total: float


def compute(base_mtr: float, base_smr: float, k_mtr: float, k_smr: float, vat: float, lim_percent: float) -> PriceBreakdown:
    """Порядок из правил: база без НДС -> наценка (МТР/СМР) -> НДС -> лимитированные затраты от ИТОГО."""
    mtr_net = base_mtr * k_mtr
    smr_net = base_smr * k_smr
    mtr_vat = mtr_net * (1 + vat)
    smr_vat = smr_net * (1 + vat)
    subtotal = mtr_vat + smr_vat
    limited = subtotal * lim_percent / 100
    return PriceBreakdown(
        mtr_net=round(mtr_net, 2),
        smr_net=round(smr_net, 2),
        mtr_with_vat=round(mtr_vat, 2),
        smr_with_vat=round(smr_vat, 2),
        subtotal=round(subtotal, 2),
        limited=round(limited, 2),
        total=round(subtotal + limited, 2),
    )
