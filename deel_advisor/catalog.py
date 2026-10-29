"""Loads and validates the bundled data once, at startup. A bad file stops the bot from starting."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from importlib import resources

from deel_advisor.models import Country, EorPricing
from deel_advisor.parser import CountryIndex


@dataclass(frozen=True)
class Catalog:
    countries: tuple[Country, ...]
    eor: EorPricing
    index: CountryIndex = field(init=False, repr=False)

    def __post_init__(self) -> None:
        codes = [c.code for c in self.countries]
        if len(codes) != len(set(codes)):
            raise ValueError(f"duplicate country codes: {codes}")
        aliases = [alias for c in self.countries for alias in c.aliases]
        if len(aliases) != len(set(aliases)):
            raise ValueError("an alias points at two countries")
        object.__setattr__(self, "index", CountryIndex(self.countries))

    def by_code(self, code: str) -> Country | None:
        return next((c for c in self.countries if c.code == code), None)


@cache
def load() -> Catalog:
    data = resources.files("deel_advisor.data")
    files = sorted(
        (f for f in data.joinpath("countries").iterdir() if f.name.endswith(".json")),
        key=lambda f: f.name,
    )
    countries = tuple(Country.model_validate_json(f.read_text(encoding="utf-8")) for f in files)
    eor = EorPricing.model_validate_json(data.joinpath("eor.json").read_text(encoding="utf-8"))
    return Catalog(countries, eor)
