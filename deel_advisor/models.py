"""The schema every country file must pass.

Country data is JSON in `deel_advisor/data/countries/`, validated at startup: a file that does
not fit refuses to load and the bot does not start. Field names are camelCase in JSON (the
format people edit) and snake_case in Python. Money and rates are JSON strings so they reach
`Decimal` without ever having been a float.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel


def _not_float(value: object) -> object:
    # 0.1 in JSON is already 0.1000000000000000055... by the time Python sees it.
    if isinstance(value, float):
        raise ValueError('write money and rates as JSON strings ("0.093"), not decimal numbers')
    return value


Period = Literal["month", "year"]
Rate = Annotated[Decimal, BeforeValidator(_not_float), Field(ge=0, lt=1, max_digits=8)]
Amount = Annotated[Decimal, BeforeValidator(_not_float), Field(ge=0, max_digits=14, decimal_places=2)]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$", max_length=32)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]


def _https(url: HttpUrl) -> HttpUrl:
    if url.scheme != "https":
        raise ValueError("sources must be https")
    return url


Source = Annotated[HttpUrl, AfterValidator(_https)]


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid", frozen=True)


class Contribution(_Model):
    """One employer contribution: `rate × clamp(salary, floor, cap)` per payslip.

    `floor` is a threshold the base starts above (UK secondary threshold); `cap` is the base
    ceiling. Both are converted to the payslip period, so an annual cap is divided by 12.
    """

    id: Slug
    name: str = Field(min_length=2, max_length=60)
    local_name: str | None = Field(default=None, max_length=80)
    rate: Rate
    cap: Amount | None = None
    cap_period: Period | None = None
    floor: Amount | None = None
    floor_period: Period | None = None
    # The rate depends on the employer (industry risk class, health insurer); the file carries
    # a typical figure and the reply marks it with "~".
    estimate: bool = False
    source: Source

    @model_validator(mode="after")
    def _periods(self) -> Contribution:
        if (self.cap is None) != (self.cap_period is None):
            raise ValueError("cap and capPeriod go together")
        if (self.floor is None) != (self.floor_period is None):
            raise ValueError("floor and floorPeriod go together")
        return self


class MinimumWage(_Model):
    amount: Amount
    period: Literal["hour", "month", "year"]
    # Spain and some others pay 14 monthly salaries a year.
    payments_per_year: int = Field(default=12, ge=12, le=14)
    # Only for an hourly wage: what a full-time year is, to compare with an annual salary.
    hours_per_year: int | None = Field(default=None, ge=1000, le=2600)
    source: Source

    @model_validator(mode="after")
    def _hours(self) -> MinimumWage:
        if (self.period == "hour") != (self.hours_per_year is not None):
            raise ValueError("hoursPerYear is required for an hourly minimum wage, and only then")
        return self

    @property
    def annual(self) -> Decimal:
        if self.period == "hour":
            if self.hours_per_year is None:  # pragma: no cover - the validator forbids it
                raise ValueError("hourly minimum wage without hoursPerYear")
            return self.amount * self.hours_per_year
        if self.period == "month":
            return self.amount * self.payments_per_year
        return self.amount


class CostItem(_Model):
    name: str = Field(min_length=2, max_length=60)
    amount: Amount
    per_employee: bool = False
    kind: Literal["official", "estimate"]
    source: Source


class Entity(_Model):
    """Running your own legal entity: one-off setup plus monthly fixed costs, each sourced."""

    setup_cost: list[CostItem] = Field(min_length=1)
    monthly_fixed: list[CostItem] = Field(min_length=1)
    # Paid-up share capital: money that stays the company's, so it is shown but never added
    # to the cost.
    share_capital: Amount | None = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("setup_cost")
    @classmethod
    def _setup_is_one_off(cls, items: list[CostItem]) -> list[CostItem]:
        if any(item.per_employee for item in items):
            raise ValueError("setup costs are one-off; perEmployee belongs in monthlyFixed")
        return items


FigureKind = Literal["rate", "money", "text"]


class Figure(_Model):
    """A single comparable number: a rate, an amount with a currency and period, or text."""

    value: str = Field(min_length=1, max_length=40)
    kind: FigureKind
    currency: Currency | None = None
    period: Literal["hour", "month", "year"] | None = None

    @model_validator(mode="after")
    def _shape(self) -> Figure:
        if self.kind in ("rate", "money"):
            try:
                Decimal(self.value)
            except ArithmeticError as error:
                raise ValueError(f"{self.kind} figure must be a number, got {self.value!r}") from error
        if (self.kind == "money") != (self.currency is not None):
            raise ValueError("currency is required for money figures, and only for them")
        return self

    def same_as(self, other: Figure) -> bool:
        if self.kind != other.kind or self.currency != other.currency or self.period != other.period:
            return False
        if self.kind == "text":
            return self.value.strip().lower() == other.value.strip().lower()
        return Decimal(self.value) == Decimal(other.value)


class GuideFigure(Figure):
    # Text exactly as it appears on the Deel page, so scripts/check_deel_guides.py can find it
    # again; `None` when the page states the figure in a way no fixed string survives.
    quote: str | None = Field(default=None, max_length=200)


class DeelGuide(_Model):
    url: Source
    figures: dict[Slug, GuideFigure]
    checked_at: date


class OfficialFigure(Figure):
    source: Source
    # When this figure changed on another date than the country's data (a mid-year step).
    effective_from: date | None = None


class Official(_Model):
    figures: dict[Slug, OfficialFigure]
    checked_at: date


class Country(_Model):
    country: str = Field(min_length=2, max_length=40)
    code: Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]
    flag: str = Field(min_length=1, max_length=8)
    # Lower-case names people type, in any language: "germany", "deutschland", "германия".
    aliases: list[str] = Field(min_length=1)
    currency: Currency
    year: int = Field(ge=2020, le=2100)
    effective_from: date
    contributions: list[Contribution] = Field(min_length=1)
    minimum_wage: MinimumWage | None = None
    entity: Entity
    deel_guide: DeelGuide
    official: Official
    notes: list[str] = Field(default_factory=list)

    @field_validator("aliases")
    @classmethod
    def _aliases_lower(cls, aliases: list[str]) -> list[str]:
        if any(alias != alias.strip().lower() or not alias for alias in aliases):
            raise ValueError("aliases must be non-empty, trimmed and lower-case")
        return aliases

    @model_validator(mode="after")
    def _consistent(self) -> Country:
        ids = [c.id for c in self.contributions]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate contribution ids in {self.country}")
        if self.effective_from.year != self.year:
            raise ValueError("effectiveFrom must fall in the data year")
        for key, figure in self.official.figures.items():
            if figure.kind == "money" and figure.currency != self.currency:
                raise ValueError(f"{self.country}: official {key} is in {figure.currency}, not {self.currency}")
        # A Deel figure may be in another currency (a guide written before Bulgaria's euro
        # switch): that is a discrepancy to report, not a broken file.
        return self


class EorPricing(_Model):
    provider: str
    monthly_fee: Amount
    currency: Currency
    source: Source
    checked_at: date
    note: str
