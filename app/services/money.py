from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def to_paise(value) -> int:
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            raise ValueError("Money must be finite and non-negative")
        return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid monetary amount") from None


def same_amount(left, right) -> bool:
    try:
        a, b = Decimal(str(left)), Decimal(str(right))
        return a.is_finite() and b.is_finite() and a >= 0 and a == b
    except (InvalidOperation, TypeError, ValueError):
        return False


def commission_paise(amount: int, rate) -> int:
    value = Decimal(str(rate))
    if not value.is_finite() or not Decimal("0") <= value <= Decimal("1"):
        raise ValueError("Commission rate must be between zero and one")
    return int((Decimal(amount) * value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
