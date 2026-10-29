"""Wires the bot together and runs it, with two background jobs beside the polling loop.

- `daily`: refresh the ECB rates and re-check the data's freshness, once at start and then
  every day shortly after the ECB publishes.
- `heartbeat`: prove the bot can still reach Telegram, for the container healthcheck.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

import httpx
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand

from deel_advisor import catalog, freshness
from deel_advisor.bot.handlers import LangMiddleware, Services, router
from deel_advisor.config import Settings
from deel_advisor.fx import FxCache
from deel_advisor.i18n import LANGS, Lang
from deel_advisor.prefs import LanguageStore

log = logging.getLogger(__name__)

# The ECB publishes around 16:00 CET; 15:30 UTC is after that in both winter and summer time.
DAILY_AT = time(15, 30, tzinfo=UTC)
HEARTBEAT_EVERY = 60

COMMANDS: dict[Lang, list[tuple[str, str]]] = {
    "en": [("cost", "Employer cost with a breakdown"), ("plan", "EOR vs own entity, break-even"),
           ("compare", "Two countries side by side"), ("sources", "Where the figures come from"),
           ("help", "How to use the bot"), ("lang", "Change language")],
    "uk": [("cost", "Вартість роботодавця з розбивкою"), ("plan", "EOR проти юрособи, беззбитковість"),
           ("compare", "Дві країни поруч"), ("sources", "Звідки цифри"),
           ("help", "Як користуватися"), ("lang", "Змінити мову")],
    "ru": [("cost", "Стоимость работодателя с разбивкой"), ("plan", "EOR против юрлица, безубыточность"),
           ("compare", "Две страны рядом"), ("sources", "Откуда цифры"),
           ("help", "Как пользоваться"), ("lang", "Сменить язык")],
}  # fmt: skip


def seconds_until(now: datetime, at: time) -> float:
    """Seconds from `now` to the next `at` (UTC), never zero: a job that just ran waits a day."""
    target = datetime.combine(now.date(), at)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def build_dispatcher(services: Services) -> Dispatcher:
    dp = Dispatcher()
    dp["services"] = services
    dp.message.outer_middleware(LangMiddleware())
    dp.callback_query.outer_middleware(LangMiddleware())
    dp.include_router(router)
    return dp


async def daily_check(services: Services, bot: Bot, reported: set[str]) -> None:
    """Refresh FX, re-check the data, and tell the owner about problems they have not heard of."""
    await services.fx.refresh()
    today = services.clock()
    problems = []
    for country in services.catalog.countries:
        state = freshness.check(country, today)
        if state.outdated_year:
            problems.append(f"{country.code}: data is for {country.year}")
        if state.unchecked_days:
            problems.append(f"{country.code}: official figures unchecked for {state.unchecked_days} days")
        problems += [f"{country.code}: Deel guide differs on {m.key}" for m in state.mismatches]
    fx_age = services.fx.age_days(today)
    if fx_age > 4:
        problems.append(f"FX rates are {fx_age} days old")
    for problem in problems:
        log.warning("data check: %s", problem)
    fresh = [p for p in problems if p not in reported]
    if fresh and services.owner_id:
        with contextlib.suppress(TelegramAPIError):
            await bot.send_message(services.owner_id, "Data check:\n" + "\n".join(fresh))
    reported.clear()
    reported.update(problems)


async def daily_loop(services: Services, bot: Bot) -> None:
    reported: set[str] = set()
    while True:
        try:
            await daily_check(services, bot, reported)
        except Exception:  # a background job must outlive any one bad day
            log.exception("daily check failed")
        await asyncio.sleep(seconds_until(datetime.now(UTC), DAILY_AT))


async def heartbeat(bot: Bot, path: Path) -> bool:
    """Touch the heartbeat file if Telegram answers; the healthcheck reads its age."""
    try:
        await bot.get_me()
        await asyncio.to_thread(path.write_text, datetime.now(UTC).isoformat())
    except (TelegramAPIError, OSError) as error:
        log.warning("heartbeat failed: %s", type(error).__name__)
        return False
    return True


async def heartbeat_loop(bot: Bot, path: Path) -> None:
    while True:
        await heartbeat(bot, path)
        await asyncio.sleep(HEARTBEAT_EVERY)


async def set_commands(bot: Bot) -> None:
    for lang in LANGS:
        commands = [BotCommand(command=c, description=d) for c, d in COMMANDS[lang]]
        await bot.set_my_commands(commands, language_code=None if lang == "en" else lang)


async def run(settings: Settings) -> None:
    data = catalog.load()
    log.info("loaded %d countries: %s", len(data.countries), ", ".join(c.code for c in data.countries))
    bot = Bot(
        settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    async with httpx.AsyncClient(headers={"User-Agent": "deel-advisor-bot/1.0"}) as http:
        services = Services(
            catalog=data,
            fx=FxCache(settings.data_dir / "fx.json", http),
            prefs=LanguageStore(settings.data_dir),
            owner_id=settings.owner_id,
        )
        dp = build_dispatcher(services)
        await set_commands(bot)
        jobs = [
            asyncio.create_task(daily_loop(services, bot), name="daily"),
            asyncio.create_task(heartbeat_loop(bot, settings.heartbeat_file), name="heartbeat"),
        ]
        try:
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        finally:
            for job in jobs:
                job.cancel()
            await asyncio.gather(*jobs, return_exceptions=True)
            await bot.session.close()
