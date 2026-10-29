"""The picture the bot sends with a team answer: one pair of bars per country, drawn like the
README banner — ink on paper, a pencil wobble, a monospaced hand.

Rendering is synchronous and CPU-bound; the handler runs it in a worker thread. Matplotlib is
imported here and nowhere else, with the non-interactive Agg backend, so the bot never needs a
display and a failure to draw costs the picture, not the answer.
"""

from __future__ import annotations

import io
import threading
from decimal import Decimal
from importlib import resources
from typing import Any

import matplotlib as mpl
from matplotlib import font_manager
from matplotlib.figure import Figure

from deel_advisor import i18n
from deel_advisor.i18n import Lang, t
from deel_advisor.money import format_money
from deel_advisor.replies import TEAM_CURRENCY, TeamRow, country_name

PAPER = "#F7F6F2"
INK = "#151515"
GREY = "#6E6D69"
# The pencil: bars and rule wobble a little, the same way on every render (scale, length, randomness).
SKETCH = (1.1, 90.0, 1.6)


def _register_fonts() -> str:
    """IBM Plex Mono ships with the package (OFL): Latin with diacritics and Cyrillic."""
    fonts = resources.files("deel_advisor").joinpath("fonts")
    for name in ("IBMPlexMono-Regular.ttf", "IBMPlexMono-SemiBold.ttf"):
        with resources.as_file(fonts.joinpath(name)) as path:
            font_manager.fontManager.addfont(str(path))
    return "IBM Plex Mono"


FAMILY = _register_fonts()
# rcParams are global: one chart at a time, so two answers rendering at once cannot mix styles.
_LOCK = threading.Lock()


def _plain(text: str) -> str:
    """Copy written for Telegram HTML, without its tags, for drawing."""
    for tag in ("<b>", "</b>", "<i>", "</i>"):
        text = text.replace(tag, "")
    return text


def team_chart(lang: Lang, rows: list[TeamRow], months: int) -> bytes:
    """PNG of EOR fees against own-entity costs per country, with the totals underneath."""

    def money(amount: Decimal) -> str:
        return format_money(amount, TEAM_CURRENCY, lang)

    people = sum(r.member.count for r in rows)
    total_eor = sum((r.eor for r in rows), Decimal(0))
    total_entity = sum((r.entity for r in rows), Decimal(0))
    top = float(max(max(r.eor, r.entity) for r in rows))

    style: dict[str, Any] = {
        "font.family": FAMILY,
        "font.size": 13,
        "text.color": INK,
        "axes.edgecolor": INK,
    }
    with _LOCK, mpl.rc_context(style):  # type: ignore[arg-type]  # keys checked against a Literal list
        step = 1.35  # a country label, two bars and some air
        height = 2.3 + 1.2 * len(rows)
        # A bare Figure renders through Agg and never touches pyplot's global figure registry.
        fig = Figure(figsize=(10, height), dpi=160)
        ax = fig.subplots()
        fig.patch.set_facecolor(PAPER)
        ax.set_facecolor(PAPER)

        bar = 0.26
        for n, row in enumerate(rows):
            y = (len(rows) - 1 - n) * step
            member = row.member
            label = (
                f"{country_name(lang, member.country)} · {i18n.people(lang, member.count)} × "
                f"{format_money(member.salary, member.currency, lang)}"
            )
            ax.text(0, y + 0.52, label, fontsize=13.5, fontweight="semibold", va="center")
            eor_bar = ax.barh(y + bar / 2 + 0.03, float(row.eor), height=bar, color=INK, edgecolor=INK, linewidth=1.4)
            entity_bar = ax.barh(y - bar / 2 - 0.03, float(row.entity), height=bar, color=PAPER, edgecolor=INK,
                                 linewidth=1.4, hatch="///")  # fmt: skip
            for patch in (*eor_bar, *entity_bar):
                patch.set_sketch_params(*SKETCH)
            gap = top * 0.012
            eor_note = f"{t(lang, 'chart.eor')}  {money(row.eor)}"
            entity_note = f"{t(lang, 'chart.entity')}  {money(row.entity)}"
            cheaper = f"  ← {t(lang, 'chart.cheaper')}"
            ax.text(float(row.eor) + gap, y + bar / 2 + 0.03, eor_note + (cheaper if row.eor_wins else ""),
                    va="center", fontsize=12)  # fmt: skip
            ax.text(float(row.entity) + gap, y - bar / 2 - 0.03, entity_note + ("" if row.eor_wins else cheaper),
                    va="center", fontsize=12, color=GREY if row.eor_wins else INK)  # fmt: skip

        ax.set_xlim(0, top * 1.75)
        ax.set_ylim(-0.8, (len(rows) - 1) * step + 0.75)
        ax.axis("off")
        (rule,) = ax.plot([0, top * 1.75], [-0.66, -0.66], color=INK, linewidth=1.4)  # under the rows
        rule.set_sketch_params(*SKETCH)

        title = _plain(t(lang, "chart.title", countries=len(rows), team=i18n.people(lang, people),
                         months=i18n.months(lang, months)))  # fmt: skip
        fig.text(0.04, 1 - 0.42 / height, title, fontsize=17, fontweight="semibold")
        fig.text(0.04, 1 - 0.78 / height, _plain(t(lang, "chart.subtitle")), fontsize=12, color=GREY)

        diff = abs(total_entity - total_eor)
        verdict = "chart.eor_saves" if total_eor <= total_entity else "chart.entities_save"
        fig.text(0.04, 0.42 / height,
                 _plain(t(lang, "chart.total", eor=money(total_eor), entities=len(rows), entity=money(total_entity))),
                 fontsize=13)  # fmt: skip
        fig.text(0.96, 0.42 / height, _plain(t(lang, verdict, diff=money(diff))), fontsize=15,
                 fontweight="semibold", ha="right")  # fmt: skip

        fig.subplots_adjust(left=0.04, right=0.96, top=1 - 1.15 / height, bottom=0.85 / height)
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", facecolor=PAPER)
    return buffer.getvalue()
