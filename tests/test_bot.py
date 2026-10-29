"""End to end through the real dispatcher: updates in, Bot API calls out, nothing on the network.

`FakeSession` stands in for aiogram's HTTP session, records every API method the handlers call
and answers with plausible objects, so the whole stack — middleware, filters, callback data,
parser, calculation, rendering — runs exactly as in production.
"""

from __future__ import annotations

import itertools
from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from deel_advisor.bot import keyboards as kb
from deel_advisor.bot.app import build_dispatcher
from deel_advisor.bot.handlers import Services
from deel_advisor.catalog import Catalog
from deel_advisor.fx import FxCache, Rates
from deel_advisor.prefs import LanguageStore

USER_ID = 5150
OWNER_ID = 1
TODAY = date(2026, 10, 29)


class FakeSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod[Any]] = []
        self._ids = itertools.count(1000)

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109 - aiogram's signature
        self.calls.append(method)
        if isinstance(method, SendMessage | EditMessageText):
            chat_id = method.chat_id if isinstance(method.chat_id, int) else USER_ID
            return Message(
                message_id=next(self._ids),
                date=datetime.now(UTC),
                chat=Chat(id=chat_id or USER_ID, type="private"),
                text=method.text,
            )
        return True

    async def close(self) -> None:
        pass

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:  # pragma: no cover
        raise NotImplementedError
        yield b""

    def sent(self) -> list[SendMessage | EditMessageText]:
        return [c for c in self.calls if isinstance(c, SendMessage | EditMessageText)]

    def last_text(self) -> str:
        return self.sent()[-1].text


@pytest.fixture(scope="module")
def dispatcher() -> Dispatcher:
    # The router is a module-level singleton and can be attached once; tests swap `services`.
    return build_dispatcher(services=None)  # type: ignore[arg-type]


@pytest.fixture
async def env(
    tmp_path: Path, dispatcher: Dispatcher, real_catalog: Catalog, fixed_rates: Rates
) -> AsyncGenerator[tuple[Bot, FakeSession, Services], None]:
    session = FakeSession()
    bot = Bot("42:TEST", session=session, default=DefaultBotProperties(parse_mode="HTML"))
    async with httpx.AsyncClient() as client:
        fx = FxCache(tmp_path / "fx.json", client)
        fx.rates = fixed_rates
        services = Services(real_catalog, fx, LanguageStore(tmp_path), owner_id=OWNER_ID, clock=lambda: TODAY)
        dispatcher["services"] = services
        yield bot, session, services


_update_ids: Iterator[int] = itertools.count(1)
USER = User(id=USER_ID, is_bot=False, first_name="Test", language_code="en")


def _message(text: str, user: User = USER) -> Update:
    return Update(
        update_id=next(_update_ids),
        message=Message(
            message_id=next(_update_ids),
            date=datetime.now(UTC),
            chat=Chat(id=user.id, type="private"),
            from_user=user,
            text=text,
        ),
    )


def _callback(data: str, user: User = USER) -> Update:
    origin = Message(message_id=77, date=datetime.now(UTC), chat=Chat(id=user.id, type="private"), text="…")
    return Update(
        update_id=next(_update_ids),
        callback_query=CallbackQuery(id=str(next(_update_ids)), from_user=user, chat_instance="c", data=data,
                                     message=origin),
    )  # fmt: skip


async def send(dp: Dispatcher, bot: Bot, update: Update) -> None:
    await dp.feed_update(bot, update)


async def test_start_asks_for_language_then_greets(dispatcher: Dispatcher, env: Any) -> None:
    bot, session, services = env
    await send(dispatcher, bot, _message("/start"))
    first = session.sent()[-1]
    assert "Choose your language" in first.text
    buttons = [b.callback_data for row in first.reply_markup.inline_keyboard for b in row]
    assert buttons == ["lang:en", "lang:uk", "lang:ru"]

    await send(dispatcher, bot, _callback("lang:uk"))
    assert isinstance(session.sent()[-1], EditMessageText)
    assert "Напишіть країну" in session.last_text()
    assert await services.prefs.get(USER_ID) == "uk"
    # And the next reply is in Ukrainian although the Telegram client says English.
    await send(dispatcher, bot, _message("/help"))
    assert "Команди" in session.last_text()


async def test_free_text_plan(dispatcher: Dispatcher, env: Any) -> None:
    bot, session, _ = env
    await send(dispatcher, bot, _message("Germany 80k 5 people"))
    text = session.last_text()
    assert "Germany" in text
    assert "EOR (Deel)" in text
    assert "Own entity" in text
    assert "💡" in text


async def test_cost_command_has_breakdown_and_buttons(dispatcher: Dispatcher, env: Any) -> None:
    bot, session, _ = env
    await send(dispatcher, bot, _message("/cost Bulgaria 60000 EUR"))
    reply = session.sent()[-1]
    assert "Employer cost" in reply.text
    assert reply.text.count("• ") >= 5
    data = [b.callback_data for row in reply.reply_markup.inline_keyboard for b in row]
    assert data == ["pc:BG:EUR:6000000", "pp:BG:EUR:6000000:12", "src:BG"]


