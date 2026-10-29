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
from deel_advisor.parser import Member, Team, build_query, parse
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
    assert "Deel's guide still shows minimum wage: €950/mo; the official figure since 1 Jan 2026 is €1,000/mo" in text


def test_cost_in_another_currency(testland: Country, ctx: replies.Context) -> None:
    text = replies.cost("en", build_query("cost", (testland,), Decimal(60_000), currency="USD"), ctx)
    assert "€48,000 gross a year" in text  # 60,000 USD at 1.25
    assert "≈ $60,000 at the ECB rate of 29 Oct 2026" in text


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
    assert "Official figures last checked 1 Oct 2026" in text  # 212 days ago
    assert "Exchange rates are from 2 Jan 2026" in text


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
    assert "Converted at ECB rates of 29 Oct 2026" in text


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
    assert "📝 Minimum wage: Deel €950/mo, official €1,000/mo" in text
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
    assert "≈ $60,000 at the ECB rate of 29 Oct 2026" in text
    assert "fee €550 per person a month" in text  # Testland's EOR price is already in EUR


def test_plan_names_the_list_price_when_converted(real_catalog: Catalog, fixed_rates: Rates) -> None:
    ctx = replies.Context(real_catalog, fixed_rates, TODAY)
    query = parse("Germany 80k 5 people", real_catalog.index, {"EUR", "USD"})
    assert "fee €479 per person a month ($599 list price, ECB rate of 29 Oct 2026)" in replies.plan("en", query, ctx)


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
    assert "ceiling from 1 Aug 2026, applied to every month" in replies.cost("en", bulgaria, ctx)
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
    assert "ceiling from 1 Aug 2026, applied to every month" in replies.plan("en", bulgaria, july)


REAL_TEAM = "Germany 2 × 80k, UK 1 × £60k, Spain 1 × 50k, Poland 1 × 200k zł"


def _team(text: str, catalog: Catalog, rates: Rates) -> Team:
    result = parse(text, catalog.index, {"EUR", *rates.per_eur})
    assert isinstance(result, Team)
    return result


def _member(country: Country, count: int = 1, salary: int = 48_000) -> Member:
    return Member(country, count, Decimal(salary), "EUR")


def test_team_reply_on_real_data(real_catalog: Catalog, fixed_rates: Rates) -> None:
    ctx = replies.Context(real_catalog, fixed_rates, TODAY)
    text = replies.team("en", _team(REAL_TEAM, real_catalog, fixed_rates), ctx)
    assert text.startswith("🌍 <b>Team in 4 countries</b> · 5 people · 12 months")
    # Each country on its own lines, with its own salary in its own currency.
    assert "🇩🇪 <b>Germany</b> · 2 people × €80,000\n   EOR (Deel): €11,501 ✅\n   Own entity: €17,708\n" in text
    assert "🇬🇧 <b>United Kingdom</b> · 1 person × £60,000\n   EOR (Deel): €5,750 ✅\n" in text
    assert "🇵🇱 <b>Poland</b> · 1 person × 200,000\u00a0zł\n" in text
    assert text.count(" ✅") == 4
    assert "<b>Total</b>: EOR (Deel) €28,752 · 4 own entities €56,550" in text
    assert "EOR saves ~€27,798 — and no company to open, run and close in 4 countries" in text
    assert "Cheapest mix" not in text  # every country is on the same side


def test_team_caption_leaves_the_detail_to_the_chart(real_catalog: Catalog, fixed_rates: Rates) -> None:
    ctx = replies.Context(real_catalog, fixed_rates, TODAY)
    team = _team(REAL_TEAM, real_catalog, fixed_rates)
    full, caption = replies.team("en", team, ctx), replies.team("en", team, ctx, breakdown=False)
    assert caption.startswith("🌍 <b>Team in 4 countries</b> · 5 people · 12 months\n\n💡 Over 12 months EOR saves")
    assert "Own entity:" not in caption
    assert "<b>Total</b>" not in caption
    assert caption in full.replace(full[full.index("🇩🇪") : full.index("💡")], "")


def test_team_rows_add_up(real_catalog: Catalog, fixed_rates: Rates) -> None:
    # The chart and the text both draw on team_rows: per country, EOR fees and entity costs in EUR.
    ctx = replies.Context(real_catalog, fixed_rates, TODAY)
    rows = replies.team_rows(_team(REAL_TEAM, real_catalog, fixed_rates), ctx)
    assert [(r.member.country.code, r.eor_wins) for r in rows] == [("DE", True), ("GB", True), ("ES", True),
                                                                   ("PL", True)]  # fmt: skip
    # Two people pay two fees; the fee is per head, whatever the salary: $575 at 1.25 per euro.
    assert [r.eor for r in rows] == [Decimal("11500.8"), *[Decimal("5750.4")] * 3]
    assert rows[1].employment > rows[2].employment  # £60k costs more than €50k to employ


