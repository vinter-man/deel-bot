"""Shared fixtures: a synthetic country with round numbers, and the real bundled catalog."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from deel_advisor import catalog
from deel_advisor.catalog import Catalog
from deel_advisor.fx import Rates, parse_ecb
from deel_advisor.models import Country

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 29)


def country_data(**overrides: Any) -> dict[str, Any]:
    """A made-up country whose numbers are easy to check by hand."""
    src = "https://example.gov/rates"
    data: dict[str, Any] = {
        "country": "Testland",
        "code": "TL",
        "flag": "🏳️",
        "aliases": ["testland", "testlandia"],
        "currency": "EUR",
        "year": 2026,
        "effectiveFrom": "2026-01-01",
        "contributions": [
            {"id": "pension", "name": "Pension", "rate": "0.10", "cap": "60000", "capPeriod": "year", "source": src},
            {"id": "health", "name": "Health", "rate": "0.05", "cap": "3000", "capPeriod": "month", "source": src},
            {"id": "accident", "name": "Accident", "rate": "0.01", "estimate": True, "source": src},
        ],
        "minimumWage": {"amount": "1000", "period": "month", "source": src},
        "entity": {
            "setupCost": [{"name": "Registration", "amount": "2400", "kind": "official", "source": src}],
            "monthlyFixed": [
                {"name": "Accountant", "amount": "300", "kind": "estimate", "source": src},
                {"name": "Payroll", "amount": "50", "perEmployee": True, "payroll": True, "kind": "estimate",
                 "source": src},
            ],
            # Zero by default so the arithmetic in the older tests stays round; tests of these
            # costs set them explicitly (see test_calc.hidden).
            "setupTime": {"weeks": 0, "source": src},
            "adminTime": {"hoursPerYear": 0, "hoursSource": src, "hourlyCost": "0", "hourlyCostSource": src},
            "exitCost": [{"name": "Closing", "amount": "0", "kind": "estimate", "source": src}],
        },
        "deelGuide": {
            "url": "https://www.deel.com/hiring-guide/testland/",
            "checkedAt": "2026-10-01",
            "figures": {
                "minimum_wage": {"value": "950", "kind": "money", "currency": "EUR", "period": "month",
                                 "quote": "minimum wage is EUR 950 per month"},
                "pension_cap": {"value": "60000", "kind": "money", "currency": "EUR", "period": "year"},
            },
        },
        "official": {
            "checkedAt": "2026-10-01",
            "figures": {
                "minimum_wage": {"value": "1000", "kind": "money", "currency": "EUR", "period": "month",
                                 "source": src},
                "pension_cap": {"value": "60000", "kind": "money", "currency": "EUR", "period": "year",
                                "source": src},
            },
        },
    }  # fmt: skip
    data.update(overrides)
    return data


@pytest.fixture
def testland() -> Country:
    return Country.model_validate(country_data())


@pytest.fixture
def rates() -> Rates:
    return parse_ecb((FIXTURES / "ecb-daily.xml").read_bytes())


@pytest.fixture
def fixed_rates() -> Rates:
    """Round rates, for assertions that should not move when the ECB fixture is refreshed."""
    return Rates(TODAY, {"USD": Decimal("1.25"), "GBP": Decimal("0.8"), "PLN": Decimal("4")})


@pytest.fixture
def real_catalog() -> Catalog:
    return catalog.load()
