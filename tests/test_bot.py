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
from aiogram.methods import AnswerCallbackQuery, EditMessageText, GetMe, SendMessage, TelegramMethod
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
        # Set to make the next call of that method type fail, as Telegram sometimes does.
        self.fail_with: dict[type, Exception] = {}

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109 - aiogram's signature
        self.calls.append(method)
        if (error := self.fail_with.pop(type(method), None)) is not None:
            raise error
        if isinstance(method, GetMe):  # "/cost@botname" makes aiogram check its own username
            return User(id=42, is_bot=True, first_name="Advisor", username="deel_hea_unofficial_bot")
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


def _callback(data: str, user: User = USER, *, with_message: bool = True) -> Update:
    origin = Message(message_id=77, date=datetime.now(UTC), chat=Chat(id=user.id, type="private"), text="…")
    return Update(
        update_id=next(_update_ids),
        callback_query=CallbackQuery(id=str(next(_update_ids)), from_user=user, chat_instance="c", data=data,
                                     message=origin if with_message else None),
    )  # fmt: skip


async def send(dp: Dispatcher, bot: Bot, update: Update) -> None:
    await dp.feed_update(bot, update)


async def test_start_asks_for_language_then_greets(dispatcher: Dispatcher, env: Any) -> None:
    bot, session, services = env
    await send(dispatcher, bot, _message("/start"))
    first = session.sent()[-1]
    assert "Choose your language" in first.text
    buttons = [b.callback_data for row in first.reply_markup.inline_keyboard for b in row]
    assert buttons == ["lang:en", "lang:de", "lang:es", "lang:pl", "lang:bg"]

    await send(dispatcher, bot, _callback("lang:pl"))
    assert isinstance(session.sent()[-1], EditMessageText)
    assert "Podaj kraj" in session.last_text()
    assert await services.prefs.get(USER_ID) == "pl"
    # And the next reply is in Polish although the Telegram client says English.
    await send(dispatcher, bot, _message("/help"))
    assert "Polecenia" in session.last_text()


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
    parts = [m.text for m in session.sent()]
    assert len(parts) >= 2  # long enough to be split, and split at block boundaries
    text = "\n\n".join(parts)
    assert "boe.es" in text
    assert "deel.com" in text
    assert "Deel Payroll" in text
    assert "Setup until the first payroll: 16 weeks" in text
    before = len(session.sent())
    await send(dispatcher, bot, _callback("src:PL"))
    assert "zus.pl" in "\n".join(m.text for m in session.sent()[before:])


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
    german = User(id=999, is_bot=False, first_name="G", language_code="de-AT")
    await send(dispatcher, bot, _message("Deutschland 80k", german))
    assert "Arbeitgeberkosten" in session.last_text()
    french = User(id=998, is_bot=False, first_name="F", language_code="fr")
    await send(dispatcher, bot, _message("Germany 80k", french))
    assert "Employer cost" in session.last_text()  # a language we do not speak falls back to English


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


