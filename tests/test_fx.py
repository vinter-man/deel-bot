from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx

from deel_advisor.fx import ECB_URL, FxCache, FxError, Rates, bundled_rates, parse_ecb
from tests.conftest import FIXTURES

ECB_XML = (FIXTURES / "ecb-daily.xml").read_bytes()


def test_parse_real_ecb_document() -> None:
    rates = parse_ecb(ECB_XML)
    assert rates.day == date(2026, 10, 28)
    assert {"USD", "GBP", "PLN"} <= rates.per_eur.keys()
    assert all(isinstance(v, Decimal) for v in rates.per_eur.values())


@pytest.mark.parametrize(
    "xml",
    [b"not xml", b"<a/>", b'<!DOCTYPE x [<!ENTITY a "b">]><a/>',
     ECB_XML.replace(b"rate='1.1133'", b"rate='abc'")],
)  # fmt: skip
def test_parse_rejects_garbage(xml: bytes) -> None:
    with pytest.raises(FxError):
        parse_ecb(xml)


def test_convert_goes_through_euro(fixed_rates: Rates) -> None:
    assert fixed_rates.convert(Decimal(100), "EUR", "USD") == Decimal(125)
    assert fixed_rates.convert(Decimal(125), "USD", "EUR") == Decimal(100)
    assert fixed_rates.convert(Decimal(100), "USD", "GBP") == Decimal(64)
    assert fixed_rates.convert(Decimal(7), "PLN", "PLN") == Decimal(7)


def test_convert_unknown_currency(fixed_rates: Rates) -> None:
    with pytest.raises(FxError, match="JPY"):
        fixed_rates.convert(Decimal(1), "JPY", "EUR")


def test_json_round_trip(fixed_rates: Rates) -> None:
    assert Rates.from_json(fixed_rates.to_json()) == fixed_rates


def test_from_json_rejects_non_positive() -> None:
    with pytest.raises(FxError):
        Rates.from_json('{"date": "2026-01-01", "rates": {"USD": "0"}}')


def test_bundled_snapshot_loads() -> None:
    assert bundled_rates().supports("USD")


async def test_cache_starts_from_snapshot_and_refreshes(tmp_path: Path) -> None:
    path = tmp_path / "fx.json"
    async with httpx.AsyncClient() as client:
        cache = FxCache(path, client)
        assert cache.rates == bundled_rates()
        with respx.mock:
            respx.get(ECB_URL).respond(200, content=ECB_XML)
            assert await cache.refresh()
    assert cache.rates.day == date(2026, 10, 28)
    assert Rates.from_json(path.read_text()) == cache.rates
    assert cache.age_days(date(2026, 10, 30)) == 2


async def test_cache_reads_its_file(tmp_path: Path, fixed_rates: Rates) -> None:
    path = tmp_path / "fx.json"
    path.write_text(fixed_rates.to_json())
    async with httpx.AsyncClient() as client:
        assert FxCache(path, client).rates == fixed_rates


async def test_unreadable_cache_falls_back(tmp_path: Path) -> None:
    path = tmp_path / "fx.json"
    path.write_text("{broken")
    async with httpx.AsyncClient() as client:
        assert FxCache(path, client).rates == bundled_rates()


@pytest.mark.parametrize("response", [httpx.Response(503), httpx.Response(200, content=b"<html/>")])
async def test_failed_refresh_keeps_rates(tmp_path: Path, response: httpx.Response) -> None:
    async with httpx.AsyncClient() as client:
        cache = FxCache(tmp_path / "fx.json", client)
        before = cache.rates
        with respx.mock:
            respx.get(ECB_URL).mock(return_value=response)
            assert not await cache.refresh()
    assert cache.rates == before
    assert not (tmp_path / "fx.json").exists()


async def test_network_error_keeps_rates(tmp_path: Path) -> None:
    async with httpx.AsyncClient() as client:
        cache = FxCache(tmp_path / "fx.json", client)
        with respx.mock:
            respx.get(ECB_URL).mock(side_effect=httpx.ConnectError("down"))
            assert not await cache.refresh()


async def test_older_ecb_answer_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "fx.json"
    path.write_text(Rates(date(2026, 12, 1), {"USD": Decimal(1)}).to_json())
    async with httpx.AsyncClient() as client:
        cache = FxCache(path, client)
        with respx.mock:
            respx.get(ECB_URL).respond(200, content=ECB_XML)
            assert not await cache.refresh()
    assert cache.rates.day == date(2026, 12, 1)


