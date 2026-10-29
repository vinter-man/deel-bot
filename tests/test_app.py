from datetime import UTC, date, datetime, time
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from aiogram.exceptions import TelegramNetworkError

from deel_advisor.bot import app
from deel_advisor.bot.handlers import Services
from deel_advisor.catalog import Catalog
from deel_advisor.fx import ECB_URL, FxCache, Rates
from deel_advisor.prefs import LanguageStore
from tests.conftest import FIXTURES


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 10, 29, 10, 0, tzinfo=UTC), 5.5 * 3600),
        (datetime(2026, 10, 29, 15, 30, tzinfo=UTC), 24 * 3600),  # just ran: wait a day, not zero
        (datetime(2026, 10, 29, 16, 0, tzinfo=UTC), 23.5 * 3600),
    ],
)
def test_seconds_until(now: datetime, expected: float) -> None:
    assert app.seconds_until(now, time(15, 30, tzinfo=UTC)) == expected


def _services(tmp_path: Path, catalog: Catalog, client: httpx.AsyncClient, today: date) -> Services:
    return Services(
        catalog=catalog,
        fx=FxCache(tmp_path / "fx.json", client),
        prefs=LanguageStore(tmp_path),
        owner_id=1,
        clock=lambda: today,
    )


async def test_daily_check_refreshes_and_reports_once(tmp_path: Path, real_catalog: Catalog) -> None:
    bot = AsyncMock()
    reported: set[str] = set()
    async with httpx.AsyncClient() as client:
        services = _services(tmp_path, real_catalog, client, date(2027, 1, 5))
        with respx.mock:
            respx.get(ECB_URL).respond(200, content=(FIXTURES / "ecb-daily.xml").read_bytes())
            await app.daily_check(services, bot, reported)
            assert bot.send_message.await_count == 1
            text = bot.send_message.await_args.args[1]
            assert "data is for 2026" in text
            assert "FX rates are 69 days old" in text  # the fixture is from 2026-10-28
            # The same problems the next day are not news.
            await app.daily_check(services, bot, reported)
            assert bot.send_message.await_count == 1


async def test_daily_check_is_quiet_when_all_is_well(tmp_path: Path, real_catalog: Catalog) -> None:
    bot = AsyncMock()
    reported: set[str] = set()
    async with httpx.AsyncClient() as client:
        services = _services(tmp_path, real_catalog, client, date(2026, 10, 29))
        services.fx.rates = Rates(date(2026, 10, 29), {"USD": Decimal(1), "GBP": Decimal(1), "PLN": Decimal(1)})
        with respx.mock:
            respx.get(ECB_URL).respond(503)
            await app.daily_check(services, bot, reported)
    mismatches = [p for p in reported if "Deel guide differs" in p]
    assert bot.send_message.await_count == (1 if mismatches else 0)
    assert all("data is for" not in p for p in reported)


async def test_heartbeat_writes_file_only_when_telegram_answers(tmp_path: Path) -> None:
    bot = AsyncMock()
    assert await app.heartbeat(bot, tmp_path / "hb")
    assert (tmp_path / "hb").read_text().startswith("20")

    bot.get_me.side_effect = TelegramNetworkError(method=AsyncMock(), message="down")
    assert not await app.heartbeat(bot, tmp_path / "hb2")
    assert not (tmp_path / "hb2").exists()


async def test_set_commands_per_language() -> None:
    bot = AsyncMock()
    await app.set_commands(bot)
    langs = [call.kwargs["language_code"] for call in bot.set_my_commands.await_args_list]
    assert langs == [None, "uk", "ru"]
