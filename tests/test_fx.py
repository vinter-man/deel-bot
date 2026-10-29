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