async def test_unwritable_cache_dir_is_not_fatal(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("")
    async with httpx.AsyncClient() as client:
        cache = FxCache(blocker / "fx.json", client)  # parent is a file: every write fails
        with respx.mock:
            respx.get(ECB_URL).respond(200, content=ECB_XML)
            assert await cache.refresh()
    assert cache.rates.day == date(2026, 10, 28)


# --- hostile documents and failing disks (holes found by mutation testing) ----------------------


@pytest.mark.parametrize(
    "xml",
    [b'<?xml version="1.0"?><!DOCTYPE x><a/>',  # a DOCTYPE alone is refused already
     b'<a><!ENTITY x "y"></a>'],  # and so is an ENTITY alone
)  # fmt: skip
def test_dtd_pieces_are_refused_separately(xml: bytes) -> None:
    with pytest.raises(FxError, match=r"^ECB response carries a DOCTYPE$"):
        parse_ecb(xml)


def test_billion_laughs_never_reaches_the_parser() -> None:
    bomb = b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;">]><l>&b;</l>'
    with pytest.raises(FxError, match="DOCTYPE"):
        parse_ecb(bomb)


@pytest.mark.parametrize(
    ("xml", "message"),
    [(b"<a/>", "^no dated Cube in the ECB response$"),
     (ECB_XML.split(b"<Cube currency")[0] + b"</Cube></Cube></gesmes:Envelope>", "^ECB response has no rates$"),
     (b"<<<", "^unreadable ECB response: ")],
)  # fmt: skip
def test_parse_errors_explain_themselves(xml: bytes, message: str) -> None:
    with pytest.raises(FxError, match=message):
        parse_ecb(xml)


def test_from_json_error_message() -> None:
    with pytest.raises(FxError, match=r"^rates file is empty or has a non-positive rate$"):
        Rates.from_json('{"date": "2026-01-01", "rates": {}}')


def test_saved_file_is_readable_json(tmp_path: Path, fixed_rates: Rates) -> None:
    text = fixed_rates.to_json()
    assert text.startswith('{\n  "date": "2026-10-29",\n  "rates": {\n    "GBP": "0.8"')


async def test_request_has_a_timeout(tmp_path: Path) -> None:
    async with httpx.AsyncClient() as client:
        cache = FxCache(tmp_path / "fx.json", client)
        with respx.mock:
            route = respx.get(ECB_URL).respond(200, content=ECB_XML)
            await cache.refresh()
    timeout = route.calls.last.request.extensions["timeout"]
    assert timeout == {"connect": 15, "read": 15, "write": 15, "pool": 15}  # never hangs the daily job


async def test_cache_creates_missing_directories(tmp_path: Path) -> None:
    path = tmp_path / "a" / "b" / "fx.json"
    async with httpx.AsyncClient() as client:
        cache = FxCache(path, client)
        with respx.mock:
            respx.get(ECB_URL).respond(200, content=ECB_XML)
            await cache.refresh()
    assert Rates.from_json(path.read_text()).day == date(2026, 10, 28)


async def test_failed_rename_leaves_no_temp_file(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    (tmp_path / "fx.json").mkdir()  # the target is a directory: writing works, the rename fails
    async with httpx.AsyncClient() as client:
        cache = FxCache(tmp_path / "fx.json", client)
        with respx.mock:
            respx.get(ECB_URL).respond(200, content=ECB_XML)
            assert await cache.refresh()
    assert [p.name for p in tmp_path.iterdir()] == ["fx.json"]  # no .fx-*.json left behind
    assert "could not persist FX rates: [Errno 21] Is a directory" in caplog.text


async def test_logs_name_the_dates(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="deel_advisor.fx")
    async with httpx.AsyncClient() as client:
        cache = FxCache(tmp_path / "fx.json", client)
        kept = cache.rates.day
        with respx.mock:
            respx.get(ECB_URL).respond(503)
            await cache.refresh()
            assert f"ECB refresh failed, keeping rates from {kept}: " in caplog.text
            assert "503" in caplog.text
            respx.get(ECB_URL).respond(200, content=ECB_XML)
            await cache.refresh()
    assert f"FX rates updated to 2026-10-28 ({len(cache.rates.per_eur)} currencies)" in caplog.text


async def test_logs_explain_a_fallback(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="deel_advisor.fx")
    async with httpx.AsyncClient() as client:
        FxCache(tmp_path / "missing.json", client)
        (tmp_path / "bad.json").write_text("{broken")
        FxCache(tmp_path / "bad.json", client)
    assert "no cached FX rates yet; using the bundled snapshot" in caplog.text
    assert "cached FX rates unreadable (Expecting property name" in caplog.text


async def test_older_answer_is_logged_with_both_dates(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    path = tmp_path / "fx.json"
    path.write_text(Rates(date(2026, 12, 1), {"USD": Decimal(1)}).to_json())
    async with httpx.AsyncClient() as client:
        cache = FxCache(path, client)
        with respx.mock:
            respx.get(ECB_URL).respond(200, content=ECB_XML)
            await cache.refresh()
    assert "ECB returned 2026-10-28, older than the cached 2026-12-01; ignoring" in caplog.text


def test_rates_reject_unknown_target(fixed_rates: Rates) -> None:
    with pytest.raises(FxError, match="no ECB rate for XYZ"):
        fixed_rates.convert(Decimal(1), "EUR", "XYZ")
    assert fixed_rates.supports("EUR")
    assert not fixed_rates.supports("XYZ")
