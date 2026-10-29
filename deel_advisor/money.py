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
NNBSP = " "

# How each language writes 80000.5 and 9.3%: (thousands separator, decimal mark, before "%").
# German and Spanish group with a dot and put a space before the percent sign; Polish and
# Bulgarian group with a (narrow, no-break) space, so "80 000 €" never wraps in Telegram.
_STYLE: dict[str, tuple[str, str, str]] = {
    "en": (",", ".", ""),
    "de": (".", ",", NBSP),
    "es": (".", ",", NBSP),
    "pl": (NNBSP, ",", ""),
    "bg": (NNBSP, ",", ""),
}


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
    """Absolute value, grouped: `80,000` / `80.000` / `80 000`, and `13.90` / `13,90` with cents."""
    group, decimal, _ = _STYLE[lang]
    rounded = abs(cents(value) if with_cents else whole(value))
    integer, _, fraction = f"{rounded:f}".partition(".")
    grouped = f"{int(integer):,}".replace(",", group)
    if not with_cents:
        return grouped
    return f"{grouped}{decimal}{fraction}"  # cents() always leaves exactly two places


def format_money(value: Decimal, currency: str, lang: str, *, with_cents: bool = False) -> str:
    """Rounded half-up to whole units unless `with_cents`: `€80,000` in English, `80.000 €` in German."""
    number = _number(value, lang, with_cents)
    sign = "-" if (cents(value) if with_cents else whole(value)) < 0 else ""
    symbol = SYMBOLS.get(currency, currency)
    if lang == "en" and currency in PREFIX_IN_EN:
        return f"{sign}{symbol}{number}"
    return f"{sign}{number}{NBSP}{symbol}"


def format_rate(rate: Decimal, lang: str) -> str:
    """0.0935 -> `9.35%`, `9,35 %`, `9,35%`: as many decimals as the rate has, no trailing zeros."""
    _, decimal, space = _STYLE[lang]
    # normalize() drops trailing zeros (9.30 -> 9.3, 20.0 -> 2E+1); ":f" undoes the exponent.
    text = f"{(rate * 100).normalize():f}"
    return f"{text.replace('.', decimal)}{space}%"
