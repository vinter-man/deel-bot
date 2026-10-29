"""Every calculation the bot makes, and nothing else.

No I/O, no Telegram, no currency conversion: amounts come in already in the country's currency
and go out as `Decimal`. The model is a payslip, not an annual formula — the annual salary is
split into 12 monthly payslips, each contribution line is rounded to the cent on that payslip,
and the year is twelve of them. That is how payroll rounds, so the totals land where a real
invoice would rather than a fraction of a cent away from it on every line.

EOR and own entity share the cost of employment itself (salary plus employer contributions):
an EOR invoices it through unchanged. What differs is the EOR fee per person per month against
the entity's one-off setup and its monthly fixed costs, and that is all the break-even compares.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from deel_advisor.models import Contribution, Country
from deel_advisor.money import ZERO, cents

MONTHS_PER_YEAR = 12


def contribution_base(contribution: Contribution, monthly_salary: Decimal) -> Decimal:
    """The slice of the monthly salary a contribution is charged on: `min(salary, cap) - floor`."""
    base = monthly_salary
    if (cap := contribution.monthly_cap) is not None:
        base = min(base, cap)
    if (floor := contribution.monthly_floor) is not None:
        base = max(ZERO, base - floor)
    return base


@dataclass(frozen=True, slots=True)
class Line:
    contribution: Contribution
    monthly: Decimal
    # The salary is above the ceiling, so this line no longer grows with it.
    capped: bool

    @property
    def annual(self) -> Decimal:
        return self.monthly * MONTHS_PER_YEAR


@dataclass(frozen=True, slots=True)
class EmployerCost:
    country: Country
    monthly_salary: Decimal
    lines: tuple[Line, ...]

    @property
    def annual_salary(self) -> Decimal:
        return self.monthly_salary * MONTHS_PER_YEAR

    @property
    def contributions_monthly(self) -> Decimal:
        return sum((line.monthly for line in self.lines), ZERO)

    @property
    def contributions_annual(self) -> Decimal:
        return self.contributions_monthly * MONTHS_PER_YEAR

    @property
    def total_monthly(self) -> Decimal:
        return self.monthly_salary + self.contributions_monthly

    @property
    def total_annual(self) -> Decimal:
        return self.total_monthly * MONTHS_PER_YEAR

    @property
    def burden(self) -> Decimal:
        """Employer contributions as a share of gross salary."""
        if self.monthly_salary == 0:
            return ZERO
        return self.contributions_monthly / self.monthly_salary


def employer_cost(country: Country, annual_salary: Decimal) -> EmployerCost:
    if annual_salary <= 0:
        raise ValueError("salary must be positive")
    monthly = cents(annual_salary / MONTHS_PER_YEAR)
    lines = []
    for contribution in country.contributions:
        base = contribution_base(contribution, monthly)
        cap = contribution.monthly_cap
        capped = cap is not None and monthly > cap
        lines.append(Line(contribution, cents(base * contribution.rate), capped))
    return EmployerCost(country, monthly, tuple(lines))


@dataclass(frozen=True, slots=True)
class EntityCost:
    setup: Decimal
    monthly_fixed: Decimal
    per_employee_monthly: Decimal

    def monthly(self, people: int) -> Decimal:
        return self.monthly_fixed + self.per_employee_monthly * people


def entity_cost(country: Country) -> EntityCost:
    items = country.entity.monthly_fixed
    return EntityCost(
        setup=sum((item.amount for item in country.entity.setup_cost), ZERO),
        monthly_fixed=sum((item.amount for item in items if not item.per_employee), ZERO),
        per_employee_monthly=sum((item.amount for item in items if item.per_employee), ZERO),
    )


def breakeven_people(entity: EntityCost, eor_fee: Decimal, months: int) -> int | None:
    """Smallest team for which the entity is strictly cheaper over `months`; None if never.

    Each person saves `eor_fee - per_employee_monthly` a month, and the entity has to earn back
    `setup + monthly_fixed × months` out of that.
    """
    margin = eor_fee - entity.per_employee_monthly
    if margin <= 0 or months <= 0:
        return None
    overhead = entity.setup + entity.monthly_fixed * months
    return int(overhead // (margin * months)) + 1


def breakeven_months(entity: EntityCost, eor_fee: Decimal, people: int) -> int | None:
    """First month after which the entity has paid for itself; None if it never does."""
    saving = (eor_fee - entity.per_employee_monthly) * people - entity.monthly_fixed
    if saving <= 0:
        return None
    return int(entity.setup // saving) + 1


@dataclass(frozen=True, slots=True)
class Plan:
    cost: EmployerCost
    entity: EntityCost
    eor_fee: Decimal
    people: int
    months: int

    @property
    def employment(self) -> Decimal:
        """Salary plus employer contributions for the whole team and horizon: the same either way."""
        return self.cost.total_monthly * self.people * self.months

    @property
    def eor_fees(self) -> Decimal:
        return self.eor_fee * self.people * self.months

    @property
    def entity_overhead(self) -> Decimal:
        return self.entity.setup + self.entity.monthly(self.people) * self.months

    @property
    def eor_total(self) -> Decimal:
        return self.employment + self.eor_fees

    @property
    def entity_total(self) -> Decimal:
        return self.employment + self.entity_overhead

    @property
    def entity_saving(self) -> Decimal:
        """Positive when the entity is cheaper over the horizon, negative when EOR is."""
        return self.eor_total - self.entity_total

    @property
    def breakeven_people(self) -> int | None:
        return breakeven_people(self.entity, self.eor_fee, self.months)

    @property
    def breakeven_months(self) -> int | None:
        return breakeven_months(self.entity, self.eor_fee, self.people)


def plan(country: Country, annual_salary: Decimal, eor_fee: Decimal, people: int, months: int) -> Plan:
    if people < 1 or months < 1:
        raise ValueError("people and months must be at least 1")
    return Plan(employer_cost(country, annual_salary), entity_cost(country), eor_fee, people, months)
