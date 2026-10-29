"""Telegram handlers: thin glue between aiogram, the parser and `replies`.

Each handler receives `services` and `lang` through aiogram's dependency injection
(`dp["services"]` and `LangMiddleware`), so tests drive the real dispatcher with fakes.
"""

from __future__ import annotations

import contextlib
import html
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from aiogram import BaseMiddleware, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, ErrorEvent, InlineKeyboardMarkup, Message, TelegramObject, User

from deel_advisor import replies
from deel_advisor.bot import keyboards as kb
from deel_advisor.catalog import Catalog
from deel_advisor.fx import FxCache
from deel_advisor.i18n import LANGS, Lang, pick_lang, t
from deel_advisor.models import Country
from deel_advisor.money import from_minor, to_minor
from deel_advisor.parser import MAX_MONTHS, Kind, ParseError, Query, build_query, find_country, parse
from deel_advisor.prefs import LanguageStore
from deel_advisor.stats import Stats

log = logging.getLogger(__name__)
router = Router(name="advisor")


def _today() -> date:
    return datetime.now(UTC).date()


@dataclass
class Services:
    catalog: Catalog
    fx: FxCache
    prefs: LanguageStore
    stats: Stats = field(default_factory=Stats)
    owner_id: int | None = None
    clock: Callable[[], date] = _today

    def context(self) -> replies.Context:
        return replies.Context(self.catalog, self.fx.rates, self.clock())


