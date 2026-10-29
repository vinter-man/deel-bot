from decimal import Decimal

import pytest

from deel_advisor.money import NBSP, NNBSP, cents, format_money, format_rate, from_minor, to_minor, whole

D = Decimal


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.005", "0.01"), ("0.004", "0.00"), ("0.0049999", "0.00"), ("2.675", "2.68"), ("-0.005", "-0.01"),
     ("-0.004", "0.00"), ("10", "10.00"), ("1.115", "1.12"), ("1.125", "1.13"), ("999999999.995", "1000000000.00")],
)  # fmt: skip
def test_cents_rounds_half_up_away_from_zero(value: str, expected: str) -> None:
    # Banker's rounding would make 2.675 -> 2.67 and 1.125 -> 1.12; payroll does not.
    assert cents(D(value)) == D(expected)


@pytest.mark.parametrize(("value", "expected"), [("0.5", 1), ("1.49", 1), ("1.5", 2), ("2.5", 3), ("-0.5", -1)])
def test_whole_rounds_half_up(value: str, expected: int) -> None:
    assert whole(D(value)) == expected


def test_no_float_artefacts() -> None:
    # 0.1 + 0.2 as floats is 0.30000000000000004; as Decimals from strings it is exact.
    assert cents(D("0.1") + D("0.2")) == D("0.30")
    assert to_minor(D("0.1") * 3) == 30


@pytest.mark.parametrize(("value", "minor"), [("80000", 8_000_000), ("0.125", 13), ("0.124", 12), ("0", 0)])
def test_to_minor(value: str, minor: int) -> None:
    assert to_minor(D(value)) == minor


def test_minor_round_trip_is_exact() -> None:
    for minor in (0, 1, 99, 100, 8_000_050, 1_000_000_000):
        assert to_minor(from_minor(minor)) == minor
    assert from_minor(8_000_050) == D("80000.50")


@pytest.mark.parametrize(
    ("value", "currency", "lang", "expected"),
    [
        ("80000", "EUR", "en", "€80,000"),
        ("80000.5", "EUR", "en", "€80,001"),
        ("-1234.4", "GBP", "en", "-£1,234"),
        ("317000", "PLN", "en", f"317,000{NBSP}zł"),
        ("80000", "EUR", "de", f"80.000{NBSP}€"),
        ("80000", "EUR", "es", f"80.000{NBSP}€"),
        ("80000", "EUR", "pl", f"80{NNBSP}000{NBSP}€"),
        ("1234567", "USD", "bg", f"1{NNBSP}234{NNBSP}567{NBSP}$"),
        ("999", "SEK", "en", f"999{NBSP}SEK"),
        ("0", "EUR", "en", "€0"),
        ("0.4", "EUR", "en", "€0"),
        ("-0.4", "EUR", "en", "€0"),  # rounds to zero: no "-€0"
        ("1000000000", "EUR", "en", "€1,000,000,000"),
    ],
)
def test_format_money(value: str, currency: str, lang: str, expected: str) -> None:
    assert format_money(D(value), currency, lang) == expected


@pytest.mark.parametrize(
    ("value", "currency", "lang", "expected"),
    [("13.9", "EUR", "en", "€13.90"), ("12.71", "GBP", "de", f"12,71{NBSP}£"), ("-0.5", "EUR", "en", "-€0.50"),
     ("1234.5", "PLN", "pl", f"1{NNBSP}234,50{NBSP}zł"), ("0.005", "EUR", "es", f"0,01{NBSP}€"),
     ("-0.004", "EUR", "en", "€0.00")],
)  # fmt: skip
def test_format_money_with_cents(value: str, currency: str, lang: str, expected: str) -> None:
    assert format_money(D(value), currency, lang, with_cents=True) == expected


def test_money_never_wraps_inside_telegram() -> None:
    # Ordinary spaces would let "80 000 €" break across lines; every gap must be no-break.
    for lang in ("en", "de", "es", "pl", "bg"):
        assert " " not in format_money(D("1234567.89"), "PLN", lang, with_cents=True)
        assert " " not in format_rate(D("0.0935"), lang)


@pytest.mark.parametrize(
    ("rate", "lang", "expected"),
    [("0.093", "en", "9.3%"), ("0.0935", "pl", "9,35%"), ("0.2", "en", "20%"), ("0", "en", "0%"),
     ("0.0015", "bg", "0,15%"), ("0.093", "de", f"9,3{NBSP}%"), ("0.25", "es", f"25{NBSP}%"),
     ("0.10", "en", "10%"), ("0.123456", "en", "12.3456%"), ("0.0000001", "en", "0.00001%")],
)  # fmt: skip
def test_format_rate(rate: str, lang: str, expected: str) -> None:
    assert format_rate(D(rate), lang) == expected


def test_negative_cents_keep_their_sign() -> None:
    # The sign is decided on the cents when cents are shown: -0.40 is negative, not "€0.40".
    assert format_money(D("-0.4"), "EUR", "en", with_cents=True) == "-€0.40"
    assert format_money(D("-0.4"), "EUR", "de", with_cents=True) == f"-0,40{NBSP}€"
