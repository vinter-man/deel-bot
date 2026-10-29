"""What the user reads: the HTML replies, on Testland's round numbers and on the real data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from deel_advisor import replies
from deel_advisor.catalog import Catalog
from deel_advisor.fx import Rates
from deel_advisor.models import Country, EorPricing
from deel_advisor.parser import build_query, parse
from tests.conftest import TODAY, country_data


def _catalog(*countries: Country, fee: str = "550") -> Catalog:
    eor = EorPricing(
        provider="Deel",
        monthly_fee=Decimal(fee),
        currency="EUR",
        source="https://www.deel.com/pricing/",
        checked_at=TODAY,
        note="list price",
    )  # type: ignore[arg-type]
    return Catalog(countries, eor)  # fmt: skip


@pytest.fixture
def ctx(testland: Country, fixed_rates: Rates) -> replies.Context:
    return replies.Context(_catalog(testland), fixed_rates, TODAY)


def test_cost_reply(testland: Country, ctx: replies.Context) -> None:
    text = replies.cost("en", build_query("cost", (testland,), Decimal(48_000)), ctx)
    assert "🏳️ <b>Testland</b> · €48,000 gross a year" in text
    assert "Employer cost: <b>€55,080</b> a year · €4,590 a month" in text
    assert "+€7,080 a year (14.8%)" in text
    assert "• Health 5%, capped — €1,800" in text
    assert "• Accident ~1% — €480" in text
    assert "typical rate" in text
    # Testland's guide disagrees with the official minimum wage:
    assert "Deel's guide says minimum wage: €950/mo; officially from 01.01.2026: €1,000/mo" in text


def test_cost_in_another_currency(testland: Country, ctx: replies.Context) -> None:
    text = replies.cost("en", build_query("cost", (testland,), Decimal(60_000), currency="USD"), ctx)
    assert "€48,000 gross a year" in text  # 60,000 USD at 1.25
    assert "≈ $60,000 at the ECB rate of 29.10.2026" in text


def test_monthly_input_is_shown(testland: Country, ctx: replies.Context) -> None:
    query = parse("Testland 4000/mo", ctx.catalog.index, {"EUR"})
    assert "€4,000 a month × 12" in replies.cost("en", query, ctx)


def test_below_minimum_wage_hint(testland: Country, ctx: replies.Context) -> None:
    text = replies.cost("en", build_query("cost", (testland,), Decimal(5_000)), ctx)
    assert "Below the 2026 minimum wage (€12,000 a year)" in text
    assert "<code>Testland 5000/mo</code>" in text


def test_stale_fx_and_old_year(testland: Country) -> None:
    old_rates = Rates(date(2026, 1, 2), {"USD": Decimal(1)})
    ctx = replies.Context(_catalog(testland), old_rates, date(2027, 5, 1))
    text = replies.cost("en", build_query("cost", (testland,), Decimal(48_000)), ctx)
    assert "These are 2026 rates; 2027 figures may differ" in text
    assert "Official figures last checked 01.10.2026" in text  # 212 days ago
    assert "Exchange rates are from 02.01.2026" in text


def test_plan_entity_cheaper(testland: Country, ctx: replies.Context) -> None:
    text = replies.plan("en", build_query("plan", (testland,), Decimal(48_000), people=3), ctx)
    assert "🏳️ <b>Testland</b> · 3 people × €48,000 a year · 12 months" in text
    assert "<b>EOR (Deel)</b>: €185,040" in text  # 3 × 12 × (4590 + 550)
    assert "<b>Own entity</b>: €173,040" in text  # 3 × 12 × 4590 + 2400 + 12 × 450
    assert "your own entity is cheaper by ~€12,000" in text
    # 3 × (550 − 50) − 300 = 1200 saved a month: 2400 of setup is even at month 2, ahead at 3.
    assert "With 3 people it pays off after 3 months." in text


def test_plan_eor_cheaper_and_breakeven_team(testland: Country, ctx: replies.Context) -> None:
    text = replies.plan("en", build_query("plan", (testland,), Decimal(48_000), people=1, months=6), ctx)
    assert "For 1 person over 6 months EOR is cheaper by ~€" in text
    assert "An entity pays off from 2 people (over 6 months)." in text
    assert "With 1 person it pays off after 13 months." in text


def test_plan_even(testland: Country, ctx: replies.Context) -> None:
    text = replies.plan("en", build_query("plan", (testland,), Decimal(48_000), people=1, months=12), ctx)
    assert "both cost about the same" in text


def test_plan_never_pays_off(testland: Country, fixed_rates: Rates) -> None:
    ctx = replies.Context(_catalog(testland, fee="40"), fixed_rates, TODAY)
    text = replies.plan("en", build_query("plan", (testland,), Decimal(48_000), people=2), ctx)
    assert "At these prices an entity never pays off." in text
    assert "EOR is cheaper" in text


def test_plan_never_for_this_team(testland: Country, fixed_rates: Rates) -> None:
    ctx = replies.Context(_catalog(testland, fee="340"), fixed_rates, TODAY)
    text = replies.plan("en", build_query("plan", (testland,), Decimal(48_000), people=1), ctx)
    assert "With 1 person it never pays off" in text


def test_plan_russian_grammar(testland: Country, ctx: replies.Context) -> None:
    text = replies.plan("ru", build_query("plan", (testland,), Decimal(48_000), people=1, months=6), ctx)
    assert "Для 1 человека на 6 месяцев EOR дешевле" in text
    assert "Юрлицо окупается с 2 человек (на 6 месяцев)." in text


def test_compare(testland: Country, fixed_rates: Rates) -> None:
    pricey = Country.model_validate(
        country_data(country="Pricey", code="PR", aliases=["pricey"], currency="PLN",
                     official={"checkedAt": "2026-10-01", "figures": {}})
    )  # fmt: skip
    ctx = replies.Context(_catalog(testland, pricey), fixed_rates, TODAY)
    text = replies.compare("en", build_query("compare", (testland, pricey), Decimal(48_000)), ctx)
    assert "<b>Testland vs Pricey</b> · €48,000 gross a year" in text
    assert "in PLN:" in text
    assert "is cheaper to employ in" in text
    assert "Converted at ECB rates of 29.10.2026" in text


def test_compare_identical_countries_has_no_winner(testland: Country, fixed_rates: Rates) -> None:
    twin = Country.model_validate(country_data(country="Twin", code="TW", aliases=["twin"]))
    ctx = replies.Context(_catalog(testland, twin), fixed_rates, TODAY)
    text = replies.compare("en", build_query("compare", (testland, twin), Decimal(48_000)), ctx)
    assert "cheaper to employ" not in text
    assert "Converted" not in text  # nothing was converted


def test_sources(testland: Country, ctx: replies.Context) -> None:
    text = replies.sources("en", testland, ctx)
    assert '<a href="https://example.gov/rates">example.gov</a>' in text
    assert "• Registration €2,400" in text
    assert "• Payroll €50/mo" in text
    assert "⚠️ Minimum wage: Deel €950/mo, official €1,000/mo" in text
    assert "✅ Pension contribution ceiling: €60,000/yr" in text


@pytest.mark.parametrize("lang", ["en", "uk", "ru"])
@pytest.mark.parametrize("text", ["Germany 80k", "Bulgaria 60k 3 people", "UK vs Spain 70000 EUR", "Poland 9000/mo"])
def test_real_data_renders_in_every_language(real_catalog: Catalog, fixed_rates: Rates, lang: str, text: str) -> None:
    ctx = replies.Context(real_catalog, fixed_rates, TODAY)
    query = parse(text, real_catalog.index, {"EUR", *fixed_rates.per_eur})
    render = {"cost": replies.cost, "plan": replies.plan, "compare": replies.compare}[query.kind]
    out = render(lang, query, ctx)  # type: ignore[arg-type]
    assert len(out) < 4096  # one Telegram message
    assert out.count("<b>") == out.count("</b>")
    assert out.count("<a ") == out.count("</a>")


@pytest.mark.parametrize("code", ["DE", "GB", "ES", "PL", "BG"])
def test_real_sources_fit_one_message(real_catalog: Catalog, fixed_rates: Rates, code: str) -> None:
    country = real_catalog.by_code(code)
    assert country is not None
    text = replies.sources("ru", country, replies.Context(real_catalog, fixed_rates, TODAY))
    assert len(text) < 4096