def test_team_mix_when_countries_disagree(testland: Country, fixed_rates: Rates) -> None:
    cheap = country_data(country="Cheapland", code="CH", aliases=["cheapland"])
    cheap["entity"]["setupCost"][0]["amount"] = "1"
    cheap["entity"]["monthlyFixed"][0]["amount"] = "1"
    cheapland = Country.model_validate(cheap)
    ctx = replies.Context(_catalog(testland, cheapland), fixed_rates, TODAY)
    text = replies.team("en", Team((_member(testland), _member(cheapland))), ctx)
    # A tie stays on EOR: no entity to open for nothing.
    assert "🏳️ <b>Testland</b> · 1 person × €48,000\n   EOR (Deel): €6,600 ✅\n   Own entity: €6,600\n" in text
    assert "<b>Cheapland</b> · 1 person × €48,000\n   EOR (Deel): €6,600\n   Own entity: €" in text
    assert "Cheapest mix: EOR in 🏳️, own entity on Deel Payroll in 🏳️" in text


@pytest.mark.parametrize("lang", ["en", "de", "es", "pl", "bg"])
@pytest.mark.parametrize("breakdown", [True, False])
def test_team_reply_in_every_language(real_catalog: Catalog, fixed_rates: Rates, lang: str, breakdown: bool) -> None:
    ctx = replies.Context(real_catalog, fixed_rates, TODAY)
    team = _team("Germany 2 × 80k, Spain 2 × 50k, Poland 1 × 150k zł 24 months", real_catalog, fixed_rates)
    text = replies.team(lang, team, ctx, breakdown=breakdown)  # type: ignore[arg-type]
    assert "{" not in text
    assert text.count("<b>") == text.count("</b>")
    assert text.count("<i>") == text.count("</i>")


def test_team_reply_carries_the_warnings(real_catalog: Catalog, fixed_rates: Rates) -> None:
    ctx = replies.Context(real_catalog, fixed_rates, TODAY)
    text = replies.team("en", _team("Germany 2, UK 1 — 20k", real_catalog, fixed_rates), ctx, breakdown=False)
    assert "🇩🇪 ⚠️ Below the 2026 minimum wage" in text
    assert "🇬🇧 ⚠️ Below the 2026 minimum wage" in text  # €20k is under the UK's too, converted
    assert "📝 Deel's guides for 🇩🇪 🇬🇧 still show some figures that have since changed" in text
    assert text.count("📝") == 1  # one line for the guides, the detail lives in /sources


def test_team_tie_is_called_a_tie(testland: Country, fixed_rates: Rates) -> None:
    twin = Country.model_validate(country_data(country="Twin", code="TW", aliases=["twin"]))
    ctx = replies.Context(_catalog(testland, twin), fixed_rates, TODAY)
    # One person each over 12 months: 6,600 of EOR fees against 6,600 of entity costs per country.
    text = replies.team("en", Team((_member(testland), _member(twin))), ctx)
    assert "both cost about the same" in text
    assert "~€0" not in text


def test_team_where_entities_win(testland: Country, fixed_rates: Rates) -> None:
    twin = Country.model_validate(country_data(country="Twin", code="TW", aliases=["twin"]))
    ctx = replies.Context(_catalog(testland, twin), fixed_rates, TODAY)
    text = replies.team("en", Team((_member(testland, 50), _member(twin, 50)), months=36), ctx)
    assert "own entities would be ~" in text
    assert "Deel Payroll can run their payroll" in text
    assert "   Own entity: €" in text
    assert "   EOR (Deel): €" in text
    assert all(line.endswith("✅") for line in text.splitlines() if line.startswith("   Own entity"))


def test_team_reply_says_when_figures_are_stale(real_catalog: Catalog, fixed_rates: Rates) -> None:
    ctx = replies.Context(real_catalog, fixed_rates, date(2027, 6, 1))
    text = replies.team("en", _team("Germany 2 × 70k, UK 1 × £60k", real_catalog, fixed_rates), ctx)
    assert "🇩🇪 ⚠️ Official figures last checked 29 Oct 2026." in text
