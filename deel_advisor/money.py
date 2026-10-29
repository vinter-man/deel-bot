"""Decimal money helpers.

Every amount in this project is a `Decimal`, never a float. Payroll rounds each payslip line to
the cent, so `cents()` is what the calculation uses; `whole()` is only for display, and the
reply says so.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ONE = Decimal("1")
ZERO = Decimal("0")

# The currencies the bot can show. Everything ECB publishes would work for conversion, but a
# symbol table that pretends to know every currency is how "1 000 ¤" ends up in a reply.
SYMBOLS: dict[str, str] = {"EUR": "€", "GBP": "£", "USD": "$", "PLN": "zł", "CHF": "CHF"}
PREFIX_IN_EN = {"EUR", "GBP", "USD"}

NBSP = " "
# Russian and Ukrainian group thousands with a space; a narrow no-break space keeps
# "80 000 €" on one line in Telegram.
NNBSP = " "


def cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def whole(value: Decimal) -> Decimal:
    return value.quantize(ONE, rounding=ROUND_HALF_UP)


def to_minor(value: Decimal) -> int:
    """Amount in cents, for places that need an integer (callback data)."""
    return int(cents(value) * 100)


def from_minor(value: int) -> Decimal:
    return Decimal(value) / 100


def _number(value: Decimal, lang: str, with_cents: bool) -> str:
    """Absolute value, grouped: `80,000` / `80 000`, and `13.90` / `13,90` with cents."""
    rounded = abs(cents(value) if with_cents else whole(value))
    integer, _, fraction = f"{rounded:f}".partition(".")
    grouped = f"{int(integer):,}".replace(",", "," if lang == "en" else NNBSP)
    if not with_cents:
        return grouped
    return f"{grouped}{'.' if lang == 'en' else ','}{fraction or '00'}"


def format_money(value: Decimal, currency: str, lang: str, *, with_cents: bool = False) -> str:
    """Rounded half-up to whole units unless `with_cents`: `€80,000` in English, `80 000 €` otherwise."""
    number = _number(value, lang, with_cents)
    sign = "-" if (cents(value) if with_cents else whole(value)) < 0 else ""
    symbol = SYMBOLS.get(currency, currency)
    if lang == "en" and currency in PREFIX_IN_EN:
        return f"{sign}{symbol}{number}"
    return f"{sign}{number}{NBSP}{symbol}"


def format_rate(rate: Decimal, lang: str) -> str:
    """0.0935 -> `9.35%` (or `9,35%`): as many decimals as the rate has, no trailing zeros."""
    percent = (rate * 100).normalize()
    text = f"{percent:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if lang != "en":
        text = text.replace(".", ",")
    return f"{text}%"
