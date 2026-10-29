"""The bundled country files: hand-checked payslips, and figures that agree with the rates.

The expected amounts are worked out by hand from the official rates (see each country's
/sources), one payslip line at a time, rounded half-up to the cent as payroll does.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from deel_advisor import calc
from deel_advisor.catalog import Catalog
from deel_advisor.models import Country

D = Decimal


def _country(catalog: Catalog, code: str) -> Country:
    country = catalog.by_code(code)
    assert country is not None
    return country


def _monthly(catalog: Catalog, code: str, salary: int) -> dict[str, Decimal]:
    cost = calc.employer_cost(_country(catalog, code), D(salary))
    return {line.contribution.id: line.monthly for line in cost.lines}


def test_germany_80k(real_catalog: Catalog) -> None:
    lines = _monthly(real_catalog, "DE", 80_000)  # 6,666.67 a month
    assert lines["pension"] == D("620.00")  # 9.3%, under the 8,450 ceiling
    assert lines["health"] == D("508.59")  # 8.75% of the 5,812.50 ceiling
    assert lines["care"] == D("104.63")  # 1.8% of 5,812.50 = 104.625, half-up
    assert lines["unemployment"] == D("86.67")
    assert lines["insolvency"] == D("10.00")
    cost = calc.employer_cost(_country(real_catalog, "DE"), D(80_000))
    assert cost.contributions_monthly == D("1571.22")
    assert cost.total_annual == D("98854.68")


def test_uk_threshold_and_band(real_catalog: Catalog) -> None:
    lines = _monthly(real_catalog, "GB", 50_000)  # 4,166.67 a month
    assert lines["nic"] == D("562.50")  # 15% above 5,000 / 12
    assert lines["workplace_pension"] == D("109.40")  # 3% of (4,166.67 - 520)


def test_spain_solidarity_tiers(real_catalog: Catalog) -> None:
    lines = _monthly(real_catalog, "ES", 120_000)  # 10,000 a month
    assert lines["common_contingencies"] == D("1203.88")  # 23.6% of the 5,101.20 ceiling
    assert lines["solidarity_1"] == D("4.90")  # 0.96% of 510.12
    assert lines["solidarity_2"] == D("21.22")  # 1.04% of 2,040.48
    assert lines["solidarity_3"] == D("28.65")  # 1.22% of 2,348.20


def test_spain_no_solidarity_below_ceiling(real_catalog: Catalog) -> None:
    lines = _monthly(real_catalog, "ES", 50_000)
    assert lines["solidarity_1"] == lines["solidarity_2"] == lines["solidarity_3"] == 0


def test_poland_annual_cap(real_catalog: Catalog) -> None:
    lines = _monthly(real_catalog, "PL", 400_000)
    assert lines["pension"] == D("2298.48")  # 9.76% of 282,600 / 12 = 23,550
    assert lines["accident"] == D("556.67")  # no cap: 1.67% of 33,333.33


def test_bulgaria_monthly_cap(real_catalog: Catalog) -> None:
    lines = _monthly(real_catalog, "BG", 60_000)
    assert lines["pension"] == D("189.06")  # 8.22% of the 2,300 ceiling
    assert lines["health"] == D("110.40")


@pytest.mark.parametrize("code", ["DE", "GB", "ES", "PL", "BG"])
def test_official_figures_agree_with_the_rates(real_catalog: Catalog, code: str) -> None:
    """A figure the bot quotes as official must be the number it calculates with."""
    country = _country(real_catalog, code)
    rates = {c.id: c for c in country.contributions}
    for key, figure in country.official.figures.items():
        if key.endswith("_rate") and key.removesuffix("_rate") in rates:
            assert D(figure.value) == rates[key.removesuffix("_rate")].rate, key
    if country.minimum_wage and "minimum_wage" in country.official.figures:
        assert D(country.official.figures["minimum_wage"].value) == country.minimum_wage.amount
    caps = {c.cap for c in country.contributions if c.cap is not None}
    for key in ("pension_cap", "max_insurable_income"):
        if key in country.official.figures:
            assert D(country.official.figures[key].value) in caps, key


@pytest.mark.parametrize("code", ["DE", "GB", "ES", "PL", "BG"])
def test_every_comparable_guide_figure_can_be_rechecked(real_catalog: Catalog, code: str) -> None:
    country = _country(real_catalog, code)
    for key in country.deel_guide.figures.keys() & country.official.figures.keys():
        assert country.deel_guide.figures[key].quote, f"{code}.{key} has no quote for check_deel_guides.py"


def test_figures_were_checked_within_the_data_period(real_catalog: Catalog) -> None:
    for country in real_catalog.countries:
        assert country.effective_from <= country.official.checked_at <= country.last_day
        assert country.deel_guide.checked_at <= country.last_day


def test_eor_price(real_catalog: Catalog) -> None:
    assert (real_catalog.eor.monthly_fee, real_catalog.eor.currency) == (D(599), "USD")


@pytest.mark.parametrize("code", ["DE", "GB", "ES", "PL", "BG"])
def test_one_hire_is_cheaper_on_eor_everywhere(real_catalog: Catalog, code: str) -> None:
    """With Deel's list price and every sourced entity cost, a single hire never justifies an
    entity, whatever the salary or horizon — the case EOR exists for."""
    from deel_advisor.fx import bundled_rates

    country = _country(real_catalog, code)
    rates = bundled_rates()
    eor = real_catalog.eor
    assert eor.payroll is not None
    fee = rates.convert(eor.monthly_fee, eor.currency, country.currency)
    payroll = rates.convert(eor.payroll.monthly_fee, eor.payroll.currency, country.currency)
    entity = calc.entity_cost(country, payroll)
    assert entity.bridge_months >= 2  # no entity runs payroll in under five weeks
    for months in (6, 12, 24, 60, 120):
        assert calc.plan(country, D(60_000), fee, 1, months, payroll).entity_saving < 0, months


def test_germany_breaks_even_from_five_people_over_a_year(real_catalog: Catalog) -> None:
    from deel_advisor.fx import bundled_rates

    germany = _country(real_catalog, "DE")
    rates = bundled_rates()
    fee = rates.convert(D(599), "USD", "EUR")
    entity = calc.entity_cost(germany, rates.convert(D(29), "USD", "EUR"))
    assert entity.admin_monthly == D("817.50")  # World Bank 218 h a year × Eurostat €45 an hour / 12
    assert calc.breakeven_people(entity, fee, 12) == 5