class LangMiddleware(BaseMiddleware):
    """Puts the user's language into `data["lang"]`: their pick, else their Telegram app's."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        services: Services = data["services"]
        user: User | None = data.get("event_from_user")
        lang: Lang = "en"
        if user is not None:
            lang = await services.prefs.get(user.id) or pick_lang(user.language_code)
        data["lang"] = lang
        return await handler(event, data)


# --- rendering a query --------------------------------------------------------------------


def error_text(lang: Lang, error: ParseError, catalog: Catalog, usage: str | None) -> str:
    # The params echo what the user typed, so they are escaped before going into HTML.
    params = {name: html.escape(value) for name, value in error.params.items()}
    key = f"err.{error.code}"
    if error.code == "unknown_word" and params.get("suggestion"):
        key = "err.unknown_word_suggest"
    else:
        params.pop("suggestion", None)
    if error.code == "no_country":
        params["countries"] = replies.countries_list(lang, catalog)
    text = t(lang, key, **params)
    # These already carry their own example or a list of what is valid.
    if usage and error.code not in ("unknown_word", "unknown_currency", "no_salary", "no_country"):
        text += "\n" + t(lang, usage)
    elif error.code == "unknown_word":
        text += "\n" + replies.countries_list(lang, catalog)
    return text


def render(query: Query, lang: Lang, ctx: replies.Context) -> tuple[str, InlineKeyboardMarkup]:
    first = query.countries[0]
    cur = query.currency or first.currency
    minor = to_minor(query.salary)
    if query.kind == "cost":
        return replies.cost(lang, query, ctx), kb.after_cost(lang, first.code, cur, minor)
    if query.kind == "plan":
        cb = kb.PlanCb(code=first.code, cur=cur, minor=minor, people=query.people, months=query.months)
        return replies.plan(lang, query, ctx), kb.after_plan(lang, cb)
    return replies.compare(lang, query, ctx), kb.after_compare(lang, *query.countries)


# Telegram's limit is 4096 characters of visible text; markup does not count, so splitting the
# raw HTML at this length is conservative. Blocks are separated by blank lines and every tag
# opens and closes inside its block, so a split there never breaks the markup.
MESSAGE_LIMIT = 4096


def split_message(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    parts: list[str] = []
    for block in text.split("\n\n"):
        if parts and len(parts[-1]) + 2 + len(block) <= limit:
            parts[-1] += "\n\n" + block
        else:
            parts.append(block)
    return parts


async def _answer_text(message: Message, text: str | None, kind: Kind | None, services: Services, lang: Lang) -> None:
    usage = f"usage.{kind}" if kind else "usage.free"
    if not text or not text.strip():
        await message.answer(t(lang, usage))
        return
    try:
        query = parse(text, services.catalog.index, _currencies(services), kind, in_eur=_in_eur(services))
        body, markup = render(query, lang, services.context())
    except ParseError as error:
        services.stats.hit(f"error.{error.code}")
        await message.answer(error_text(lang, error, services.catalog, usage))
        return
    await message.answer(body, reply_markup=markup)


def _currencies(services: Services) -> set[str]:
    return {"EUR", *services.fx.rates.per_eur}


def _in_eur(services: Services) -> Callable[[Decimal, str], Decimal]:
    rates = services.fx.rates
    return lambda amount, currency: rates.convert(amount, currency, "EUR")


# --- commands -----------------------------------------------------------------------------


@router.message(CommandStart())
async def start(message: Message, services: Services) -> None:
    services.stats.hit("start")
    await message.answer(t("en", "lang.prompt"), reply_markup=kb.languages())


@router.message(Command("lang"))
async def lang_cmd(message: Message, services: Services) -> None:
    services.stats.hit("lang")
    await message.answer(t("en", "lang.prompt"), reply_markup=kb.languages())


@router.message(Command("help"))
async def help_cmd(message: Message, services: Services, lang: Lang) -> None:
    services.stats.hit("help")
    await message.answer(t(lang, "help", countries=replies.countries_list(lang, services.catalog)))


@router.message(Command("cost"))
async def cost_cmd(message: Message, command: CommandObject, services: Services, lang: Lang) -> None:
    services.stats.hit("cost")
    await _answer_text(message, command.args, "cost", services, lang)


@router.message(Command("plan"))
async def plan_cmd(message: Message, command: CommandObject, services: Services, lang: Lang) -> None:
    services.stats.hit("plan")
    await _answer_text(message, command.args, "plan", services, lang)


@router.message(Command("compare"))
async def compare_cmd(message: Message, command: CommandObject, services: Services, lang: Lang) -> None:
    services.stats.hit("compare")
    await _answer_text(message, command.args, "compare", services, lang)


@router.message(Command("sources"))
async def sources_cmd(message: Message, command: CommandObject, services: Services, lang: Lang) -> None:
    services.stats.hit("sources")
    if not command.args:
        await message.answer(t(lang, "usage.sources"))
        return
    try:
        country = find_country(command.args, services.catalog.index)
    except ParseError as error:
        await message.answer(error_text(lang, error, services.catalog, "usage.sources"))
        return
    for part in split_message(replies.sources(lang, country, services.context())):
        await message.answer(part)


@router.message(Command("stats"))
async def stats_cmd(message: Message, services: Services, lang: Lang) -> None:
    if message.from_user is None or message.from_user.id != services.owner_id:
        return  # not a public command: stay silent rather than confirm it exists
    since = services.stats.since.strftime("%Y-%m-%d %H:%M UTC")
    await message.answer(t(lang, "stats", since=since, lines="\n".join(services.stats.lines()) or "—"))


@router.message(F.text.startswith("/"))
async def unknown_command(message: Message, services: Services, lang: Lang) -> None:
    services.stats.hit("unknown_command")
    await message.answer(t(lang, "usage.free"))


@router.message(F.text)
async def free_text(message: Message, services: Services, lang: Lang) -> None:
    services.stats.hit("free_text")
    await _answer_text(message, message.text, None, services, lang)


# --- buttons ------------------------------------------------------------------------------


def _country(services: Services, code: str) -> Country:
    country = services.catalog.by_code(code)
    if country is None:
        raise ParseError("stale_button")
    return country


def _button_query(
    services: Services,
    kind: Kind,
    codes: tuple[str, ...],
    cur: str,
    minor: int,
    people: int = 1,
    months: int = 12,
) -> Query:
    """A query rebuilt from callback data, validated exactly like a typed one."""
    if cur not in _currencies(services):
        raise ParseError("stale_button")
    countries = tuple(_country(services, code) for code in codes)
    return build_query(
        kind, countries, from_minor(minor), currency=cur, people=people, months=months, in_eur=_in_eur(services)
    )


async def _send_or_edit(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup, edit: bool) -> None:
    message = callback.message
    if edit and isinstance(message, Message):
        try:
            await message.edit_text(text, reply_markup=markup)
        except TelegramBadRequest as error:
            # Tapping the button that is already selected re-renders the same text.
            if "message is not modified" not in str(error):
                raise
        return
    if isinstance(message, Message):
        await message.answer(text, reply_markup=markup)


async def _button_error(callback: CallbackQuery, lang: Lang, error: ParseError) -> None:
    # A button only carries values we produced, so a failure means old or forged data.
    log.info("rejected callback data (%s)", error.code)
    await callback.answer(t(lang, "err.stale_button"), show_alert=True)


@router.callback_query(kb.LangCb.filter())
async def on_lang(callback: CallbackQuery, callback_data: kb.LangCb, services: Services) -> None:
    lang = next((code for code in LANGS if code == callback_data.lang), None)
    if lang is None:
        await callback.answer()
        return
    services.stats.hit(f"lang.{lang}")
    await services.prefs.set(callback.from_user.id, lang)
    await callback.answer(t(lang, "lang.set"))
    countries = replies.countries_list(lang, services.catalog)
    await _send_or_edit(callback, t(lang, "start", countries=countries), kb.start_examples(lang), edit=True)


@router.callback_query(kb.CostCb.filter())
async def on_cost(callback: CallbackQuery, callback_data: kb.CostCb, services: Services, lang: Lang) -> None:
    services.stats.hit("button.cost")
    try:
        query = _button_query(services, "cost", (callback_data.code,), callback_data.cur, callback_data.minor)
    except ParseError as error:
        await _button_error(callback, lang, error)
        return
    await callback.answer()
    await _send_or_edit(callback, *render(query, lang, services.context()), edit=False)


@router.callback_query(kb.PickCompareCb.filter())
async def on_pick_compare(
    callback: CallbackQuery, callback_data: kb.PickCompareCb, services: Services, lang: Lang
) -> None:
    services.stats.hit("button.pick_compare")
    try:
        country = _country(services, callback_data.code)
    except ParseError as error:
        await _button_error(callback, lang, error)
        return
    others = [c for c in services.catalog.countries if c.code != country.code]
    markup = kb.pick_country(lang, others, country.code, callback_data.cur, callback_data.minor)
    await callback.answer()
    text = t(lang, "pick.country", country=replies.country_name(lang, country))
    await _send_or_edit(callback, text, markup, edit=False)


@router.callback_query(kb.CompareCb.filter())
async def on_compare(callback: CallbackQuery, callback_data: kb.CompareCb, services: Services, lang: Lang) -> None:
    services.stats.hit("button.compare")
    codes = (callback_data.a, callback_data.b)
    try:
        query = _button_query(services, "compare", codes, callback_data.cur, callback_data.minor)
    except ParseError as error:
        await _button_error(callback, lang, error)
        return
    await callback.answer()
    await _send_or_edit(callback, *render(query, lang, services.context()), edit=True)


@router.callback_query(kb.PickPeopleCb.filter())
async def on_pick_people(
    callback: CallbackQuery, callback_data: kb.PickPeopleCb, services: Services, lang: Lang
) -> None:
    services.stats.hit("button.pick_people")
    try:
        _country(services, callback_data.code)
    except ParseError as error:
        await _button_error(callback, lang, error)
        return
    cb = callback_data
    if not 1 <= cb.months <= MAX_MONTHS:
        await _button_error(callback, lang, ParseError("stale_button"))
        return
    markup = kb.pick_people(cb.code, cb.cur, cb.minor, months=cb.months)
    await callback.answer()
    await _send_or_edit(callback, t(lang, "pick.people"), markup, edit=False)


@router.callback_query(kb.PlanCb.filter())
async def on_plan(callback: CallbackQuery, callback_data: kb.PlanCb, services: Services, lang: Lang) -> None:
    services.stats.hit("button.plan")
    cb = callback_data
    try:
        query = _button_query(services, "plan", (cb.code,), cb.cur, cb.minor, cb.people, cb.months)
    except ParseError as error:
        await _button_error(callback, lang, error)
        return
    await callback.answer()
    await _send_or_edit(callback, *render(query, lang, services.context()), edit=True)


@router.callback_query(kb.SourcesCb.filter())
async def on_sources(callback: CallbackQuery, callback_data: kb.SourcesCb, services: Services, lang: Lang) -> None:
    services.stats.hit("button.sources")
    try:
        country = _country(services, callback_data.code)
    except ParseError as error:
        await _button_error(callback, lang, error)
        return
    await callback.answer()
    if isinstance(callback.message, Message):
        for part in split_message(replies.sources(lang, country, services.context())):
            await callback.message.answer(part)


@router.callback_query()
async def on_unknown_button(callback: CallbackQuery, lang: Lang) -> None:
    await callback.answer(t(lang, "err.stale_button"), show_alert=True)


@router.errors()
async def on_error(event: ErrorEvent, **data: Any) -> bool:
    # The update id, never its content: message text is exactly what must not reach the log.
    log.error(
        "update %s failed: %s",
        event.update.update_id,
        type(event.exception).__name__,
        exc_info=(type(event.exception), event.exception, event.exception.__traceback__),
    )
    # Tell the user rather than leave them waiting (or a button spinning). Best effort only:
    # if Telegram itself is what failed, this fails too, and that is already logged.
    # aiogram does not pass middleware data to error handlers, so the language is looked up again.
    update = event.update
    source = update.callback_query or update.message
    user = source.from_user if source is not None else None
    services: Services | None = data.get("services")
    lang: Lang = "en"
    if user is not None:
        stored = await services.prefs.get(user.id) if services is not None else None
        lang = stored or pick_lang(user.language_code)
    with contextlib.suppress(TelegramAPIError):
        if event.update.callback_query is not None:
            await event.update.callback_query.answer(t(lang, "err.internal"), show_alert=True)
        elif event.update.message is not None:
            await event.update.message.answer(t(lang, "err.internal"))
    return True
