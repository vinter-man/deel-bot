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
from pathlib import Path
from typing import Any

from aiogram.types import InlineKeyboardMarkup

from deel_advisor import catalog, replies
from deel_advisor.bot import keyboards as kb
from deel_advisor.bot.handlers import error_text, render
from deel_advisor.fx import bundled_rates
from deel_advisor.i18n import Lang, t
from deel_advisor.parser import ParseError, find_country, parse

OUT = Path(__file__).resolve().parent.parent / "docs" / "remotion" / "src" / "shots.json"
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
        "plan": [{"out": "Germany 80k 3 people"}, {"in": _reply(ctx, lang, "Germany 80k 3 people")}],
        # The demo GIF taps "24 mo" on the reply above; this is what the bot edits it into.
        "plan24": [{"out": "Germany 80k 3 people"}, {"in": _reply(ctx, lang, "Germany 80k 3 people 24 months")}],
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


def main() -> int:
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
