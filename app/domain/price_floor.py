"""
Price floor helper — standalone defensive price calculation.

Extracted as a separate module so service layer code can compute
`defensive_price` for storage in `my_products.defensive_price` without
importing the full rule engine.

    defensive_price = cost + min_margin_amount

When only min_margin_rate is set:

    defensive_price = ceil(cost × (1 + min_margin_rate))
"""

from decimal import ROUND_HALF_UP, Decimal


def compute_defensive_price(
    cost: Decimal | int | float,
    min_margin_amount: Decimal | int | float | None = None,
    min_margin_rate: Decimal | int | float | None = None,
) -> int:
    """
    Compute the absolute minimum acceptable price for a product.

    At least one of `min_margin_amount` or `min_margin_rate` must be provided.
    If both are provided, `min_margin_amount` takes precedence (¥ is more
    predictable than a ratio for operators setting hard floors).

    Parameters
    ----------
    cost               : Product cost in ¥.
    min_margin_amount  : Minimum margin in ¥ (e.g. 500).
    min_margin_rate    : Minimum margin as a ratio (e.g. 0.15 = 15%).

    Returns
    -------
    Defensive price floor as integer ¥.

    Raises
    ------
    ValueError  If neither margin parameter is provided.
    """
    cost_d = Decimal(str(cost))

    if min_margin_amount is not None:
        floor = cost_d + Decimal(str(min_margin_amount))
    elif min_margin_rate is not None:
        floor = cost_d * (Decimal("1") + Decimal(str(min_margin_rate)))
    else:
        raise ValueError("Either min_margin_amount or min_margin_rate must be provided")

    return int(floor.to_integral_value(rounding=ROUND_HALF_UP))
