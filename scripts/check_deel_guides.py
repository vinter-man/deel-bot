"""Re-check the figures we quote from Deel's public country guides. Run by hand, never by the bot.

    uv run python scripts/check_deel_guides.py            # every country
    uv run python scripts/check_deel_guides.py DE BG      # some of them
    uv run python scripts/check_deel_guides.py --strict   # exit 1 if anything needs a look

For every country it fetches the guide page named in the JSON — one request at a time, with a
pause between them, under its own User-Agent, and only if robots.txt allows it — and looks for
each figure's `quote` in the page text. A quote that is no longer there means Deel edited the
page and the stored figure needs a human to look again. It also lists where the guide and the
official figures disagree, which is exactly what the bot warns users about.

It never writes the JSON: deciding what a changed page now says is a judgement call.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import re
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from deel_advisor import catalog, freshness
from deel_advisor.models import Country, Figure

USER_AGENT = "deel-advisor-guide-check/1.0 (+https://github.com/vinter-man/deel-bot)"
DEFAULT_DELAY = 5.0


@dataclass(frozen=True)
class Result:
    country: Country
    fetched: bool
    reason: str = ""
    missing: tuple[str, ...] = ()
    found: tuple[str, ...] = ()
    mismatches: tuple[str, ...] = ()

    @property
    def needs_attention(self) -> bool:
        return not self.fetched or bool(self.missing or self.mismatches)


def page_text(markup: str) -> str:
    """Visible text, whitespace collapsed, lower-cased: what a quote is matched against."""
    markup = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", markup)
    text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", markup))
    return re.sub(r"\s+", " ", text).strip().lower()


def _normalize(quote: str) -> str:
    return re.sub(r"\s+", " ", quote).strip().lower()


def describe(figure: Figure) -> str:
    """`3750 BGN/month`, `0.017`: the value with whatever makes it comparable."""
    unit = f" {figure.currency}" if figure.currency else ""
    period = f"/{figure.period}" if figure.period else ""
    return f"{figure.value}{unit}{period}"


class Robots:
    """robots.txt per host, fetched once, with the crawl delay it asks for."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._parsers: dict[str, RobotFileParser] = {}

    async def _parser(self, url: str) -> RobotFileParser:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._parsers:
            parser = RobotFileParser(f"{base}/robots.txt")
            response = await self._client.get(f"{base}/robots.txt")
            if response.status_code >= 500:
                # Unreachable robots.txt: assume the worst and fetch nothing from this host.
                parser.parse(["User-agent: *", "Disallow: /"])
            elif response.status_code >= 400:
                parser.parse([])  # no robots.txt: everything is allowed
            else:
                parser.parse(response.text.splitlines())
            self._parsers[base] = parser
        return self._parsers[base]

    async def allowed(self, url: str) -> bool:
        return (await self._parser(url)).can_fetch(USER_AGENT, url)

    async def delay(self, url: str) -> float:
        asked = (await self._parser(url)).crawl_delay(USER_AGENT)
        return max(DEFAULT_DELAY, float(asked or 0))


async def check_country(country: Country, client: httpx.AsyncClient, robots: Robots) -> Result:
    url = str(country.deel_guide.url)
    if not await robots.allowed(url):
        return Result(country, fetched=False, reason="disallowed by robots.txt")
    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as error:
        return Result(country, fetched=False, reason=f"{type(error).__name__}: {error}")
    text = page_text(response.text)
    found: list[str] = []
    missing: list[str] = []
    for key, figure in sorted(country.deel_guide.figures.items()):
        if figure.quote is None:
            continue
        (found if _normalize(figure.quote) in text else missing).append(key)
    disagreements = tuple(
        f"{m.key}: Deel {describe(m.deel)} vs official {describe(m.official)}" for m in freshness.mismatches(country)
    )
    return Result(country, True, missing=tuple(missing), found=tuple(found), mismatches=disagreements)


async def run(
    codes: list[str],
    client: httpx.AsyncClient,
    delay: float | None = None,
    pause: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> list[Result]:
    """`delay` overrides the pause between pages (tests pass 0); by default robots.txt decides."""
    data = catalog.load()
    countries = [c for c in data.countries if not codes or c.code in codes]
    unknown = set(codes) - {c.code for c in data.countries}
    if unknown:
        raise SystemExit(f"unknown country codes: {', '.join(sorted(unknown))}")
    robots = Robots(client)
    results = []
    for i, country in enumerate(countries):
        if i:
            await pause(delay if delay is not None else await robots.delay(str(country.deel_guide.url)))
        results.append(await check_country(country, client, robots))
    return results


def report(results: list[Result]) -> str:
    lines = []
    for result in results:
        c = result.country
        if not result.fetched:
            lines.append(f"{c.code}  SKIPPED  {result.reason}")
            continue
        status = "CHECK" if result.needs_attention else "OK"
        lines.append(f"{c.code}  {status}  {len(result.found)} quotes found  {c.deel_guide.url}")
        lines += [f"      quote not on the page any more: {key}" for key in result.missing]
        lines += [f"      guide differs from official: {m}" for m in result.mismatches]
    return "\n".join(lines)


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("codes", nargs="*", help="ISO country codes, e.g. DE BG (default: all)")
    parser.add_argument("--strict", action="store_true", help="exit 1 when anything needs a look")
    args = parser.parse_args(argv)
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        results = await run([c.upper() for c in args.codes], client)
    print(report(results))
    return 1 if args.strict and any(r.needs_attention for r in results) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
