"""ECB euro reference rates: fetched once a day, cached on disk, never required to answer.

The ECB publishes one set of rates per working day around 16:00 CET, free and without a key.
The bot keeps the last good set in `fx.json` in the data directory and ships a snapshot in the
package, so a fresh container with no network still answers — the reply names the date of the
rates it used, so a stale set is visible rather than silent.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib import resources
from pathlib import Path
from xml.etree import ElementTree

import httpx

log = logging.getLogger(__name__)

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
_ECB_NS = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}


class FxError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Rates:
    """Units of each currency per 1 EUR, as the ECB publishes them."""

    day: date
    per_eur: dict[str, Decimal]

    def supports(self, currency: str) -> bool:
        return currency == "EUR" or currency in self.per_eur

    def convert(self, amount: Decimal, source: str, target: str) -> Decimal:
        """Exact `Decimal` division; rounding is the caller's business."""
        if source == target:
            return amount
        for currency in (source, target):
            if not self.supports(currency):
                raise FxError(f"no ECB rate for {currency}")
        in_eur = amount if source == "EUR" else amount / self.per_eur[source]
        return in_eur if target == "EUR" else in_eur * self.per_eur[target]

    def to_json(self) -> str:
        return json.dumps(
            {"date": self.day.isoformat(), "rates": {k: str(v) for k, v in sorted(self.per_eur.items())}},
            indent=2,
        )

    @classmethod
    def from_json(cls, text: str) -> Rates:
        raw = json.loads(text)
        rates = {str(k): Decimal(str(v)) for k, v in raw["rates"].items()}
        if not rates or any(v <= 0 for v in rates.values()):
            raise FxError("rates file is empty or has a non-positive rate")
        return cls(date.fromisoformat(raw["date"]), rates)


def parse_ecb(xml: bytes) -> Rates:
    try:
        # The ECB document never has a DTD, and entity-expansion attacks need one; refusing it
        # makes stdlib ElementTree safe here without pulling in defusedxml.
        if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
            raise FxError("ECB response carries a DOCTYPE")
        root = ElementTree.fromstring(xml)  # noqa: S314 - see the DOCTYPE check above
        day_node = root.find(".//e:Cube[@time]", _ECB_NS)
        if day_node is None:
            raise FxError("no dated Cube in the ECB response")
        rates = {
            node.attrib["currency"]: Decimal(node.attrib["rate"])
            for node in day_node.findall("e:Cube[@currency]", _ECB_NS)
        }
        if not rates:
            raise FxError("ECB response has no rates")
        return Rates(date.fromisoformat(day_node.attrib["time"]), rates)
    except (ElementTree.ParseError, KeyError, ArithmeticError, ValueError) as error:
        raise FxError(f"unreadable ECB response: {error}") from error


def bundled_rates() -> Rates:
    return Rates.from_json(resources.files("deel_advisor.data").joinpath("fx_seed.json").read_text())


class FxCache:
    """The current rates, the file they persist to, and the fetch that refreshes them."""

    def __init__(self, path: Path, client: httpx.AsyncClient) -> None:
        self._path = path
        self._client = client
        self.rates = self._load()

    def _load(self) -> Rates:
        try:
            return Rates.from_json(self._path.read_text())
        except FileNotFoundError:
            log.info("no cached FX rates yet; using the bundled snapshot")
        except (OSError, FxError, ValueError, KeyError) as error:
            log.warning("cached FX rates unreadable (%s); using the bundled snapshot", error)
        return bundled_rates()

    def age_days(self, today: date) -> int:
        return (today - self.rates.day).days

    async def refresh(self) -> bool:
        """Fetch today's rates. On any failure keep the ones we have and say so in the log."""
        try:
            response = await self._client.get(ECB_URL, timeout=15)
            response.raise_for_status()
            fresh = parse_ecb(response.content)
        except (httpx.HTTPError, FxError) as error:
            log.warning("ECB refresh failed, keeping rates from %s: %s", self.rates.day, error)
            return False
        if fresh.day < self.rates.day:
            log.warning("ECB returned %s, older than the cached %s; ignoring", fresh.day, self.rates.day)
            return False
        self.rates = fresh
        self._save(fresh)
        log.info("FX rates updated to %s (%d currencies)", fresh.day, len(fresh.per_eur))
        return True

    def _save(self, rates: Rates) -> None:
        # Write-then-rename, so a crash mid-write leaves the previous file rather than half a one.
        # Failing to persist is not failing to refresh: the new rates are already in memory.
        tmp: Path | None = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(dir=self._path.parent, prefix=".fx-", suffix=".json")
            tmp = Path(name)
            with os.fdopen(fd, "w") as handle:
                handle.write(rates.to_json())
            tmp.replace(self._path)
        except OSError as error:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
            log.warning("could not persist FX rates: %s", error)
