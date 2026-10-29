"""What the user reads: the HTML replies, on Testland's round numbers and on the real data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from deel_advisor import replies
from deel_advisor.bot.handlers import split_message
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


def test_plan_grammar_in_polish_and_german(testland: Country, ctx: replies.Context) -> None:
    text = replies.plan("pl", build_query("plan", (testland,), Decimal(48_000), people=1, months=6), ctx)
    assert "Dla 1 osoby przez 6 miesięcy EOR jest tańszy" in text
    assert "Spółka opłaca się od 2 osób (przez 6 miesięcy)." in text
    assert "Dla 1 osoby zwraca się po 13 miesiącach." in text
    german = replies.plan("de", build_query("plan", (testland,), Decimal(48_000), people=1, months=6), ctx)
    assert "Mit 1 Person rechnet sie sich nach 13 Monaten." in german
    assert "Für 1 Person über 6 Monate ist EOR" in german


def test_compare(testland: Country, fixed_rates: Rates) -> None:
    pricey = Country.model_validate(
        country_data(country="Pricey", code="PR", aliases=["pricey"], currency="PLN",
                     official={"checkedAt": "2026-10-01", "figures": {}})
    )  # fmt: skip
    ctx = replies.Context(_catalog(testland, pricey), fixed_rates, TODAY)
    text = replies.compare("en", build_query("compare", (testland, pricey), Decimal(48_000)), ctx)
    assert "<b>Testland vs Pricey</b> · €48,000 gross a year" in text
    assert "in PLN:" in text
    assert "💡 Cheaper: " in text
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


@pytest.mark.parametrize("lang", ["en", "de", "es", "pl", "bg"])
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
def test_real_sources_split_into_valid_messages(real_catalog: Catalog, fixed_rates: Rates, code: str) -> None:
    country = real_catalog.by_code(code)
    assert country is not None
    text = replies.sources("bg", country, replies.Context(real_catalog, fixed_rates, TODAY))
    parts = split_message(text)
    assert "\n\n".join(parts) == text
    for part in parts:
        assert len(part) <= 4096
        assert part.count("<a ") == part.count("</a>")
        assert part.count("<b>") == part.count("</b>")


def test_split_message_keeps_blocks_whole() -> None:
    assert split_message("a\n\nbb\n\nccc", limit=6) == ["a\n\nbb", "ccc"]
    assert split_message("short") == ["short"]


def test_monthly_input_below_minimum_gets_no_monthly_hint(testland: Country, ctx: replies.Context) -> None:
    query = parse("Testland 900/mo", ctx.catalog.index, {"EUR"})
    text = replies.cost("en", query, ctx)
    assert "Below the 2026 minimum wage" in text
    assert "/mo</code>" not in text  # they already typed a monthly salary


def test_monthly_hint_keeps_the_currency(testland: Country, ctx: replies.Context) -> None:
    text = replies.cost("en", build_query("cost", (testland,), Decimal(5_000), currency="USD"), ctx)
    assert "<code>Testland 5000 USD/mo</code>" in text


def test_plan_discloses_conversions(testland: Country, ctx: replies.Context) -> None:
    query = build_query("plan", (testland,), Decimal(60_000), currency="USD", people=2)
    text = replies.plan("en", query, ctx)
    assert "≈ $60,000 at the ECB rate of 29.10.2026" in text
    assert "fee €550 per person a month" in text  # Testland's EOR price is already in EUR


def test_plan_names_the_list_price_when_converted(real_catalog: Catalog, fixed_rates: Rates) -> None:
    ctx = replies.Context(real_catalog, fixed_rates, TODAY)
    query = parse("Germany 80k 5 people", real_catalog.index, {"EUR", "USD"})
    assert "fee €479 per person a month ($599 list price, ECB rate of 29.10.2026)" in replies.plan("en", query, ctx)


def test_compare_percentage_is_share_of_the_dearer_total(testland: Country, fixed_rates: Rates) -> None:
    pricey = Country.model_validate(
        country_data(country="Pricey", code="PR", aliases=["pricey"],
                     contributions=[{"id": "pension", "name": "Pension", "rate": "0.5", "source": "https://example.gov/x"}])
    )  # fmt: skip
    ctx = replies.Context(_catalog(testland, pricey), fixed_rates, TODAY)
    text = replies.compare("en", build_query("compare", (testland, pricey), Decimal(48_000)), ctx)
    # Testland €55,080 vs Pricey €72,000: €16,920 is 23.5% of €72,000.
    assert "Cheaper: Testland, by ~€16,920 a year (23.5% less)" in text


def test_uk_rates_hold_until_april(real_catalog: Catalog, fixed_rates: Rates) -> None:
    uk = real_catalog.by_code("GB")
    assert uk is not None
    from deel_advisor import freshness

    assert not freshness.check(uk, date(2027, 3, 1)).outdated_year
    assert freshness.check(uk, date(2027, 4, 6)).outdated_year


def test_mid_year_ceiling_is_announced(real_catalog: Catalog, fixed_rates: Rates) -> None:
    ctx = replies.Context(real_catalog, fixed_rates, TODAY)
    bulgaria = parse("Bulgaria 60k", real_catalog.index, {"EUR"})
    assert "ceiling from 01.08.2026, applied to every month" in replies.cost("en", bulgaria, ctx)
    germany = parse("Germany 60k", real_catalog.index, {"EUR"})
    assert "ceiling from" not in replies.cost("en", germany, ctx)


def test_share_capital_has_a_source(real_catalog: Catalog, fixed_rates: Rates) -> None:
    germany = real_catalog.by_code("DE")
    assert germany is not None
    text = replies.sources("en", germany, replies.Context(real_catalog, fixed_rates, TODAY))
    assert "Share capital €25,000: stays the company's, not a cost — <a href=" in text


def test_ceiling_note_is_in_plan_replies_too(real_catalog: Catalog, fixed_rates: Rates) -> None:
    bulgaria = parse("Bulgaria 60k 3 people", real_catalog.index, {"EUR"})
    # Even before the date the calculation uses the newer ceiling, so the note is always there.
    july = replies.Context(real_catalog, fixed_rates, date(2026, 7, 15))
    assert "ceiling from 01.08.2026, applied to every month" in replies.plan("en", bulgaria, july)
