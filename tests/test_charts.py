"""The team chart: a valid PNG, the same picture every time, in every language, safe to draw
from several threads at once (the handler renders it with asyncio.to_thread)."""

from __future__ import annotations

import asyncio
import struct
from decimal import Decimal

import pytest

from deel_advisor import charts, replies
from deel_advisor.catalog import Catalog
from deel_advisor.fx import Rates
from deel_advisor.models import Country, EorPricing
from deel_advisor.parser import Member, Team, parse
from tests.conftest import TODAY

PNG = b"\x89PNG\r\n\x1a\n"


def _rows(text: str, catalog: Catalog, rates: Rates) -> tuple[list[replies.TeamRow], int]:
    team = parse(text, catalog.index, {"EUR", *rates.per_eur})
    assert isinstance(team, Team)
    return replies.team_rows(team, replies.Context(catalog, rates, TODAY)), team.months


def _size(png: bytes) -> tuple[int, int]:
    width, height = struct.unpack(">II", png[16:24])  # the IHDR chunk follows the signature
    return width, height


@pytest.mark.parametrize("lang", ["en", "de", "es", "pl", "bg"])
def test_chart_is_a_png_in_every_language(real_catalog: Catalog, fixed_rates: Rates, lang: str) -> None:
    rows, months = _rows("Germany 2 × 80k, UK 1 × £60k, Bulgaria 1 × 30k", real_catalog, fixed_rates)
    png = charts.team_chart(lang, rows, months)  # type: ignore[arg-type]
    assert png.startswith(PNG)
    assert _size(png) == (1600, 1008)  # 10 in wide, 2.7 + 1.2 per country tall, at 160 dpi


def test_chart_grows_with_the_team_and_is_reproducible(real_catalog: Catalog, fixed_rates: Rates) -> None:
    two, _ = _rows("Germany 2 × 80k, Spain 1 × 50k", real_catalog, fixed_rates)
    five, _ = _rows("Germany 2 × 80k, UK 1 × £60k, Spain 1 × 50k, Poland 1 × 200k zł, Bulgaria 1 × 30k",
                    real_catalog, fixed_rates)  # fmt: skip
    assert _size(charts.team_chart("en", five, 12))[1] > _size(charts.team_chart("en", two, 12))[1]
    # The pencil wobble is seeded: the same team draws the same bytes, so a horizon tap that
    # changes nothing really changes nothing.
    assert charts.team_chart("en", two, 12) == charts.team_chart("en", two, 12)
    assert charts.team_chart("en", two, 12) != charts.team_chart("en", two, 24)


async def test_charts_drawn_at_once_do_not_mix(real_catalog: Catalog, fixed_rates: Rates) -> None:
    rows, months = _rows("Germany 2 × 80k, Spain 1 × 50k", real_catalog, fixed_rates)
    expected = {lang: charts.team_chart(lang, rows, months) for lang in ("en", "bg")}
    langs = ["en", "bg"] * 4
    drawn = await asyncio.gather(*(asyncio.to_thread(charts.team_chart, lang, rows, months) for lang in langs))  # type: ignore[arg-type]
    assert drawn == [expected[lang] for lang in langs]


def test_html_never_reaches_the_picture() -> None:
    assert charts._plain("💡 <b>EOR</b> saves <i>~€1</i>") == "💡 EOR saves ~€1"


def test_chart_verdicts(testland: Country, fixed_rates: Rates, monkeypatch: pytest.MonkeyPatch) -> None:
    # The verdict line agrees with the caption: a tie is a tie, a win names the winner.
    said: list[str] = []
    real_t = charts.t
    monkeypatch.setattr(charts, "t", lambda lang, key, **kw: said.append(key) or real_t(lang, key, **kw))
    ctx = replies.Context(Catalog([testland], _eor()), fixed_rates, TODAY)
    for count, months, verdict in [
        (1, 12, "chart.even"),
        (1, 6, "chart.eor_saves"),
        (50, 36, "chart.entities_save_one"),
    ]:
        said.clear()
        team = Team((Member(testland, count, Decimal(48_000), "EUR"),), months)
        charts.team_chart("en", replies.team_rows(team, ctx), months)
        assert verdict in said, (count, months)


def _eor() -> EorPricing:
    return EorPricing(provider="Deel", monthly_fee=Decimal(550), currency="EUR", source="https://www.deel.com/pricing/",
                      checked_at=TODAY, note="list price")  # type: ignore[arg-type]  # fmt: skip
