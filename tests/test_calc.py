"""The arithmetic, on Testland's round numbers (see conftest.country_data)."""

from decimal import Decimal

import pytest

from deel_advisor import calc
from deel_advisor.models import Contribution, Country

D = Decimal
SRC = "https://example.gov/rates"


def test_below_every_cap(testland: Country) -> None:
    cost = calc.employer_cost(testland, D(48_000))
    assert cost.monthly_salary == D(4000)
    by_id = {line.contribution.id: line for line in cost.lines}
    assert by_id["pension"].monthly == D(400)  # 10% of 4000, under the 5000/mo cap
    assert by_id["health"].monthly == D(150)  # 5% of the 3000 cap, not of 4000
    assert by_id["health"].capped
    assert not by_id["pension"].capped
    assert by_id["accident"].monthly == D(40)
    assert cost.contributions_monthly == D(590)
    assert cost.contributions_annual == D(7080)
    assert cost.total_annual == D(55_080)
    assert cost.burden == D("0.1475")


def test_annual_cap_is_applied_per_month(testland: Country) -> None:
    cost = calc.employer_cost(testland, D(90_000))
    pension = next(line for line in cost.lines if line.contribution.id == "pension")
    assert pension.monthly == D(500)  # 60000 a year = 5000 a month, 10%
    assert pension.annual == D(6000)
    assert pension.capped


def test_every_payslip_line_is_rounded_to_the_cent(testland: Country) -> None:
    cost = calc.employer_cost(testland, D("10000.10"))
    assert cost.monthly_salary == D("833.34")  # 833.3416... per payslip
    assert all(line.monthly == line.monthly.quantize(D("0.01")) for line in cost.lines)
    assert next(line for line in cost.lines if line.contribution.id == "accident").monthly == D("8.33")


def _contribution(**fields: object) -> Contribution:
    return Contribution.model_validate({"id": "x", "name": "Test", "source": SRC, **fields})


def test_floor_is_a_threshold_the_base_starts_above() -> None:
    nic = _contribution(rate="0.15", floor="5000", floorPeriod="year")
    assert calc.contribution_base(nic, D(2500)) == D(2500) - D(5000) / 12
    assert calc.contribution_base(nic, D(300)) == 0


def test_floor_and_cap_make_a_band() -> None:
    # UK auto-enrolment: 3% of earnings between the lower and upper qualifying limits.
    band = _contribution(rate="0.03", floor="6240", floorPeriod="year", cap="50270", capPeriod="year")
    base = calc.contribution_base(band, D(5000))
    assert base == D(50270) / 12 - D(520)
    assert calc.contribution_base(band, D(400)) == 0


def test_rejects_non_positive_salary(testland: Country) -> None:
    with pytest.raises(ValueError, match="positive"):
        calc.employer_cost(testland, D(0))


def test_entity_cost_splits_fixed_and_per_employee(testland: Country) -> None:
    entity = calc.entity_cost(testland)
    assert entity == calc.EntityCost(setup=D(2400), monthly_fixed=D(300), per_employee_monthly=D(50))
    assert entity.monthly(3) == D(450)


def test_plan_totals(testland: Country) -> None:
    plan = calc.plan(testland, D(48_000), eor_fee=D(550), people=3, months=12)
    assert plan.employment == D(4590) * 3 * 12
    assert plan.eor_fees == D(550 * 3 * 12)
    assert plan.entity_overhead == D(2400 + 450 * 12)
    assert plan.eor_total - plan.entity_total == plan.entity_saving == D(19_800 - 7_800)


def test_breakeven_is_strict(testland: Country) -> None:
    entity = calc.entity_cost(testland)
    # One person for 12 months costs exactly the same both ways (6600), so it takes two.
    assert calc.breakeven_people(entity, D(550), months=12) == 2
    # One person saves 500 - 300 = 200 a month: 2400 of setup is even at month 12, ahead at 13.
    assert calc.breakeven_months(entity, D(550), people=1) == 13


def test_breakeven_never(testland: Country) -> None:
    entity = calc.entity_cost(testland)
    assert calc.breakeven_people(entity, D(50), months=12) is None  # fee no higher than payroll
    assert calc.breakeven_months(entity, D(340), people=1) is None  # saving 290 < fixed 300
    assert calc.breakeven_people(entity, D(550), months=0) is None


def test_plan_breakeven_properties(testland: Country) -> None:
    plan = calc.plan(testland, D(48_000), eor_fee=D(550), people=1, months=12)
    assert plan.breakeven_people == 2
    assert plan.breakeven_months == 13
    assert plan.entity_saving == 0


def test_plan_rejects_empty_team(testland: Country) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        calc.plan(testland, D(48_000), D(550), people=0, months=12)
