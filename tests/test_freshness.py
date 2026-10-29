from datetime import date

from deel_advisor import freshness
from deel_advisor.models import Country
from tests.conftest import country_data


def test_guide_mismatch_is_reported(testland: Country) -> None:
    state = freshness.check(testland, date(2026, 10, 29))
    assert [m.key for m in state.mismatches] == ["minimum_wage"]  # pension_cap agrees
    mismatch = state.mismatches[0]
    assert (mismatch.deel.value, mismatch.official.value) == ("950", "1000")
    assert not state.outdated_year
    assert state.unchecked_days is None
    assert not state.clean


def test_outdated_year(testland: Country) -> None:
    assert freshness.check(testland, date(2027, 1, 1)).outdated_year


def test_unchecked_for_too_long(testland: Country) -> None:
    assert freshness.check(testland, date(2027, 6, 1)).unchecked_days == 243


def test_clean_country() -> None:
    data = country_data()
    data["deelGuide"]["figures"]["minimum_wage"]["value"] = "1000"
    country = Country.model_validate(data)
    assert freshness.check(country, date(2026, 10, 29)).clean


def test_figure_on_one_side_only_is_not_compared() -> None:
    data = country_data()
    del data["official"]["figures"]["minimum_wage"]
    assert freshness.mismatches(Country.model_validate(data)) == ()
