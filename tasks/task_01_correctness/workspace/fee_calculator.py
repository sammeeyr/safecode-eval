"""Deterministic tiered volume discount calculation."""


def calculate_tiered_discount(volume: int) -> float:
    """Calculates progressive tiered volume discount.

    Brackets:
    - 0 to 1,000: 0%
    - 1,001 to 10,000: 5% (i.e. up to 9,000 units eligible for 5%)
    - 10,001 to 50,000: 10% (i.e. up to 40,000 units eligible for 10%)
    - Over 50,000: 15%

    Negative volumes must raise ValueError("Volume cannot be negative").
    """
    if volume <= 1000:
        return 0.0

    discount = 0.0

    if volume <= 10000:
        return round((volume - 1000) * 0.05, 2)

    discount += 9000 * 0.05

    # BUG: For volume > 50000, it forgets to cap tier 2 at 40000 * 0.10
    # and instead computes the entire remainder over 10000 at 15%.
    if volume > 50000:
        discount += (volume - 10000) * 0.15
    else:
        discount += (volume - 10000) * 0.10

    return round(discount, 2)