async def test_compare_flow_through_buttons(dispatcher: Dispatcher, env: Any) -> None:
    bot, session, _ = env
    await send(dispatcher, bot, _callback("pc:BG:EUR:6000000"))
    picker = session.sent()[-1]
    assert "Compare Bulgaria with" in picker.text
    options = [b.callback_data for row in picker.reply_markup.inline_keyboard for b in row]
    assert "cmp:BG:DE:EUR:6000000" in options
    assert not any(":BG:EUR" in o.split("cmp:BG")[-1] for o in options)  # not with itself

    await send(dispatcher, bot, _callback("cmp:BG:DE:EUR:6000000"))
    assert isinstance(session.sent()[-1], EditMessageText)
    assert "Bulgaria vs Germany" in session.last_text()


async def test_plan_flow_through_buttons(dispatcher: Dispatcher, env: Any) -> None:
    bot, session, _ = env
    await send(dispatcher, bot, _callback("pp:DE:EUR:8000000:24"))
    assert "How many people" in session.last_text()
    await send(
        dispatcher, bot, _callback(kb.PlanCb(code="DE", cur="EUR", minor=8_000_000, people=10, months=24).pack())
    )
    text = session.last_text()
    assert "10 people" in text
    assert "24 months" in text


async def test_sources(dispatcher: Dispatcher, env: Any) -> None:
    bot, session, _ = env
    await send(dispatcher, bot, _message("/sources Spain"))
    text = session.last_text()
    assert "boe.es" in text
    assert "deel.com" in text
    await send(dispatcher, bot, _callback("src:PL"))
    assert "zus.pl" in session.last_text()


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ("/cost", "Usage"),
        ("/cost Narnia 50000", "I don't know “narnia”"),
        ("/cost Germny 50000", "Did you mean <b>Germany</b>"),
        ("/compare Germany 50000", "Name two countries"),
        ("/plan Germany 80000 0", "between 1 and"),
        ("/sources", "Usage"),
        ("/sources Atlantis", "I don't know"),
        ("Germany", "annual gross salary"),
        ("/frobnicate", "Try"),
        ("<b>Germany</b> 80k", "I don't know “&lt;b&gt;germany&lt;/b&gt;”"),
    ],
)
async def test_errors_are_explained(dispatcher: Dispatcher, env: Any, text: str, needle: str) -> None:
    bot, session, _ = env
    await send(dispatcher, bot, _message(text))
    assert needle in session.last_text()


@pytest.mark.parametrize(
    "data",
    ["cost:XX:EUR:6000000", "cost:DE:XYZ:6000000", "cost:DE:EUR:1", "pln:DE:EUR:8000000:0:12",
     "cmp:DE:DE:EUR:8000000", "src:ZZ", "pc:ZZ:EUR:1", "pp:ZZ:EUR:1:12", "pp:DE:EUR:8000000:999",
     "cost:PL:PLN:300000", "totally-unknown"],
)  # fmt: skip
async def test_forged_or_stale_buttons_are_refused(dispatcher: Dispatcher, env: Any, data: str) -> None:
    bot, session, _ = env
    await send(dispatcher, bot, _callback(data))
    answer = session.calls[-1]
    assert isinstance(answer, AnswerCallbackQuery)
    assert answer.show_alert
    assert not session.sent()


async def test_stats_only_for_owner(dispatcher: Dispatcher, env: Any) -> None:
    bot, session, _ = env
    await send(dispatcher, bot, _message("Germany 80k"))
    await send(dispatcher, bot, _message("/stats"))
    assert "Since start" not in session.last_text()  # silence for everybody else
    owner = User(id=OWNER_ID, is_bot=False, first_name="Owner")
    await send(dispatcher, bot, _message("/stats", owner))
    assert "free_text: 1" in session.last_text()


async def test_language_from_telegram_client(dispatcher: Dispatcher, env: Any) -> None:
    bot, session, _ = env
    russian = User(id=999, is_bot=False, first_name="R", language_code="ru")
    await send(dispatcher, bot, _message("Германия 80k", russian))
    assert "Стоимость для работодателя" in session.last_text()


async def test_start_examples_work(dispatcher: Dispatcher, env: Any) -> None:
    bot, session, _ = env
    for row in kb.start_examples("en").inline_keyboard:
        await send(dispatcher, bot, _callback(row[0].callback_data or ""))
        assert "Employer cost" in session.last_text() or "EOR" in session.last_text()


async def test_crash_is_reported_to_the_user(dispatcher: Dispatcher, env: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    bot, session, _ = env

    def boom(*_: Any) -> Any:
        raise RuntimeError("bug")

    monkeypatch.setattr("deel_advisor.bot.handlers.render", boom)
    await send(dispatcher, bot, _message("Germany 80k"))
    assert "Something went wrong" in session.last_text()
    await send(dispatcher, bot, _callback("cost:DE:EUR:8000000"))
    answer = session.calls[-1]
    assert isinstance(answer, AnswerCallbackQuery)
    assert answer.text
    assert "Something went wrong" in answer.text
