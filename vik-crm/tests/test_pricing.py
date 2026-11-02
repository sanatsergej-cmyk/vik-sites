from app.pricing import compute


def test_markup_vat_and_limited_order():
    p = compute(1000, 1000, 1.20, 1.356, 0.22, 8)
    assert p.mtr_with_vat == 1464.0
    assert p.smr_with_vat == 1654.32
    assert p.subtotal == 3118.32
    assert p.limited == 249.47
    assert p.total == 3367.79


def test_zero_is_zero():
    assert compute(0, 0, 1.2, 1.356, 0.22, 8).total == 0
