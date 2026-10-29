from decimal import Decimal

import pytest

from deel_advisor.models import Country
from deel_advisor.parser import CountryIndex, ParseError, Query, build_query, find_country, parse
from tests.conftest import country_data

CURRENCIES = {"EUR", "USD", "GBP", "PLN", "CHF"}


@pytest.fixture
def index(testland: Country) -> CountryIndex:
    other = Country.model_validate(
        country_data(country="United Otherland", code="UO", aliases=["united otherland", "otherland", "uo"])
    )
    return CountryIndex([testland, other])


def p(text: str, index: CountryIndex, kind: str | None = None) -> Query:
    return parse(text, index, CURRENCIES, kind)  # type: ignore[arg-type]


def err(text: str, index: CountryIndex, kind: str | None = None) -> ParseError:
    with pytest.raises(ParseError) as caught:
        p(text, index, kind)
    return caught.value


@pytest.mark.parametrize(
    ("text", "salary"),
    [
        ("Testland 80000", 80_000), ("testland 80k", 80_000), ("Testland 80K", 80_000),
        ("Testland 80,000", 80_000), ("Testland 80.000", 80_000), ("Testland 80 000", 80_000),
        ("Testland 1.200.000", 1_200_000), ("Testland 80.5k", 80_500), ("Testland 1.2m", 1_200_000),
        ("Testland 75000,50", Decimal("75000.50")), ("тестландия 80к", 80_000), ("Testland 80 тыс", 80_000),
    ],
)  # fmt: skip
def test_salary_formats(text: str, salary: Decimal, index: CountryIndex) -> None:
    query = p(text, index)
    assert query.kind == "cost"
    assert query.salary == salary
    assert query.currency is None


@pytest.mark.parametrize(
    ("text", "currency"),
    [("Testland 60000 EUR", "EUR"), ("Testland €60k", "EUR"), ("Testland 60k€", "EUR"), ("Testland $60k", "USD"),
     ("Testland 60000 usd", "USD"), ("Testland 60000 pounds", "GBP"), ("Testland 60000 zł", "PLN"),
     ("Testland 60000 chf", "CHF"), ("Testland 60000 евро", "EUR")],
)  # fmt: skip
def test_currencies(text: str, currency: str, index: CountryIndex) -> None:
    assert p(text, index).currency == currency


def test_free_text_plan(index: CountryIndex) -> None:
    query = p("Testland 80k 5 people", index)
    assert (query.kind, query.people, query.months) == ("plan", 5, 12)


@pytest.mark.parametrize(
    ("text", "people", "months"),
    [
        ("Testland 80k 5 people 24 months", 5, 24), ("Testland 80k x3", 3, 12), ("Testland 80k 3ppl", 3, 12),
        ("Testland 80k 5 человек на 2 года", 5, 24), ("Testland 80k 4 осіб 18 місяців", 4, 18),
        ("Testland 80k for 10 employees over 6mo", 10, 6), ("Testland 80k 5", 5, 12), ("Testland 80k 5 36", 5, 36),
    ],
)  # fmt: skip
def test_people_and_months(text: str, people: int, months: int, index: CountryIndex) -> None:
    query = p(text.replace(" over ", " "), index)
    assert (query.kind, query.people, query.months) == ("plan", people, months)


def test_positional_plan_command(index: CountryIndex) -> None:
    query = p("Testland 60000 5 120", index, "plan")
    assert (query.salary, query.people, query.months) == (60_000, 5, 120)


def test_compare_free_text(index: CountryIndex) -> None:
    query = p("Testland vs United Otherland 60k", index)
    assert query.kind == "compare"
    assert [c.code for c in query.countries] == ["TL", "UO"]


def test_monthly_salary(index: CountryIndex) -> None:
    for text in ("Testland 5000/mo", "Testland 5000 per month", "Testland 5000 monthly", "Testland 5k в месяц"):
        query = p(text, index)
        assert query.salary == 60_000, text
        assert query.salary_was_monthly


def test_per_year_is_the_default(index: CountryIndex) -> None:
    assert p("Testland 60000 per year", index).salary == 60_000


