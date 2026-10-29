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

from deel_advisor import catalog, charts, replies
from deel_advisor.bot import keyboards as kb
from deel_advisor.bot.handlers import error_text
from deel_advisor.fx import bundled_rates
from deel_advisor.i18n import Lang, t
from deel_advisor.parser import ParseError, find_country, parse

REMOTION = Path(__file__).resolve().parent.parent / "docs" / "remotion"
OUT = REMOTION / "src" / "shots.json"
# Team charts go where Remotion serves static files from (staticFile in shots.tsx).
PUBLIC = REMOTION / "public"
# The README's lead case: a small team spread over four countries, a salary for each.
TEAM = kb.EXAMPLES[0].text
ONE = kb.EXAMPLES[1].text
# The horizon the demo GIF taps.
TEAM_MONTHS = 6
TODAY = date(2026, 10, 29)


def _keys(markup: InlineKeyboardMarkup | None) -> list[list[str]]:
    return [[button.text for button in row] for row in markup.inline_keyboard] if markup else []


def _reply(ctx: replies.Context, lang: Lang, text: str, photo: str | None = None) -> dict[str, Any]:
    """The bot's answer to `text`: its chart is written to public/`photo`, as the bot sends it."""
    try:
        team = parse(text, ctx.catalog.index, {"EUR", *ctx.rates.per_eur})
    except ParseError as error:
        return {"html": error_text(lang, error, ctx.catalog, "usage.team"), "keyboard": []}
    if photo is None:
        raise ValueError(f"{text!r} is answered with a chart: give it a file name")
    PUBLIC.mkdir(exist_ok=True)
    (PUBLIC / photo).write_bytes(charts.team_chart(lang, replies.team_rows(team, ctx), team.months))
    markup = kb.after_team(lang, kb.TeamCb(key="readme", months=team.months), [m.country for m in team.members])
    return {"html": replies.team(lang, team, ctx, breakdown=False), "keyboard": _keys(markup), "photo": photo}


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
        "team": [{"out": TEAM}, {"in": _reply(ctx, lang, TEAM, "team.png")}],
        # The demo GIF taps "6 mo" on the reply above; this is what the bot edits it into.
        "team6": [{"out": TEAM}, {"in": _reply(ctx, lang, f"{TEAM} {TEAM_MONTHS} months", "team6.png")}],
        "one": [{"out": ONE}, {"in": _reply(ctx, lang, ONE, "one.png")}],
        "sources": [
            {"out": "/sources Poland"},
            {"in": {"html": replies.sources(lang, poland, ctx), "keyboard": []}},
        ],
        "errors": [
            {"out": "Germny 2 × 80k"},
            {"in": _reply(ctx, lang, "Germny 2 × 80k")},
            {"out": "Germany 2 × 80k, Spain 1"},
            {"in": _reply(ctx, lang, "Germany 2 × 80k, Spain 1")},
            {"out": "Spain 0 × 50k"},
            {"in": _reply(ctx, lang, "Spain 0 × 50k")},
        ],
    }


def main() -> int:
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
