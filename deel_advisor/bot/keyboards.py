"""Inline keyboards and the callback data behind them.

Callback data comes back from the client and Telegram does not check it against the message
that carried the button, so every field is re-validated before use (`handlers._button_query`).
The salary travels in minor units of the currency it was typed in: an integer survives the
round trip through a 64-byte string exactly, a Decimal's repr would not be guaranteed to.
"""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from deel_advisor.i18n import COUNTRY_NAMES, LANG_NAMES, LANGS, Lang, t
from deel_advisor.models import Country
from deel_advisor.replies import country_name

PEOPLE_CHOICES = (2, 3, 5, 10, 25, 50)
MONTH_CHOICES = (6, 12, 24, 36)


class LangCb(CallbackData, prefix="lang"):
    lang: str


class CostCb(CallbackData, prefix="cost"):
    code: str
    cur: str
    minor: int


class PickCompareCb(CallbackData, prefix="pc"):
    code: str
    cur: str
    minor: int


class CompareCb(CallbackData, prefix="cmp"):
    a: str
    b: str
    cur: str
    minor: int


class PickPeopleCb(CallbackData, prefix="pp"):
    code: str
    cur: str
    minor: int
    # The horizon to keep when the team size changes (12 when coming from a /cost reply).
    months: int


class PlanCb(CallbackData, prefix="pln"):
    code: str
    cur: str
    minor: int
    people: int
    months: int


class SourcesCb(CallbackData, prefix="src"):
    code: str


class TeamCb(CallbackData, prefix="tm"):
    # A team with a salary per country does not fit in 64 bytes; the button carries the key of
    # the team in the bot's TeamStore instead (handlers.py), and the horizon to show.
    key: str
    months: int


def languages() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for lang in LANGS:
        builder.button(text=LANG_NAMES[lang], callback_data=LangCb(lang=lang))
    builder.adjust(3, 2)
    return builder.as_markup()


# The team on the /start button: a fixed key the store knows from startup (handlers.TeamStore).
EXAMPLE_TEAM_TEXT = "Germany 2 × 80k, UK 1 × £60k, Spain 1 × 50k, Poland 1 × 200k zł"
EXAMPLE_TEAM_LABEL = "🇩🇪 2 · 🇬🇧 1 · 🇪🇸 1 · 🇵🇱 1"
EXAMPLE_TEAM_CB = TeamCb(key="example", months=12)


def start_examples(lang: Lang) -> InlineKeyboardMarkup:
    """Two taps to a real answer, for whoever opens the bot from a README link: a team over four
    countries, two hires in Germany, a first hire in the UK — each a case the EOR is made for."""
    names = COUNTRY_NAMES[lang]
    de, uk = names.get("DE", "Germany"), names.get("GB", "United Kingdom")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🌍 {EXAMPLE_TEAM_LABEL}",
                                  callback_data=EXAMPLE_TEAM_CB.pack())],
            [InlineKeyboardButton(text=f"🇩🇪 {de} · €80k · 👥 2",
                                  callback_data=PlanCb(code="DE", cur="EUR", minor=8_000_000, people=2,
                                                       months=12).pack())],
            [InlineKeyboardButton(text=f"🇬🇧 {uk} · £60k · 👥 1",
                                  callback_data=PlanCb(code="GB", cur="GBP", minor=6_000_000, people=1,
                                                       months=12).pack())],
        ]
    )  # fmt: skip


def after_cost(lang: Lang, code: str, cur: str, minor: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn.compare"),
                                  callback_data=PickCompareCb(code=code, cur=cur, minor=minor).pack())],
            [InlineKeyboardButton(text=t(lang, "btn.plan"),
                                  callback_data=PickPeopleCb(code=code, cur=cur, minor=minor, months=12).pack())],
            [InlineKeyboardButton(text=t(lang, "btn.sources"), callback_data=SourcesCb(code=code).pack())],
        ]
    )  # fmt: skip


def pick_country(lang: Lang, others: list[Country], code: str, cur: str, minor: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for other in others:
        builder.button(
            text=f"{other.flag} {country_name(lang, other)}",
            callback_data=CompareCb(a=code, b=other.code, cur=cur, minor=minor),
        )
    builder.adjust(2)
    return builder.as_markup()


def pick_people(code: str, cur: str, minor: int, months: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for n in PEOPLE_CHOICES:
        builder.button(text=str(n), callback_data=PlanCb(code=code, cur=cur, minor=minor, people=n, months=months))
    builder.adjust(3)
    return builder.as_markup()


def after_plan(lang: Lang, cb: PlanCb) -> InlineKeyboardMarkup:
    months = [
        InlineKeyboardButton(
            text=("• " if n == cb.months else "") + t(lang, "btn.months", n=n),
            callback_data=PlanCb(code=cb.code, cur=cb.cur, minor=cb.minor, people=cb.people, months=n).pack(),
        )
        for n in MONTH_CHOICES
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            months,
            [InlineKeyboardButton(text=t(lang, "btn.plan"),
                                  callback_data=PickPeopleCb(code=cb.code, cur=cb.cur, minor=cb.minor,
                                                             months=cb.months).pack())],
            [InlineKeyboardButton(text=t(lang, "btn.compare"),
                                  callback_data=PickCompareCb(code=cb.code, cur=cb.cur, minor=cb.minor).pack())],
            [InlineKeyboardButton(text=t(lang, "btn.sources"), callback_data=SourcesCb(code=cb.code).pack())],
        ]
    )  # fmt: skip


def after_team(lang: Lang, cb: TeamCb) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=("• " if n == cb.months else "") + t(lang, "btn.months", n=n),
                callback_data=TeamCb(key=cb.key, months=n).pack(),
            )
            for n in MONTH_CHOICES
        ]]
    )  # fmt: skip


def after_compare(lang: Lang, first: Country, second: Country) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{t(lang, 'btn.sources')} {first.flag}",
                                     callback_data=SourcesCb(code=first.code).pack()),
                InlineKeyboardButton(text=f"{t(lang, 'btn.sources')} {second.flag}",
                                     callback_data=SourcesCb(code=second.code).pack()),
            ]
        ]
    )  # fmt: skip
