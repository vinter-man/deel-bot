"""Writes the bot's real replies to docs/remotion/src/shots.json for the README screenshots.

    uv run python scripts/export_shots.py && (cd docs/remotion && npm run build)

Each shot is produced by the same functions the handlers call — parser, calculation, rendering,
keyboards — against the bundled data and FX snapshot, so the screenshots cannot drift from what
the bot actually says. Only the clock is fixed, to keep the output reproducible.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from aiogram.types import InlineKeyboardMarkup

from deel_advisor import calc, catalog, replies
from deel_advisor.bot import keyboards as kb
from deel_advisor.bot.handlers import error_text, render
from deel_advisor.fx import bundled_rates
from deel_advisor.i18n import Lang, t
from deel_advisor.parser import ParseError, find_country, parse

OUT = Path(__file__).resolve().parent.parent / "docs" / "remotion" / "src" / "shots.json"
BANNER_OUT = OUT.with_name("banner.json")
# The banner's chart and the README's lead case: a small team spread over four countries.
TEAM = "Germany 2 UK 1 Spain 1 Poland 1 70k"
TEAM_MONTHS = 24
TODAY = date(2026, 10, 29)


def _keys(markup: InlineKeyboardMarkup | None) -> list[list[str]]:
    return [[button.text for button in row] for row in markup.inline_keyboard] if markup else []


def _reply(ctx: replies.Context, lang: Lang, text: str) -> dict[str, Any]:
    currencies = {"EUR", *ctx.rates.per_eur}
    try:
        query = parse(text, ctx.catalog.index, currencies)
    except ParseError as error:
        return {"html": error_text(lang, error, ctx.catalog, "usage.free"), "keyboard": []}
    body, markup = render(query, lang, ctx)
    return {"html": body, "keyboard": _keys(markup)}


def build() -> dict[str, Any]:
    ctx = replies.Context(catalog.load(), bundled_rates(), TODAY)
    lang: Lang = "en"
    countries = replies.countries_list(lang, ctx.catalog)
    poland = find_country("Poland", ctx.catalog.index)
    return {
        "start": [
            {"out": "/start"},
            {"in": {"html": t(lang, "lang.prompt"), "keyboard": _keys(kb.languages())}},
            {"in": {"html": t(lang, "start", countries=countries), "keyboard": _keys(kb.start_examples(lang))}},
        ],
        "team": [{"out": TEAM}, {"in": _reply(ctx, lang, TEAM)}],
        # The demo GIF taps "24 mo" on the reply above; this is what the bot edits it into.
        "team24": [{"out": TEAM}, {"in": _reply(ctx, lang, f"{TEAM} {TEAM_MONTHS} months")}],
        "plan": [{"out": "Germany 80k 2 people"}, {"in": _reply(ctx, lang, "Germany 80k 2 people")}],
        # And the other side of the break-even: a team big enough for its own entity.
        "scale": [{"out": "Germany 80k 10 people"}, {"in": _reply(ctx, lang, "Germany 80k 10 people")}],
        "cost": [{"out": "/cost Bulgaria 60000 EUR"}, {"in": _reply(ctx, lang, "Bulgaria 60000 EUR")}],
        "compare": [{"out": "UK vs Poland 50k GBP"}, {"in": _reply(ctx, lang, "UK vs Poland 50k GBP")}],
        "sources": [
            {"out": "/sources Poland"},
            {"in": {"html": replies.sources(lang, poland, ctx), "keyboard": []}},
        ],
        "errors": [
            {"out": "Germny 80k"},
            {"in": _reply(ctx, lang, "Germny 80k")},
            {"out": "Germany"},
            {"in": _reply(ctx, lang, "Germany")},
            {"out": "Spain 50k 0 people"},
            {"in": _reply(ctx, lang, "Spain 50k 0 people")},
        ],
        "de": [
            {"out": "Spanien 50k 3 Personen 24 Monate"},
            {"in": _reply(ctx, "de", "Spanien 50k 3 Personen 24 Monate")},
        ],
    }


def banner() -> dict[str, Any]:
    """Cumulative EOR fees and own-entity costs for the README team, month by month.

    Each point is the bot's own calculation for that horizon, summed over the countries in EUR
    (so the entity line includes closing each entity at that month, as /team does); month 0 is
    what the entities cost before anyone is paid.
    """
    ctx = replies.Context(catalog.load(), bundled_rates(), TODAY)
    query = parse(TEAM, ctx.catalog.index, {"EUR", *ctx.rates.per_eur})
    eor = [Decimal(0)] * (TEAM_MONTHS + 1)
    entity = [Decimal(0)] * (TEAM_MONTHS + 1)
    for country, count in zip(query.countries, query.counts, strict=True):
        salary = ctx.rates.convert(query.salary, "EUR", country.currency)
        fee, payroll = replies.eor_fee(country, ctx), replies.payroll_fee(country, ctx)
        for month in range(1, TEAM_MONTHS + 1):
            result = calc.plan(country, salary, fee, count, month, payroll)
            eor[month] += ctx.rates.convert(result.eor_fees, country.currency, "EUR")
            entity[month] += ctx.rates.convert(result.entity_overhead, country.currency, "EUR")
        first = calc.entity_cost(country, payroll)
        entity[0] += ctx.rates.convert(first.setup + first.exit, country.currency, "EUR")
    return {
        "team": " · ".join(
            f"{c.country.replace('United Kingdom', 'UK')} {n}"
            for c, n in zip(query.countries, query.counts, strict=True)
        ),
        "people": query.people,
        "entities": len(query.countries),
        "salary": int(query.salary),
        "months": TEAM_MONTHS,
        "fee": round(replies.eor_fee(query.countries[0], ctx)),
        "eor": [round(v) for v in eor],
        "entity": [round(v) for v in entity],
        "saving": round(entity[-1] - eor[-1]),
    }


def main() -> int:
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    BANNER_OUT.write_text(json.dumps(banner(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} and {BANNER_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
