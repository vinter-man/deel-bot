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


def test_boundaries_are_exclusive(testland: Country) -> None:
    last_day = date(2026, 12, 31)
    assert not freshness.check(testland, last_day).outdated_year  # still valid on its last day
    assert freshness.check(testland, date(2027, 1, 1)).outdated_year
    checked = testland.official.checked_at
    exactly = date.fromordinal(checked.toordinal() + freshness.STALE_AFTER_DAYS)
    assert freshness.check(testland, exactly).unchecked_days is None  # 180 days is still fine
    assert freshness.check(testland, date.fromordinal(exactly.toordinal() + 1)).unchecked_days == 181


def test_result_names_its_country(testland: Country) -> None:
    assert freshness.check(testland, date(2026, 10, 29)).country is testland
