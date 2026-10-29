"""Telegram handlers: thin glue between aiogram, the parser, `replies` and `charts`.

Each handler receives `services` and `lang` through aiogram's dependency injection
(`dp["services"]` and `LangMiddleware`), so tests drive the real dispatcher with fakes.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import html
import logging
import re
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from aiogram import BaseMiddleware, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    ErrorEvent,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
    TelegramObject,
    User,
)

from deel_advisor import charts, replies
from deel_advisor.bot import keyboards as kb
from deel_advisor.catalog import Catalog
from deel_advisor.fx import FxCache
from deel_advisor.i18n import LANGS, Lang, pick_lang, t
from deel_advisor.models import Country
from deel_advisor.parser import ParseError, Team, check_team, find_country, parse
from deel_advisor.prefs import LanguageStore
from deel_advisor.stats import Stats

log = logging.getLogger(__name__)


def _today() -> date:
    return datetime.now(UTC).date()


class TeamStore:
    """Teams behind the horizon buttons, by a short key derived from the team itself.

    A team's salaries and currencies do not fit in 64 bytes of callback data. The store holds
    numbers only (countries, head counts, salaries) — nothing about who asked — and the most
    recent `limit` of them; a button whose team has been evicted, or that predates a restart,
    gets the usual "old message" answer.
    """

    def __init__(self, limit: int = 2000) -> None:
        self._teams: OrderedDict[str, Team] = OrderedDict()
        self._limit = limit
        # Teams behind buttons the bot ships with (the /start examples): never evicted.
        self._fixed: dict[str, Team] = {}

    def fix(self, key: str, team: Team) -> None:
        self._fixed[key] = team

    @staticmethod
    def key_of(team: Team) -> str:
        spec = ";".join(f"{m.country.code}{m.count}@{m.salary}{m.currency}" for m in team.members)
        return hashlib.sha256(spec.encode()).hexdigest()[:12]

    def put(self, team: Team, key: str | None = None) -> str:
        key = key or self.key_of(team)
        self._teams[key] = team
        self._teams.move_to_end(key)
        while len(self._teams) > self._limit:
            self._teams.popitem(last=False)
        return key

    def get(self, key: str) -> Team | None:
        return self._fixed.get(key) or self._teams.get(key)


@dataclass
class Services:
    catalog: Catalog
    fx: FxCache
    prefs: LanguageStore
    stats: Stats = field(default_factory=Stats)
    owner_id: int | None = None
    clock: Callable[[], date] = _today
    teams: TeamStore = field(default_factory=TeamStore)

    def __post_init__(self) -> None:
        for example in kb.EXAMPLES:
            self.teams.fix(example.key, parse(example.text, self.catalog.index, _currencies(self)))

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


# --- rendering a team ---------------------------------------------------------------------


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
    if error.code == "team_salary" and (country := catalog.by_code(error.params["country"])) is not None:
        params["country"] = replies.country_name(lang, country)
    text = t(lang, key, **params)
    # These already carry their own example or a list of what is valid.
    if usage and error.code not in ("unknown_word", "unknown_currency", "no_salary", "no_country", "team_salary"):
        text += "\n" + t(lang, usage)
    elif error.code == "unknown_word":
        text += "\n" + replies.countries_list(lang, catalog)
    return text


@dataclass(frozen=True, slots=True)
class Answer:
    text: str
    markup: InlineKeyboardMarkup
    # A picture to send with the text as its caption (team answers).
    photo: bytes | None = None


async def render_team(team: Team, lang: Lang, services: Services) -> Answer:
    """The team chart with a short caption; the full text if the chart cannot be drawn."""
    ctx = services.context()
    key = services.teams.put(team)
    markup = kb.after_team(lang, kb.TeamCb(key=key, months=team.months), [m.country for m in team.members])
    try:
        rows = replies.team_rows(team, ctx)
        photo = await asyncio.to_thread(charts.team_chart, lang, rows, team.months)
    except Exception:  # a picture is a nicety: never lose the answer over it
        log.exception("team chart failed")
        return Answer(replies.team(lang, team, ctx), markup)
    caption = replies.team(lang, team, ctx, breakdown=False)
    if _visible_length(caption) > CAPTION_LIMIT:  # a pile of warnings: the text alone, in full
        return Answer(replies.team(lang, team, ctx), markup)
    return Answer(caption, markup, photo)


# Telegram's limit on a photo caption, counted on the text as shown, without the HTML tags, and
# in UTF-16 code units: every flag and most emoji count twice.
CAPTION_LIMIT = 1024
_TAG = re.compile(r"<[^>]+>")


def _visible_length(text: str) -> int:
    return len(html.unescape(_TAG.sub("", text)).encode("utf-16-le")) // 2


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


async def _answer_text(message: Message, text: str | None, services: Services, lang: Lang) -> None:
    if not text or not text.strip():
        await message.answer(t(lang, "usage.team"))
        return
    try:
        team = parse(text, services.catalog.index, _currencies(services), in_eur=_in_eur(services))
        answer = await render_team(team, lang, services)
    except ParseError as error:
        services.stats.hit(f"error.{error.code}")
        await message.answer(error_text(lang, error, services.catalog, "usage.team"))
        return
    await _deliver(message, answer)


async def _deliver(message: Message, answer: Answer) -> None:
    if answer.photo is None:
        await message.answer(answer.text, reply_markup=answer.markup)
        return
    photo = BufferedInputFile(answer.photo, filename="team.png")
    await message.answer_photo(photo, caption=answer.text, reply_markup=answer.markup)


def _currencies(services: Services) -> set[str]:
    return {"EUR", *services.fx.rates.per_eur}


def _in_eur(services: Services) -> Callable[[Decimal, str], Decimal]:
    rates = services.fx.rates
    return lambda amount, currency: rates.convert(amount, currency, "EUR")


# --- commands -----------------------------------------------------------------------------


async def start(message: Message, services: Services) -> None:
    services.stats.hit("start")
    await message.answer(t("en", "lang.prompt"), reply_markup=kb.languages())


async def lang_cmd(message: Message, services: Services) -> None:
    services.stats.hit("lang")
    await message.answer(t("en", "lang.prompt"), reply_markup=kb.languages())


async def help_cmd(message: Message, services: Services, lang: Lang) -> None:
    services.stats.hit("help")
    await message.answer(t(lang, "help", countries=replies.countries_list(lang, services.catalog)))


async def team_cmd(message: Message, command: CommandObject, services: Services, lang: Lang) -> None:
    services.stats.hit("team")
    await _answer_text(message, command.args, services, lang)


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


async def stats_cmd(message: Message, services: Services, lang: Lang) -> None:
    if message.from_user is None or message.from_user.id != services.owner_id:
        return  # not a public command: stay silent rather than confirm it exists
    since = services.stats.since.strftime("%Y-%m-%d %H:%M UTC")
    await message.answer(t(lang, "stats", since=since, lines="\n".join(services.stats.lines()) or "—"))


async def unknown_command(message: Message, services: Services, lang: Lang) -> None:
    services.stats.hit("unknown_command")
    await message.answer(t(lang, "usage.team"))


async def not_text(message: Message, services: Services, lang: Lang) -> None:
    # A sticker, a photo, a voice note: answer with what the bot does understand, not silence.
    services.stats.hit("not_text")
    await message.answer(t(lang, "usage.team"))


async def free_text(message: Message, services: Services, lang: Lang) -> None:
    services.stats.hit("free_text")
    await _answer_text(message, message.text, services, lang)


# --- buttons ------------------------------------------------------------------------------


def _country(services: Services, code: str) -> Country:
    country = services.catalog.by_code(code)
    if country is None:
        raise ParseError("stale_button")
    return country


async def _button_error(callback: CallbackQuery, lang: Lang, error: ParseError) -> None:
    # A button only carries values we produced, so a failure means old or forged data.
    log.info("rejected callback data (%s)", error.code)
    await callback.answer(t(lang, "err.stale_button"), show_alert=True)


async def on_lang(callback: CallbackQuery, callback_data: kb.LangCb, services: Services) -> None:
    lang = next((code for code in LANGS if code == callback_data.lang), None)
    if lang is None:
        await callback.answer()
        return
    services.stats.hit(f"lang.{lang}")
    await services.prefs.set(callback.from_user.id, lang)
    await callback.answer(t(lang, "lang.set"))
    if not isinstance(callback.message, Message):
        return
    countries = replies.countries_list(lang, services.catalog)
    try:
        await callback.message.edit_text(t(lang, "start", countries=countries), reply_markup=kb.start_examples(lang))
    except TelegramBadRequest as error:
        # Tapping the language that is already picked re-renders the same text.
        if "message is not modified" not in str(error):
            raise


async def on_team(callback: CallbackQuery, callback_data: kb.TeamCb, services: Services, lang: Lang) -> None:
    services.stats.hit("button.team")
    team = services.teams.get(callback_data.key)
    if team is None:
        await _button_error(callback, lang, ParseError("stale_button"))
        return
    try:
        team = check_team(Team(team.members, callback_data.months))
    except ParseError as error:
        await _button_error(callback, lang, error)
        return
    await callback.answer()
    answer = await render_team(team, lang, services)
    message = callback.message
    if not isinstance(message, Message):
        return
    try:
        if answer.photo is not None and message.photo:
            media = InputMediaPhoto(media=BufferedInputFile(answer.photo, filename="team.png"), caption=answer.text)
            await message.edit_media(media, reply_markup=answer.markup)
        elif answer.photo is None and not message.photo:
            await message.edit_text(answer.text, reply_markup=answer.markup)
        else:
            # A chart under the /start examples' text, or the full text under a chart that could
            # not be redrawn (too long for a caption): a new message rather than a broken edit.
            await _deliver(message, answer)
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error):
            raise


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


async def on_unknown_button(callback: CallbackQuery, lang: Lang) -> None:
    await callback.answer(t(lang, "err.stale_button"), show_alert=True)


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
        stored = None
        if services is not None:
            with contextlib.suppress(Exception):  # the store may be what broke
                stored = await services.prefs.get(user.id)
        lang = stored or pick_lang(user.language_code)
    with contextlib.suppress(TelegramAPIError):
        if event.update.callback_query is not None:
            await event.update.callback_query.answer(t(lang, "err.internal"), show_alert=True)
        elif event.update.message is not None:
            await event.update.message.answer(t(lang, "err.internal"))
    return True


def create_router() -> Router:
    """A fresh router with every handler on it, in matching order: specific filters first,
    the catch-alls (any /command, any text, any button) last. A new one per dispatcher, so
    tests and tools can build as many dispatchers as they like in one process."""
    router = Router(name="advisor")
    router.message.register(start, CommandStart())
    router.message.register(lang_cmd, Command("lang"))
    router.message.register(help_cmd, Command("help"))
    router.message.register(team_cmd, Command("team"))
    router.message.register(sources_cmd, Command("sources"))
    router.message.register(stats_cmd, Command("stats"))
    router.message.register(unknown_command, F.text.startswith("/"))
    router.message.register(free_text, F.text)
    router.message.register(not_text)
    router.callback_query.register(on_lang, kb.LangCb.filter())
    router.callback_query.register(on_team, kb.TeamCb.filter())
    router.callback_query.register(on_sources, kb.SourcesCb.filter())
    router.callback_query.register(on_unknown_button)
    router.errors.register(on_error)
    return router
