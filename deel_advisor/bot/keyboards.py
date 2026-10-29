"""Inline keyboards and the callback data behind them.

Callback data comes back from the client and Telegram does not check it against the message
that carried the button, so every field is re-validated before use (`handlers.on_team`,
`handlers.on_sources`). A team with a salary per country does not fit in 64 bytes, so its
buttons carry a short key into the bot's `TeamStore` instead of the team itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from deel_advisor.i18n import COUNTRY_NAMES, LANG_NAMES, LANGS, Lang, t
from deel_advisor.models import Country

MONTH_CHOICES = (3, 6, 12)


class LangCb(CallbackData, prefix="lang"):
    lang: str


class SourcesCb(CallbackData, prefix="src"):
    code: str


class TeamCb(CallbackData, prefix="tm"):
    key: str
    months: int


def languages() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for lang in LANGS:
        builder.button(text=LANG_NAMES[lang], callback_data=LangCb(lang=lang))
    builder.adjust(3, 2)
    return builder.as_markup()


@dataclass(frozen=True, slots=True)
class Example:
    """A team behind a /start button, under a fixed key the store knows from startup."""

    key: str
    text: str
    # The button label; {DE}, {GB}… are country names in the reader's language.
    label: str


# Each a case the EOR is made for: a team over four countries, two hires in Germany, a first
# hire in the UK.
EXAMPLES = (
    Example("ex-team", "Germany 2 × 80k, UK 1 × £60k, Spain 1 × 50k, Poland 1 × 200k zł",
            "🌍 🇩🇪 2 · 🇬🇧 1 · 🇪🇸 1 · 🇵🇱 1"),
    Example("ex-de", "Germany 2 × 80k", "🇩🇪 {DE} · 2 × €80k"),
    Example("ex-gb", "UK 1 × £60k", "🇬🇧 {GB} · 1 × £60k"),
)  # fmt: skip


def start_examples(lang: Lang) -> InlineKeyboardMarkup:
    """Two taps to a real answer, for whoever opens the bot from a README link."""
    # English names live in the country files; the labels only need these two.
    names = {"DE": "Germany", "GB": "United Kingdom", **COUNTRY_NAMES[lang]}
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=example.label.format(**names),
                                  callback_data=TeamCb(key=example.key, months=12).pack())]
            for example in EXAMPLES
        ]
    )  # fmt: skip


def after_team(lang: Lang, cb: TeamCb, countries: list[Country]) -> InlineKeyboardMarkup:
    """The horizons, then every country's sources."""
    months = [
        InlineKeyboardButton(
            text=("• " if n == cb.months else "") + t(lang, "btn.months", n=n),
            callback_data=TeamCb(key=cb.key, months=n).pack(),
        )
        for n in MONTH_CHOICES
    ]
    sources = [
        InlineKeyboardButton(text=f"📚 {country.flag}", callback_data=SourcesCb(code=country.code).pack())
        for country in countries
    ]
    return InlineKeyboardMarkup(inline_keyboard=[months, sources])
