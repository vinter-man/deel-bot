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
from deel_advisor.parser import Member, Team, parse
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


def test_sources(testland: Country, ctx: replies.Context) -> None:
    text = replies.sources("en", testland, ctx)
    assert '<a href="https://example.gov/rates">example.gov</a>' in text
    assert "• Registration €2,400" in text
    assert "• Payroll €50/mo" in text
    assert "📝 Minimum wage: Deel €950/mo, official €1,000/mo" in text
    assert "✅ Pension contribution ceiling: €60,000/yr" in text


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


def test_uk_rates_hold_until_april(real_catalog: Catalog, fixed_rates: Rates) -> None:
    uk = real_catalog.by_code("GB")
    assert uk is not None
    from deel_advisor import freshness

    assert not freshness.check(uk, date(2027, 3, 1)).outdated_year
    assert freshness.check(uk, date(2027, 4, 6)).outdated_year


def test_share_capital_has_a_source(real_catalog: Catalog, fixed_rates: Rates) -> None:
    germany = real_catalog.by_code("DE")
    assert germany is not None
    text = replies.sources("en", germany, replies.Context(real_catalog, fixed_rates, TODAY))
    assert "Share capital €25,000: stays the company's, not a cost — <a href=" in text


REAL_TEAM = "Germany 2 × 80k, UK 1 × £60k, Spain 1 × 50k, Poland 1 × 200k zł"


def _team(text: str, catalog: Catalog, rates: Rates) -> Team:
    return parse(text, catalog.index, {"EUR", *rates.per_eur})


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


def test_one_country_reads_as_one_company(real_catalog: Catalog, fixed_rates: Rates) -> None:
    ctx = replies.Context(real_catalog, fixed_rates, TODAY)
    text = replies.team("en", _team("Germany 2 × 80k", real_catalog, fixed_rates), ctx)
    assert text.startswith("🇩🇪 <b>Germany</b> · 2 people · 12 months")
    assert "<b>Total</b>: EOR (Deel) €11,501 · own entity €17,708" in text
    assert "EOR saves ~€6,207 — and no company to open, run and close." in text
    assert "countries" not in text
    assert "own entities" not in text


def test_one_country_where_the_entity_wins(testland: Country, fixed_rates: Rates) -> None:
    ctx = replies.Context(_catalog(testland), fixed_rates, TODAY)
    text = replies.team("de", Team((_member(testland, 50),), months=36), ctx)
    assert "wäre eine eigene Gesellschaft ~" in text
    assert "eigene Gesellschaften" not in text


@pytest.mark.parametrize("lang", ["en", "de", "es", "pl", "bg"])
@pytest.mark.parametrize(
    "text", ["Germany 80k", "Bulgaria 60k 3 people", "Poland 9000/mo", "UK 1 × £60k, Spain 1, 70k"]
)
def test_real_data_renders_in_every_language(real_catalog: Catalog, fixed_rates: Rates, lang: str, text: str) -> None:
    ctx = replies.Context(real_catalog, fixed_rates, TODAY)
    for breakdown in (True, False):
        out = replies.team(lang, _team(text, real_catalog, fixed_rates), ctx, breakdown=breakdown)  # type: ignore[arg-type]
        assert len(out) < 4096  # one Telegram message
        assert "{" not in out
        assert out.count("<b>") == out.count("</b>")
