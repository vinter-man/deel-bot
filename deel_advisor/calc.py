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
from decimal import ROUND_CEILING, Decimal

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
    """What running your own entity costs beyond the employment itself, per month and one-off.

    `bridge_months` is the setup time: until the entity can run payroll, the team is employed
    through the EOR anyway (or not at all), so those months carry the EOR fee on the entity side.
    `admin_monthly` is your own team's time on tax and payroll compliance, which an EOR does
    for you; `exit` is closing the entity at the end of the horizon.
    """

    setup: Decimal
    exit: Decimal
    monthly_fixed: Decimal
    admin_monthly: Decimal
    per_employee_monthly: Decimal
    bridge_months: int

    @property
    def overhead_monthly(self) -> Decimal:
        return self.monthly_fixed + self.admin_monthly


WEEKS_PER_MONTH = Decimal(52) / 12


def entity_cost(country: Country, payroll_fee: Decimal | None = None) -> EntityCost:
    """`payroll_fee`: run payroll on Deel Payroll at this price per person instead of the local
    provider in the data (items flagged `payroll`)."""
    entity = country.entity
    items = entity.monthly_fixed
    per_employee = [i.amount for i in items if i.per_employee and not (payroll_fee is not None and i.payroll)]
    if payroll_fee is not None:
        per_employee.append(payroll_fee)
    admin = entity.admin_time
    return EntityCost(
        setup=sum((item.amount for item in entity.setup_cost), ZERO),
        exit=sum((item.amount for item in entity.exit_cost), ZERO),
        monthly_fixed=sum((item.amount for item in items if not item.per_employee), ZERO),
        admin_monthly=cents(admin.hourly_cost * admin.hours_per_year / MONTHS_PER_YEAR),
        per_employee_monthly=sum(per_employee, ZERO),
        # Part of a month is a month: payroll runs monthly, so 7 weeks means two EOR invoices.
        # (Not `-(-a // b)`: Decimal's `//` truncates towards zero rather than flooring.)
        bridge_months=int((entity.setup_time.weeks / WEEKS_PER_MONTH).to_integral_value(ROUND_CEILING)),
    )


def breakeven_people(entity: EntityCost, eor_fee: Decimal, months: int) -> int | None:
    """Smallest team for which the entity is strictly cheaper over `months`; None if never.

    The entity side pays the setup, the exit, its monthly overhead for every month, and the EOR
    fee during the setup months; each person saves `eor_fee - per_employee_monthly` for every
    month after them.
    """
    running = months - min(entity.bridge_months, months)
    margin = (eor_fee - entity.per_employee_monthly) * running
    if margin <= 0:
        return None
    overhead = entity.setup + entity.exit + entity.overhead_monthly * months
    return int(overhead // margin) + 1


def breakeven_months(entity: EntityCost, eor_fee: Decimal, people: int) -> int | None:
    """Shortest horizon over which the entity is strictly cheaper; None if it never is.

    For a horizon M past the setup months the entity's advantage is
    `M × slope − (setup + exit + bridge months × people × margin)`.
    """
    per_person = eor_fee - entity.per_employee_monthly
    slope = per_person * people - entity.overhead_monthly
    if slope <= 0:
        return None
    sunk = entity.setup + entity.exit + per_person * people * entity.bridge_months
    return int(sunk // slope) + 1


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
    def bridge_months(self) -> int:
        return min(self.entity.bridge_months, self.months)

    @property
    def running_months(self) -> int:
        return self.months - self.bridge_months

    @property
    def bridge_fees(self) -> Decimal:
        """EOR fees paid on the entity side while the entity is being set up."""
        return self.eor_fee * self.people * self.bridge_months

    @property
    def admin(self) -> Decimal:
        return self.entity.admin_monthly * self.months

    @property
    def entity_overhead(self) -> Decimal:
        return (
            self.entity.setup
            + self.entity.exit
            + self.entity.monthly_fixed * self.months
            + self.admin
            + self.entity.per_employee_monthly * self.people * self.running_months
            + self.bridge_fees
        )

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


def plan(
    country: Country,
    annual_salary: Decimal,
    eor_fee: Decimal,
    people: int,
    months: int,
    payroll_fee: Decimal | None = None,
) -> Plan:
    if people < 1 or months < 1:
        raise ValueError("people and months must be at least 1")
    entity = entity_cost(country, payroll_fee)
    return Plan(employer_cost(country, annual_salary), entity, eor_fee, people, months)
