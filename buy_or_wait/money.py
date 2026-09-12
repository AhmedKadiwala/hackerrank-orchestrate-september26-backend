from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext

getcontext().prec = 28

CENTS = Decimal("0.01")


def dec(value) -> Decimal:
    if value is None:
        return Decimal("0")
    text = str(value).strip().replace(",", "")
    if text == "":
        return Decimal("0")
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def q2(value: Decimal) -> Decimal:
    return dec(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def fmt_money(value: Decimal) -> str:
    value = q2(value)
    if value == 0:
        return "0"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def pretty(value: Decimal, currency: str) -> str:
    amount = q2(value)
    whole = amount == amount.to_integral_value()
    body = f"{amount:,.0f}" if whole else f"{amount:,.2f}"
    return f"{currency} {body}"