def test_cost_command_with_people_becomes_a_plan(index: CountryIndex) -> None:
    assert p("Testland 80k 5 people", index, "cost").kind == "plan"


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("", "empty"), ("80000", "no_country"), ("Testland", "no_salary"), ("Testland 500", "salary_too_low"),
        ("Testland 50m", "salary_too_high"), ("Testland 80k 0 people", "people_range"),
        ("Testland 80k 2 people 500 months", "months_range"), ("Testland Testland 80k", "same_country"),
        ("Testland 80k 5 6 7", "unexpected"), ("Testland 80k 5 1.5", "unexpected"),
    ],
)  # fmt: skip
def test_errors(text: str, code: str, index: CountryIndex) -> None:
    assert err(text, index).code == code


def test_unknown_word_suggests_a_country(index: CountryIndex) -> None:
    error = err("Testlnd 80k", index)
    assert error.code == "unknown_word"
    assert error.params == {"word": "testlnd", "suggestion": "Testland"}


def test_unknown_word_without_suggestion(index: CountryIndex) -> None:
    error = err("Narnia 80k", index)
    assert (error.code, error.params["suggestion"]) == ("unknown_word", "")


def test_symbol_for_unavailable_currency(index: CountryIndex) -> None:
    with pytest.raises(ParseError) as caught:
        parse("Testland £60k", index, {"EUR"})
    assert caught.value.code == "unknown_currency"


def test_command_arity(index: CountryIndex) -> None:
    assert err("Testland 60k", index, "compare").code == "need_two_countries"
    assert err("Testland Otherland 60k", index, "cost").code == "too_many_countries"


def test_build_query_validates_button_input(testland: Country) -> None:
    with pytest.raises(ParseError, match="salary_too_low"):
        build_query("cost", (testland,), Decimal(10))
    assert build_query("plan", (testland,), Decimal(50_000), people=3).people == 3


def test_find_country(index: CountryIndex) -> None:
    assert find_country("United Otherland", index).code == "UO"
    assert find_country("uo", index).code == "UO"
    with pytest.raises(ParseError, match="unknown_word"):
        find_country("Testland 80k", index)
    with pytest.raises(ParseError, match="no_country"):
        find_country("  ", index)


@pytest.mark.parametrize(
    ("text", "code"),
    [("Testland 80k 5 people 5 people", "twice"), ("Testland 80k x3 x4", "twice"),
     ("Testland 80k 12 months 24 months", "twice"), ("Testland 80k 90k", "unexpected"),
     ("Testland -80k", "unexpected")],
)  # fmt: skip
def test_contradictions_are_errors(text: str, code: str, index: CountryIndex) -> None:
    assert err(text, index).code == code


def test_salary_bounds_are_judged_in_euro(index: CountryIndex) -> None:
    def in_eur(amount: Decimal, currency: str) -> Decimal:
        return amount / {"EUR": 1, "JPY": 175, "PLN": 4}[currency]

    with pytest.raises(ParseError) as caught:
        parse("Testland 80000 jpy", index, CURRENCIES | {"JPY"}, in_eur=in_eur)
    assert (caught.value.code, caught.value.params) == ("salary_too_low", {"minimum": "1000 EUR"})
    assert parse("Testland 80000 pln", index, CURRENCIES | {"PLN"}, in_eur=in_eur).salary == 80_000


def test_no_salary_example_uses_the_country(index: CountryIndex) -> None:
    assert err("United Otherland", index).params == {"example": "United Otherland 80000"}


@pytest.mark.parametrize(
    ("text", "salary", "people", "months"),
    [("Testland 80 000 200 people", 80_000, 200, 12), ("Testland 80 000 120 months", 80_000, 1, 120),
     ("Testland 1 200 000 5 people", 1_200_000, 5, 12)],
)  # fmt: skip
def test_grouped_thousands_stop_before_a_count(
    text: str, salary: int, people: int, months: int, index: CountryIndex
) -> None:
    query = p(text, index)
    assert (query.salary, query.people, query.months) == (salary, people, months)
