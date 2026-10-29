from decimal import Decimal

import pytest

from deel_advisor.money import NBSP, NNBSP, cents, format_money, format_rate, from_minor, to_minor, whole


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.005", "0.01"), ("0.004", "0.00"), ("2.675", "2.68"), ("-0.005", "-0.01"), ("10", "10.00")],
)
def test_cents_rounds_half_up(value: str, expected: str) -> None:
    # Banker's rounding would turn 2.675 into 2.67 (and float would make it 2.67499...).
    assert cents(Decimal(value)) == Decimal(expected)


def test_whole_rounds_half_up() -> None:
    assert whole(Decimal("0.5")) == 1
    assert whole(Decimal("1.49")) == 1


def test_minor_units_round_trip() -> None:
    assert to_minor(Decimal("80000")) == 8_000_000
    assert to_minor(Decimal("0.125")) == 13
    assert from_minor(8_000_050) == Decimal("80000.50")


@pytest.mark.parametrize(
    ("value", "currency", "lang", "expected"),
    [
        ("80000", "EUR", "en", "€80,000"),
        ("80000.5", "EUR", "en", "€80,001"),
        ("-1234.4", "GBP", "en", "-£1,234"),
        ("317000", "PLN", "en", f"317,000{NBSP}zł"),
        ("80000", "EUR", "ru", f"80{NNBSP}000{NBSP}€"),
        ("1234567", "USD", "uk", f"1{NNBSP}234{NNBSP}567{NBSP}$"),
        ("999", "SEK", "en", f"999{NBSP}SEK"),
    ],
)
def test_format_money(value: str, currency: str, lang: str, expected: str) -> None:
    assert format_money(Decimal(value), currency, lang) == expected


def test_format_money_with_cents() -> None:
    assert format_money(Decimal("13.9"), "EUR", "en", with_cents=True) == "€13.90"
    assert format_money(Decimal("12.71"), "GBP", "ru", with_cents=True) == f"12,71{NBSP}£"
    assert format_money(Decimal("-0.5"), "EUR", "en", with_cents=True) == "-€0.50"


@pytest.mark.parametrize(
    ("rate", "lang", "expected"),
    [("0.093", "en", "9.3%"), ("0.0935", "ru", "9,35%"), ("0.2", "en", "20%"), ("0", "en", "0%"),
     ("0.0015", "uk", "0,15%")],
)  # fmt: skip
def test_format_rate(rate: str, lang: str, expected: str) -> None:
    assert format_rate(Decimal(rate), lang) == expected
