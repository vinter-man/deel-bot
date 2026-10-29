"""The schema refuses files that would make a reply wrong rather than crash it."""

import copy
import json
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from deel_advisor.models import Country, Figure, MinimumWage
from tests.conftest import country_data

SRC = "https://example.gov/x"


def _with(path: list[str | int], value: Any) -> dict[str, Any]:
    data = copy.deepcopy(country_data())
    node: Any = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return data


def test_valid_fixture(testland: Country) -> None:
    assert testland.code == "TL"
    assert testland.effective_from == date(2026, 1, 1)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (["contributions", 0, "rate"], "1.5", "less than 1"),
        (["contributions", 0, "rate"], 0.1, "JSON strings"),  # a float is refused, not rounded
        (["contributions", 0, "source"], "http://example.gov", "https"),
        (["contributions", 0, "capPeriod"], None, "go together"),
        (["contributions", 1, "id"], "pension", "duplicate"),
        (["aliases"], ["Testland"], "lower-case"),
        (["effectiveFrom"], "2025-12-31", "data year"),
        (["code"], "TLX", "pattern"),
        (["entity", "setupCost"], [], "at least 1"),
        (["official", "figures", "minimum_wage", "currency"], "USD", "not EUR"),
        (["contributions", 0, "unknown"], 1, "Extra inputs"),
    ],
)
def test_rejects(path: list[str | int], value: Any, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Country.model_validate(_with(path, value))


def test_rejects_float_rate_from_json() -> None:
    data = country_data()
    data["contributions"][0]["rate"] = 0.1
    with pytest.raises(ValidationError):
        Country.model_validate_json(json.dumps(data))


def test_setup_cost_cannot_be_per_employee() -> None:
    item = {"name": "Fee", "amount": "10", "perEmployee": True, "kind": "official", "source": SRC}
    with pytest.raises(ValidationError, match="one-off"):
        Country.model_validate(_with(["entity", "setupCost"], [item]))


def test_minimum_wage_annual() -> None:
    hourly = MinimumWage.model_validate({"amount": "13.90", "period": "hour", "hoursPerYear": 2080, "source": SRC})
    assert hourly.annual == 28_912
    spain = MinimumWage.model_validate({"amount": "1221", "period": "month", "paymentsPerYear": 14, "source": SRC})
    assert spain.annual == 17_094
    yearly = MinimumWage.model_validate({"amount": "20000", "period": "year", "source": SRC})
    assert yearly.annual == 20_000


def test_hourly_minimum_wage_needs_hours() -> None:
    with pytest.raises(ValidationError, match="hoursPerYear"):
        MinimumWage.model_validate({"amount": "13.90", "period": "hour", "source": SRC})


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        ({"value": "0.093", "kind": "rate"}, {"value": "0.0930", "kind": "rate"}, True),
        ({"value": "12.82", "kind": "money", "currency": "EUR", "period": "hour"},
         {"value": "13.90", "kind": "money", "currency": "EUR", "period": "hour"}, False),
        ({"value": "1213", "kind": "money", "currency": "BGN", "period": "month"},
         {"value": "1213", "kind": "money", "currency": "EUR", "period": "month"}, False),
        ({"value": "EUR", "kind": "text"}, {"value": " eur ", "kind": "text"}, True),
        ({"value": "1000", "kind": "money", "currency": "EUR", "period": "month"},
         {"value": "1000", "kind": "money", "currency": "EUR", "period": "year"}, False),
    ],
)  # fmt: skip
def test_figure_comparison(a: dict[str, str], b: dict[str, str], same: bool) -> None:
    assert Figure.model_validate(a).same_as(Figure.model_validate(b)) is same


def test_figure_shape() -> None:
    with pytest.raises(ValidationError, match="must be a number"):
        Figure.model_validate({"value": "about 9%", "kind": "rate"})
    with pytest.raises(ValidationError, match="currency is required"):
        Figure.model_validate({"value": "100", "kind": "money"})


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [(["contributions", 0, "source"], "http://example.gov", "sources must be https"),
     (["contributions", 0, "rate"], 0.1, 'write money and rates as JSON strings ("0.093"), not decimal numbers')],
)  # fmt: skip
def test_error_messages_say_what_to_fix(path: list[str | int], value: Any, message: str) -> None:
    # The person editing a data file reads these; they must say what is wrong, verbatim.
    with pytest.raises(ValidationError) as caught:
        Country.model_validate(_with(path, value))
    assert message in str(caught.value)


def test_thresholds_per_payslip() -> None:
    from deel_advisor.models import Contribution

    c = Contribution.model_validate({"id": "x", "name": "Test", "rate": "0.1", "source": SRC, "cap": "1200",
                                     "capPeriod": "year", "floor": "300", "floorPeriod": "month"})  # fmt: skip
    assert (c.monthly_cap, c.monthly_floor) == (100, 300)
    plain = Contribution.model_validate({"id": "x", "name": "Test", "rate": "0.1", "source": SRC})
    assert (plain.monthly_cap, plain.monthly_floor) == (None, None)
