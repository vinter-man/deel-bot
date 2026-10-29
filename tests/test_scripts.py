"""The two maintenance scripts: the Deel guide checker (network mocked) and the shot exporter."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from deel_advisor.catalog import Catalog
from scripts import check_deel_guides as guides
from scripts import export_shots

ROBOTS_OK = "User-Agent: *\nDisallow: /login\n"


def _page_with_quotes(catalog: Catalog, code: str, drop: str | None = None) -> str:
    country = catalog.by_code(code)
    assert country is not None
    quotes = [f.quote for k, f in country.deel_guide.figures.items() if f.quote and k != drop]
    body = "".join(f"<li>{q.replace('&', '&amp;')}</li>" for q in quotes)
    return f"<html><script>var x = 1;</script><body><ul>{body}</ul></body></html>"


def test_page_text_strips_markup() -> None:
    html = "<p>Pension&nbsp;-  <b>9.76%</b></p><script>ignore()</script><style>.x{}</style>"
    assert guides.page_text(html) == "pension - 9.76%"


async def test_all_quotes_found(real_catalog: Catalog) -> None:
    with respx.mock:
        respx.get("https://www.deel.com/robots.txt").respond(200, text=ROBOTS_OK)
        respx.get("https://www.deel.com/hiring/employees/poland/").respond(
            200, text=_page_with_quotes(real_catalog, "PL")
        )
        async with httpx.AsyncClient() as client:
            [result] = await guides.run(["PL"], client, delay=0)
    poland = real_catalog.by_code("PL")
    assert poland is not None
    assert result.fetched
    assert not result.missing
    assert len(result.found) == sum(1 for f in poland.deel_guide.figures.values() if f.quote)
    assert result.mismatches == ("pension_cap: Deel 260190 PLN/year vs official 282600 PLN/year",)


async def test_changed_page_is_flagged(real_catalog: Catalog) -> None:
    with respx.mock:
        respx.get("https://www.deel.com/robots.txt").respond(200, text=ROBOTS_OK)
        respx.get("https://www.deel.com/hiring/employees/germany/").respond(
            200, text=_page_with_quotes(real_catalog, "DE", drop="care_rate")
        )
        async with httpx.AsyncClient() as client:
            [result] = await guides.run(["DE"], client, delay=0)
    assert result.missing == ("care_rate",)
    assert "quote not on the page any more: care_rate" in guides.report([result])


async def test_robots_disallow_is_respected(real_catalog: Catalog) -> None:
    with respx.mock:
        respx.get("https://www.deel.com/robots.txt").respond(200, text="User-Agent: *\nDisallow: /hiring/\n")
        page = respx.get("https://www.deel.com/hiring/employees/spain/")
        async with httpx.AsyncClient() as client:
            [result] = await guides.run(["ES"], client, delay=0)
    assert not page.called
    assert (result.fetched, result.reason) == (False, "disallowed by robots.txt")
    assert "SKIPPED" in guides.report([result])


async def test_unreachable_robots_means_no_fetching() -> None:
    with respx.mock:
        respx.get("https://www.deel.com/robots.txt").respond(503)
        page = respx.get("https://www.deel.com/hiring/employees/spain/")
        async with httpx.AsyncClient() as client:
            [result] = await guides.run(["ES"], client, delay=0)
    assert not page.called
    assert not result.fetched


async def test_http_error_is_reported() -> None:
    with respx.mock:
        respx.get("https://www.deel.com/robots.txt").respond(404)  # no robots.txt: allowed
        respx.get("https://www.deel.com/hiring/employees/spain/").respond(500)
        async with httpx.AsyncClient() as client:
            [result] = await guides.run(["ES"], client, delay=0)
    assert not result.fetched
    assert "HTTPStatusError" in result.reason


async def test_requests_are_sequential_with_a_pause() -> None:
    pauses: list[float] = []

    async def fake_pause(seconds: float) -> None:
        pauses.append(seconds)

    with respx.mock:
        respx.get("https://www.deel.com/robots.txt").respond(200, text=ROBOTS_OK + "Crawl-delay: 9\n")
        respx.get(url__startswith="https://www.deel.com/hiring/").respond(200, text="<p>nothing</p>")
        async with httpx.AsyncClient() as client:
            results = await guides.run(["DE", "PL"], client, pause=fake_pause)
    assert len(results) == 2
    assert pauses == [9.0]  # one pause between two pages, at robots.txt's crawl delay


async def test_unknown_code() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(SystemExit, match="XX"):
            await guides.run(["XX"], client, delay=0)


async def test_main_strict_exit_code(capsys: pytest.CaptureFixture[str]) -> None:
    with respx.mock:
        respx.get("https://www.deel.com/robots.txt").respond(200, text=ROBOTS_OK)
        respx.get("https://www.deel.com/hiring/employees/poland/").respond(200, text="<p>changed</p>")
        assert await guides.main(["pl", "--strict"]) == 1
        assert await guides.main(["pl"]) == 0
    assert "PL  CHECK" in capsys.readouterr().out


def test_export_shots_uses_real_replies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(export_shots, "PUBLIC", tmp_path)  # the charts, not into the repo
    shots = export_shots.build()
    assert set(shots) == {"start", "team", "team24", "plan", "cost", "compare", "sources", "errors"}
    # Team answers are a chart and its caption, as the bot sends them.
    team = shots["team"][1]["in"]
    assert team["photo"] == "team.png"
    assert (tmp_path / "team.png").read_bytes().startswith(b"\x89PNG")
    assert (tmp_path / "team24.png").read_bytes() != (tmp_path / "team.png").read_bytes()
    assert shots["team"][0]["out"] == "Germany 2 × 80k, UK 1 × £60k, Spain 1 × 50k, Poland 1 × 200k zł"
    plan_reply = shots["plan"][1]["in"]
    assert "EOR (Deel)" in plan_reply["html"]
    assert plan_reply["keyboard"][0][1] == "• 12 mo"
    assert "Team in 4 countries" in shots["team"][1]["in"]["html"]
    assert shots["team24"][1]["in"]["keyboard"][0][2] == "• 24 mo"
    assert "Did you mean <b>Germany</b>" in shots["errors"][1]["in"]["html"]
    assert "annual gross salary" in shots["errors"][3]["in"]["html"]
    assert "between 1 and" in shots["errors"][5]["in"]["html"]


async def test_robots_network_error_means_no_fetching() -> None:
    with respx.mock:
        respx.get("https://www.deel.com/robots.txt").mock(side_effect=httpx.ConnectError("down"))
        page = respx.get("https://www.deel.com/hiring/employees/spain/")
        async with httpx.AsyncClient() as client:
            [result] = await guides.run(["ES"], client, delay=0)
    assert not page.called
    assert result.reason == "robots.txt unreachable, fetching nothing"
