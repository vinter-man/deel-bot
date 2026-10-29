"""Is the data still true? Three checks, each surfaced in the reply rather than buried in a log.

1. The rates are for an earlier year than today's — contribution ceilings move every January.
2. Nobody has re-checked the official figures for a long time.
3. Deel's public guide states a figure differently from the official source.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from deel_advisor.models import Country, GuideFigure, OfficialFigure

STALE_AFTER_DAYS = 180


@dataclass(frozen=True, slots=True)
class Mismatch:
    key: str
    deel: GuideFigure
    official: OfficialFigure


@dataclass(frozen=True, slots=True)
class Freshness:
    country: Country
    outdated_year: bool
    unchecked_days: int | None
    mismatches: tuple[Mismatch, ...]

    @property
    def clean(self) -> bool:
        return not (self.outdated_year or self.unchecked_days or self.mismatches)


def mismatches(country: Country) -> tuple[Mismatch, ...]:
    """Figures both sides state, where they disagree. A figure only one side has is not compared."""
    guide, official = country.deel_guide.figures, country.official.figures
    return tuple(
        Mismatch(key, guide[key], official[key])
        for key in sorted(guide.keys() & official.keys())
        if not guide[key].same_as(official[key])
    )


def check(country: Country, today: date) -> Freshness:
    age = (today - country.official.checked_at).days
    return Freshness(
        country=country,
        outdated_year=country.year < today.year,
        unchecked_days=age if age > STALE_AFTER_DAYS else None,
        mismatches=mismatches(country),
    )