async def test_crash_message_is_in_the_users_language(
    dispatcher: Dispatcher, env: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot, session, _ = env

    def boom(*_: Any) -> Any:
        raise RuntimeError("bug")

    monkeypatch.setattr("deel_advisor.bot.handlers.render", boom)
    bulgarian = User(id=4242, is_bot=False, first_name="B", language_code="bg")
    await send(dispatcher, bot, _message("Германия 80k", bulgarian))
    assert "Нещо се обърка" in session.last_text()


# --- what Telegram and users throw at a bot besides well-formed text ----------------------------


async def test_sticker_or_photo_gets_a_hint_not_silence(dispatcher: Dispatcher, env: Any) -> None:
    bot, session, _ = env
    sticker = Update(
        update_id=next(_update_ids),
        message=Message(message_id=5, date=datetime.now(UTC), chat=Chat(id=USER_ID, type="private"),
                        from_user=USER, caption="Germany 80k"),
    )  # fmt: skip
    await send(dispatcher, bot, sticker)
    assert "Try <code>Germany 80k</code>" in session.last_text()


async def test_button_on_a_message_telegram_no_longer_shows(dispatcher: Dispatcher, env: Any) -> None:
    bot, session, _ = env
    await send(dispatcher, bot, _callback("cost:DE:EUR:8000000", with_message=False))
    assert isinstance(session.calls[-1], AnswerCallbackQuery)  # acknowledged, nothing to edit
    assert not session.sent()


async def test_tapping_the_selected_horizon_again(dispatcher: Dispatcher, env: Any) -> None:
    from aiogram.exceptions import TelegramBadRequest

    bot, session, _ = env
    session.fail_with[EditMessageText] = TelegramBadRequest(
        method=EditMessageText(text="x"), message="Bad Request: message is not modified"
    )
    await send(dispatcher, bot, _callback(kb.PlanCb(code="DE", cur="EUR", minor=8_000_000, people=5, months=12).pack()))
    # The no-op edit is swallowed: no error alert, no extra message.
    assert not any(isinstance(c, AnswerCallbackQuery) and c.show_alert for c in session.calls)


async def test_other_edit_failures_reach_the_error_handler(dispatcher: Dispatcher, env: Any) -> None:
    from aiogram.exceptions import TelegramBadRequest

    bot, session, _ = env
    session.fail_with[EditMessageText] = TelegramBadRequest(
        method=EditMessageText(text="x"), message="Bad Request: message to edit not found"
    )
    await send(dispatcher, bot, _callback(kb.PlanCb(code="DE", cur="EUR", minor=8_000_000, people=5, months=12).pack()))
    alerts = [c for c in session.calls if isinstance(c, AnswerCallbackQuery) and c.show_alert]
    assert alerts
    assert alerts[-1].text is not None
    assert "Something went wrong" in alerts[-1].text


async def test_telegram_down_while_answering_is_contained(dispatcher: Dispatcher, env: Any) -> None:
    from aiogram.exceptions import TelegramNetworkError

    bot, session, _ = env
    session.fail_with[SendMessage] = TelegramNetworkError(method=SendMessage(chat_id=1, text="x"), message="down")
    await send(dispatcher, bot, _message("Germany 80k"))  # must not raise out of the dispatcher
    assert isinstance(session.calls[-1], SendMessage)  # the apology was attempted after the failure


@pytest.mark.parametrize(
    "text",
    ["/cost@deel_hea_unofficial_bot Germany 80000", "/COST Germany 80000", "/cost   Germany    80000  "],
)
async def test_command_variants(dispatcher: Dispatcher, env: Any, text: str) -> None:
    bot, session, _ = env
    await send(dispatcher, bot, _message(text))
    assert "Employer cost" in session.last_text() or "Try" in session.last_text()


async def test_html_in_user_input_never_reaches_telegram_unescaped(dispatcher: Dispatcher, env: Any) -> None:
    bot, session, _ = env
    for text in ['<a href="x">Germany</a> 80k', "Germany 80k <b>", "&amp; 80k", "/sources <i>Spain</i>"]:
        await send(dispatcher, bot, _message(text))
        reply = session.last_text()
        assert '<a href="x">' not in reply
        assert "<i>Spain</i>" not in reply


async def test_every_language_answers_every_flow(dispatcher: Dispatcher, env: Any) -> None:
    bot, session, _ = env
    for lang in ("en", "de", "es", "pl", "bg"):
        await send(dispatcher, bot, _callback(f"lang:{lang}"))
        for data in ("cost:DE:EUR:8000000", "cmp:GB:PL:GBP:5000000", "src:BG",
                     kb.PlanCb(code="ES", cur="EUR", minor=5_000_000, people=3, months=24).pack()):  # fmt: skip
            await send(dispatcher, bot, _callback(data))
            assert "{" not in session.last_text(), (lang, data)  # no unfilled placeholder
