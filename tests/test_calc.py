"""The arithmetic, on Testland's round numbers (see conftest.country_data)."""

from decimal import Decimal

import pytest

from deel_advisor import calc
from deel_advisor.models import Contribution, Country
from tests.conftest import country_data

D = Decimal
SRC = "https://example.gov/rates"


def test_below_every_cap(testland: Country) -> None:
    cost = calc.employer_cost(testland, D(48_000))
    assert cost.monthly_salary == D(4000)
    by_id = {line.contribution.id: line for line in cost.lines}
    assert by_id["pension"].monthly == D(400)  # 10% of 4000, under the 5000/mo cap
    assert by_id["health"].monthly == D(150)  # 5% of the 3000 cap, not of 4000
    assert by_id["accident"].monthly == D(40)
    assert cost.contributions_monthly == D(590)
    assert cost.total_annual == D(55_080)


def test_annual_cap_is_applied_per_month(testland: Country) -> None:
    cost = calc.employer_cost(testland, D(90_000))
    pension = next(line for line in cost.lines if line.contribution.id == "pension")
    assert pension.monthly == D(500)  # 60000 a year = 5000 a month, 10%


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
    assert entity == calc.EntityCost(
        setup=D(2400), exit=D(0), monthly_fixed=D(300), per_employee_monthly=D(50), bridge_months=0
    )


def test_deel_payroll_replaces_the_local_provider(testland: Country) -> None:
    assert calc.entity_cost(testland, payroll_fee=D(26)).per_employee_monthly == D(26)  # not 50 + 26


def test_plan_totals(testland: Country) -> None:
    plan = calc.plan(testland, D(48_000), eor_fee=D(550), people=3, months=12)
    assert plan.employment == D(4590) * 3 * 12
    assert plan.eor_fees == D(550 * 3 * 12)
    assert plan.entity_overhead == D(2400 + 450 * 12)
    assert plan.entity_saving == D(19_800 - 7_800)


def test_breakeven_is_strict(testland: Country) -> None:
    entity = calc.entity_cost(testland)
    # One person for 12 months costs exactly the same both ways (6600), so it takes two.
    assert calc.breakeven_people(entity, D(550), months=12) == 2


def test_breakeven_never(testland: Country) -> None:
    entity = calc.entity_cost(testland)
    assert calc.breakeven_people(entity, D(50), months=12) is None  # fee no higher than payroll
    assert calc.breakeven_people(entity, D(550), months=0) is None


def test_plan_breakeven_properties(testland: Country) -> None:
    plan = calc.plan(testland, D(48_000), eor_fee=D(550), people=1, months=12)
    assert plan.breakeven_people == 2
    assert plan.entity_saving == 0


def test_salary_must_be_positive(testland: Country) -> None:
    assert calc.employer_cost(testland, D("0.12")).monthly_salary == D("0.01")
    for salary in (D(0), D(-1)):
        with pytest.raises(ValueError, match=r"^salary must be positive$"):
            calc.employer_cost(testland, salary)


def test_plan_rejects_empty_team(testland: Country) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        calc.plan(testland, D(48_000), D(550), people=0, months=12)


# --- boundaries the first version of these tests let through (found by mutation testing) ------


def test_one_month_horizon(testland: Country) -> None:
    plan = calc.plan(testland, D(48_000), eor_fee=D(550), people=10, months=1)
    assert plan.months == 1
    # 10 × 500 saved in one month against 2,400 setup + 300 fixed: the entity already wins.
    assert plan.entity_saving == D(10 * 500 - 2400 - 300)
    assert calc.breakeven_people(calc.entity_cost(testland), D(550), months=1) == 6  # 2,700 // 500 + 1
    with pytest.raises(ValueError, match=r"^people and months must be at least 1$"):
        calc.plan(testland, D(48_000), D(550), people=1, months=0)


def test_breakeven_with_a_margin_just_above_zero(testland: Country) -> None:
    entity = calc.entity_cost(testland)
    assert calc.breakeven_people(entity, D("50.50"), months=12) == 1001  # 6,000 // (0.50 × 12) + 1


def test_breakeven_people_floors_rather_than_rounds(testland: Country) -> None:
    entity = calc.entity_cost(testland)
    # overhead 6,000 / (margin 499 × 12) = 1.002: the smallest strictly cheaper team is 2.
    assert calc.breakeven_people(entity, D(549), months=12) == 2


# --- what an entity costs that an EOR absorbs ------------------------------------------------


@pytest.fixture
def hidden() -> Country:
    """Testland with a 6-week setup and €1,000 to close."""
    data = country_data()
    src = "https://example.gov/rates"
    data["entity"]["setupTime"] = {"weeks": 6, "source": src}
    data["entity"]["exitCost"] = [{"name": "Closing", "amount": "1000", "kind": "estimate", "source": src}]
    return Country.model_validate(data)


@pytest.mark.parametrize(("weeks", "months"), [(0, 0), (1, 1), (4, 1), (5, 2), (7, 2), (8, 2), (9, 3), (13, 3),
                                               (16, 4), (52, 12)])  # fmt: skip
def test_setup_weeks_round_up_to_whole_payroll_months(weeks: int, months: int) -> None:
    data = country_data()
    data["entity"]["setupTime"]["weeks"] = weeks
    assert calc.entity_cost(Country.model_validate(data)).bridge_months == months


def test_hidden_costs_on_the_entity_side(hidden: Country) -> None:
    entity = calc.entity_cost(hidden)
    assert (entity.bridge_months, entity.exit) == (2, D(1000))
    plan = calc.plan(hidden, D(48_000), eor_fee=D(550), people=3, months=12)
    assert plan.bridge_fees == D(550 * 3 * 2)  # two months on the EOR while the entity is set up
    assert plan.running_months == 10
    # setup + exit + 12 months of fixed costs + payroll for the running months + the bridge fees
    assert plan.entity_overhead == D(2400 + 1000 + 12 * 300 + 50 * 3 * 10 + 3300)
    assert plan.entity_saving == plan.eor_fees - plan.entity_overhead == D(19_800 - 11_800)


def test_horizon_shorter_than_setup(hidden: Country) -> None:
    plan = calc.plan(hidden, D(48_000), eor_fee=D(550), people=3, months=1)
    assert (plan.bridge_months, plan.running_months) == (1, 0)
    assert plan.entity_saving < 0  # the entity never ran payroll, yet was opened and closed
    assert plan.breakeven_people is None  # no running month to save anything in


def test_breakeven_with_hidden_costs_matches_brute_force(hidden: Country) -> None:
    """The closed form must agree with simply trying every team size."""
    entity = calc.entity_cost(hidden)
    for fee in (D(400), D(550), D(900)):
        for months in (1, 2, 3, 6, 12, 24, 60):
            brute = next(
                (n for n in range(1, 500) if calc.plan(hidden, D(48_000), fee, n, months).entity_saving > 0), None
            )
            assert calc.breakeven_people(entity, fee, months) == brute, (fee, months)


def test_plan_passes_the_payroll_price_on(testland: Country) -> None:
    assert calc.plan(testland, D(48_000), D(550), 1, 12, payroll_fee=D(26)).entity.per_employee_monthly == D(26)


def test_a_margin_below_one_unit_still_breaks_even(testland: Country) -> None:
    # 5 cents a person a month over 12 months: 60 cents in total, far from "never".
    entity = calc.entity_cost(testland)
    assert calc.breakeven_people(entity, D("50.05"), months=12) == 10_001  # 6,000 // 0.60 + 1
