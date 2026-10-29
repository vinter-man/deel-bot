"""The free-text parser: what people really type, what they type by mistake, and what a bored
tester types to see what happens. Every input either parses to exactly the intended query or is
refused with an error that names the problem — never a silently wrong number.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from deel_advisor.catalog import Catalog
from deel_advisor.models import Country
from deel_advisor.parser import (
    MAX_MONTHS,
    MAX_PEOPLE,
    CountryIndex,
    ParseError,
    Query,
    build_query,
    find_country,
    parse,
)
from tests.conftest import country_data

D = Decimal
CURRENCIES = {"EUR", "USD", "GBP", "PLN", "CHF", "JPY"}


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


# --- salaries -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "salary"),
    [
        ("Testland 80000", 80_000), ("testland 80k", 80_000), ("TESTLAND 80K", 80_000),
        ("Testland 80,000", 80_000), ("Testland 80.000", 80_000), ("Testland 80 000", 80_000),
        ("Testland 1.200.000", 1_200_000), ("Testland 1,200,000", 1_200_000), ("Testland 1 200 000", 1_200_000),
        ("Testland 80.5k", 80_500), ("Testland 80,5k", 80_500), ("Testland 1.2m", 1_200_000),
        ("Testland 75000,50", D("75000.50")), ("Testland 75000.50", D("75000.50")),
        ("testlandia 80k", 80_000), ("Testland 80 tys.", 80_000), ("Testland 80 tsd", 80_000),
        ("Testland 80 mil", 80_000), ("Testland 80 хил.", 80_000), ("Testland 1,2 Mio.", 1_200_000),
        ("Testland 1,5 mln", 1_500_000), ("Testland 80tys", 80_000), ("Testland 80 000", 80_000),
        ("  Testland   80000  ", 80_000), ("Testland, 80000!", 80_000), ("(Testland) 80000", 80_000),
        ("Testland 80000 ???", 80_000), ("Testland: 80000;", 80_000),
    ],
)  # fmt: skip
def test_salary_formats(text: str, salary: Decimal, index: CountryIndex) -> None:
    query = p(text, index)
    assert query.kind == "cost"
    assert query.salary == salary
    assert query.currency is None


@pytest.mark.parametrize("text", ["80000 Testland", "80k testland", "€60k Testland"])
def test_order_does_not_matter(text: str, index: CountryIndex) -> None:
    assert p(text, index).countries[0].code == "TL"


@pytest.mark.parametrize(
    ("text", "currency"),
    [("Testland 60000 EUR", "EUR"), ("Testland €60k", "EUR"), ("Testland 60k€", "EUR"), ("Testland $60k", "USD"),
     ("Testland 60000 usd", "USD"), ("Testland 60000 pounds", "GBP"), ("Testland 60000 zł", "PLN"),
     ("Testland 60000 chf", "CHF"), ("Testland 60000 euro", "EUR"), ("Testland 60000 евро", "EUR"),
     ("Testland 60000 Pfund", "GBP"), ("Testland 60000 dólares", "USD"), ("Testland 60000 złotych", "PLN"),
     ("Testland £60k", "GBP"), ("Testland 60000 jpy", "JPY"), ("Testland 60k zł", "PLN")],
)  # fmt: skip
def test_currencies(text: str, currency: str, index: CountryIndex) -> None:
    assert p(text, index).currency == currency


def test_last_currency_wins_over_none_but_symbol_sets_it(index: CountryIndex) -> None:
    assert p("Testland EUR 60000", index).currency == "EUR"  # the code before the amount still counts


@pytest.mark.parametrize(
    "text", ["Testland 5000/mo", "Testland 5000 per month", "Testland 5000 monthly", "Testland 5k pro Monat",
             "Testland 5k al mes", "Testland 5k miesięcznie", "Testland 5k на месец", "Testland 5k/month",
             "Testland 5k mensual"],
)  # fmt: skip
def test_monthly_salary(text: str, index: CountryIndex) -> None:
    query = p(text, index)
    assert query.salary == 60_000, text
    assert query.salary_was_monthly


@pytest.mark.parametrize("text", ["Testland 60000 per year", "Testland 60000 a year", "Testland 60000 al año"])
def test_per_year_is_the_default(text: str, index: CountryIndex) -> None:
    query = p(text, index)
    assert (query.salary, query.salary_was_monthly) == (60_000, False)


# --- team and horizon -----------------------------------------------------------------------


def test_free_text_plan(index: CountryIndex) -> None:
    query = p("Testland 80k 5 people", index)
    assert (query.kind, query.people, query.months) == ("plan", 5, 12)


@pytest.mark.parametrize(
    ("text", "people", "months"),
    [
        ("Testland 80k 5 people 24 months", 5, 24), ("Testland 80k x3", 3, 12), ("Testland 80k ×3", 3, 12),
        ("Testland 80k 3ppl", 3, 12), ("Testland 80k 5 Personen 2 Jahre", 5, 24),
        ("Testland 80k 4 osoby 18 miesięcy", 4, 18), ("Testland 80k 7 personas 3 años", 7, 36),
        ("Testland 80k 2 служители 6 месеца", 2, 6), ("Testland 80k for 10 employees 6mo", 10, 6),
        ("Testland 80k 5", 5, 12), ("Testland 80k 5 36", 5, 36), ("Testland 80k 24 months 5 people", 5, 24),
        ("Testland 80k 1 year", 1, 12), ("Testland 80k 10 years", 1, 120), ("Testland 80k 1 person", 1, 12),
    ],
)  # fmt: skip
def test_people_and_months(text: str, people: int, months: int, index: CountryIndex) -> None:
    query = p(text, index)
    assert (query.kind, query.people, query.months) == ("plan", people, months)


def test_positional_plan_command(index: CountryIndex) -> None:
    query = p("Testland 60000 5 120", index, "plan")
    assert (query.salary, query.people, query.months) == (60_000, 5, 120)


@pytest.mark.parametrize(
    ("text", "salary", "people", "months"),
    [("Testland 80 000 200 people", 80_000, 200, 12), ("Testland 80 000 120 months", 80_000, 1, 120),
     ("Testland 1 200 000 5 people", 1_200_000, 5, 12), ("Testland 80 000 5 120", 80_000, 5, 120)],
)  # fmt: skip
def test_grouped_thousands_stop_before_a_count(
    text: str, salary: int, people: int, months: int, index: CountryIndex
) -> None:
    query = p(text, index)
    assert (query.salary, query.people, query.months) == (salary, people, months)


def test_bounds_are_inclusive(index: CountryIndex) -> None:
    assert p(f"Testland 80k {MAX_PEOPLE} people {MAX_MONTHS} months", index).people == MAX_PEOPLE
    assert p("Testland 1000", index).salary == 1000
    assert p("Testland 10m", index).salary == 10_000_000
    assert err(f"Testland 80k {MAX_PEOPLE + 1} people", index).code == "people_range"
    assert err(f"Testland 80k {MAX_MONTHS + 1} months", index).code == "months_range"
    assert err("Testland 999.99", index).code == "salary_too_low"
    assert err("Testland 10000000.01", index).code == "salary_too_high"


# --- kinds of question ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "text", ["Testland vs United Otherland 60k", "Testland United Otherland 60k", "testland и otherland 60k",
             "Testland gegen Otherland 60k", "Testland contra uo 60k", "Testland vs. Otherland 60000 EUR"],
)  # fmt: skip
def test_compare_free_text(text: str, index: CountryIndex) -> None:
    query = p(text, index)
    assert query.kind == "compare"
    assert [c.code for c in query.countries] == ["TL", "UO"]


def test_multiword_alias_beats_its_prefix(index: CountryIndex) -> None:
    # "united otherland" must match as one country, not "united" as an unknown word.
    assert [c.code for c in p("united otherland 80k", index).countries] == ["UO"]


def test_cost_command_with_people_becomes_a_plan(index: CountryIndex) -> None:
    assert p("Testland 80k 5 people", index, "cost").kind == "plan"


def test_command_arity(index: CountryIndex) -> None:
    assert err("Testland 60k", index, "compare").code == "need_two_countries"
    assert err("Testland Otherland 60k", index, "cost").code == "too_many_countries"
    assert err("Testland Otherland 60k", index, "plan").code == "too_many_countries"


# --- what goes wrong ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("", "empty"), ("   ", "empty"), ("\n\t", "empty"), ("80000", "no_country"), ("Testland", "no_salary"),
        ("Testland 500", "salary_too_low"), ("Testland 0", "salary_too_low"), ("Testland 50m", "salary_too_high"),
        ("Testland 80k 0 people", "people_range"), ("Testland 80k 2 people 500 months", "months_range"),
        ("Testland 80k 0 months", "months_range"), ("Testland Testland 80k", "same_country"),
        ("Testland 80k 5 6 7", "unexpected"), ("Testland 80k 5 1.5", "unexpected"),
        ("Testland 80k 90k", "unexpected"), ("Testland -80k", "unexpected"), ("Testland 80k -5 people", "unexpected"),
        ("Testland 80k 5 people 5 people", "twice"), ("Testland 80k x3 x4", "twice"),
        ("Testland 80k 12 months 24 months", "twice"), ("Testland 80k 12 months 1 year", "twice"),
        ("Testland 1e6", "unknown_word"), ("Testland 80k 🙂", "unexpected"),
        ("Testland 80k <script>", "unknown_word"), ("Testland 0x1F", "unknown_word"),
        ("Testland 80k bgn", "unknown_currency"), ("Testland 80k лв", "unknown_currency"),
    ],
)  # fmt: skip
def test_errors(text: str, code: str, index: CountryIndex) -> None:
    assert err(text, index).code == code


def test_unknown_word_suggests_a_country(index: CountryIndex) -> None:
    error = err("Testlnd 80k", index)
    assert error.code == "unknown_word"
    assert error.params == {"word": "testlnd", "suggestion": "Testland"}


def test_unknown_word_without_suggestion(index: CountryIndex) -> None:
    assert err("Narnia 80k", index).params == {"word": "narnia", "suggestion": ""}


def test_symbol_for_unavailable_currency(index: CountryIndex) -> None:
    with pytest.raises(ParseError) as caught:
        parse("Testland £60k", index, {"EUR"})
    assert (caught.value.code, caught.value.params) == ("unknown_currency", {"currency": "GBP"})


def test_word_for_unavailable_currency(index: CountryIndex) -> None:
    with pytest.raises(ParseError) as caught:
        parse("Testland 60k pounds", index, {"EUR"})
    assert caught.value.code == "unknown_currency"


def test_three_letter_word_that_is_no_currency(index: CountryIndex) -> None:
    # "xyz" is not an ECB code: it is reported as an unknown word, not as a currency.
    assert err("Testland 80k xyz", index).code == "unknown_word"


def test_no_salary_example_uses_the_country(index: CountryIndex) -> None:
    assert err("United Otherland", index).params == {"example": "United Otherland 80000"}


def test_very_long_input_is_refused_quickly(index: CountryIndex) -> None:
    # A wall of junk ends at the first unknown word; nothing is quadratic in the input.
    assert err("Testland 80k " + "blah " * 5000, index).code == "unknown_word"
    assert err("Testland " + "9" * 400, index).code == "salary_too_high"


def test_huge_people_count_is_a_range_error_not_a_crash(index: CountryIndex) -> None:
    assert err("Testland 80k " + "9" * 50 + " people", index).code == "people_range"


# --- salary bounds in euro ------------------------------------------------------------------


def _in_eur(amount: Decimal, currency: str) -> Decimal:
    return amount / {"EUR": 1, "JPY": 175, "PLN": 4, "USD": D("1.25"), "GBP": D("0.8")}[currency]


def test_salary_bounds_are_judged_in_euro(index: CountryIndex) -> None:
    with pytest.raises(ParseError) as caught:
        parse("Testland 80000 jpy", index, CURRENCIES, in_eur=_in_eur)
    assert (caught.value.code, caught.value.params) == ("salary_too_low", {"minimum": "1,000 EUR"})
    assert parse("Testland 80000 pln", index, CURRENCIES, in_eur=_in_eur).salary == 80_000
    with pytest.raises(ParseError, match="salary_too_high"):
        parse("Testland 9m gbp", index, CURRENCIES, in_eur=_in_eur)  # £9m ≈ €11.25m


def test_bounds_without_currency_use_the_country_currency(testland: Country) -> None:
    pln_land = Country.model_validate(country_data(code="PZ", aliases=["pzland"], currency="PLN",
                                                   official={"checkedAt": "2026-10-01", "figures": {}}))  # fmt: skip
    with pytest.raises(ParseError, match="salary_too_low"):
        parse("pzland 3000", CountryIndex([pln_land]), CURRENCIES, in_eur=_in_eur)  # 3000 PLN ≈ €750


# --- buttons and /sources -------------------------------------------------------------------


def test_build_query_validates_button_input(testland: Country) -> None:
    with pytest.raises(ParseError, match="salary_too_low"):
        build_query("cost", (testland,), D(10))
    with pytest.raises(ParseError, match="people_range"):
        build_query("plan", (testland,), D(50_000), people=0)
    with pytest.raises(ParseError, match="same_country"):
        build_query("compare", (testland, testland), D(50_000))
    assert build_query("plan", (testland,), D(50_000), people=3).people == 3


def test_find_country(index: CountryIndex) -> None:
    assert find_country("United Otherland", index).code == "UO"
    assert find_country("  UO  ", index).code == "UO"
    with pytest.raises(ParseError, match="unknown_word"):
        find_country("Testland 80k", index)
    with pytest.raises(ParseError, match="unknown_word"):
        find_country("Testland Otherland", index)
    with pytest.raises(ParseError, match="no_country"):
        find_country("  ", index)


# --- the real five countries, in their own languages -----------------------------------------


@pytest.mark.parametrize(
    ("text", "code"),
    [("Deutschland 80k", "DE"), ("Alemania 80k", "DE"), ("Niemcy 80k", "DE"), ("Германия 80k", "DE"),
     ("Großbritannien 80k", "GB"), ("Reino Unido 80k", "GB"), ("Wielka Brytania 80k", "GB"),
     ("Великобритания 80k", "GB"), ("UK 80k", "GB"), ("England 80k", "GB"), ("España 80k", "ES"),
     ("Espana 80k", "ES"), ("Spanien 80k", "ES"), ("Hiszpania 80k", "ES"), ("Испания 80k", "ES"),
     ("Polska 80k", "PL"), ("Polen 80k", "PL"), ("Polonia 80k", "PL"), ("Полша 80k", "PL"),
     ("България 60k", "BG"), ("Bułgaria 60k", "BG"), ("Bulgarien 60k", "BG")],
)  # fmt: skip
def test_every_country_in_every_language(real_catalog: Catalog, text: str, code: str) -> None:
    query = parse(text, real_catalog.index, CURRENCIES)
    assert query.countries[0].code == code


def test_real_aliases_are_unique_and_unambiguous(real_catalog: Catalog) -> None:
    seen: dict[str, str] = {}
    for country in real_catalog.countries:
        for alias in country.aliases:
            assert seen.setdefault(alias, country.code) == country.code, alias


# --- the word in the error is the word the user typed (holes found by mutation testing) ----------


@pytest.mark.parametrize(
    ("text", "code", "params"),
    [
        ("Testland 80k 5 6 7", "unexpected", {"word": "7"}),
        ("Testland 80k 90k", "unexpected", {"word": "90k"}),
        ("Testland -80k", "unexpected", {"word": "-80k"}),
        ("Testland 80k 🙂", "unexpected", {"word": "🙂"}),
        ("Testland 80k 5 people 6 people", "twice", {"word": "6 people"}),
        ("Testland 80k x3 x4", "twice", {"word": "x4"}),
        ("Testland 80k 2ppl 3ppl", "twice", {"word": "3ppl"}),
        ("Testland 80k 12 months 24 months", "twice", {"word": "24 months"}),
        ("Testland 80k 1yr 2yrs", "twice", {"word": "2yrs"}),
        ("Testland 80k bgn", "unknown_currency", {"currency": "BGN"}),
        ("Testland 50m", "salary_too_high", {"maximum": "10,000,000 EUR"}),
        ("Testland 80k 0 people", "people_range", {"maximum": str(MAX_PEOPLE)}),
        ("Testland 80k 0 months", "months_range", {"maximum": str(MAX_MONTHS)}),
    ],
)  # fmt: skip
def test_error_params_name_the_problem(text: str, code: str, params: dict[str, str], index: CountryIndex) -> None:
    error = err(text, index)
    assert (error.code, error.params) == (code, params)


@pytest.mark.parametrize(
    ("text", "people", "months"),
    [("Testland 80k 2yrs", 1, 24), ("Testland 80k 3mo", 1, 3), ("Testland 80k 24 months", 1, 24),
     ("Testland 5000 per month 3 people", 3, 12), ("Testland 60000 per year 5 people", 5, 12),
     ("Testland 60000 a year 4", 4, 12)],
)  # fmt: skip
def test_units_do_not_swallow_the_next_number(text: str, people: int, months: int, index: CountryIndex) -> None:
    query = p(text, index)
    assert (query.kind, query.people, query.months) == ("plan", people, months)


@pytest.mark.parametrize("sep", ["-", "—", "/", "&", "+"])
def test_separators_between_countries(sep: str, index: CountryIndex) -> None:
    query = p(f"Testland {sep} Otherland 60k", index)
    assert [c.code for c in query.countries] == ["TL", "UO"]


def test_a_lone_year_word_is_not_silently_eaten(index: CountryIndex) -> None:
    assert err("Testland 80k brutto year", index).params["word"] == "year"


def test_currency_symbol_on_its_own(index: CountryIndex) -> None:
    assert p("Testland 60000 €", index).currency == "EUR"
    assert p("Testland 60000 £", index).currency == "GBP"


def test_grouping_after_a_multiword_country(index: CountryIndex) -> None:
    assert p("United Otherland 80 000", index).salary == 80_000


def test_country_name_and_code_work_without_aliases() -> None:
    plain = Country.model_validate(country_data(country="Plainland", code="PX", aliases=["somewhere"]))
    index = CountryIndex([plain])
    assert p("plainland 80k", index).countries[0].code == "PX"
    assert p("PX 80k", index).countries[0].code == "PX"


def test_suggestions_need_a_close_match(index: CountryIndex) -> None:
    assert err("Testlxyz 80k", index).params["suggestion"] == ""  # 62% similar: too far
    assert err("united otherlnd 80k", index).code == "unknown_word"
    assert index.suggest("united otherlnd") == "United Otherland"  # multi-word aliases too


def test_build_query_defaults(testland: Country) -> None:
    query = build_query("cost", (testland,), D(50_000))
    assert (query.people, query.months, query.currency, query.salary_was_monthly) == (1, 12, None, False)
    assert build_query("plan", (testland,), D(50_000), months=1).months == 1


def test_find_country_error_params(index: CountryIndex) -> None:
    with pytest.raises(ParseError) as caught:
        find_country("Otherlnd", index)
    assert (caught.value.code, caught.value.params) == (
        "unknown_word",
        {"word": "otherlnd", "suggestion": "United Otherland"},
    )
    with pytest.raises(ParseError) as caught:
        find_country("Zzzz Yyyy", index)
    assert caught.value.params == {"word": "zzzz yyyy", "suggestion": ""}
    with pytest.raises(ParseError) as caught:
        find_country("", index)
    assert caught.value.code == "no_country"


def test_months_alone_make_a_plan(index: CountryIndex) -> None:
    assert p("Testland 80k 24 months", index).kind == "plan"
