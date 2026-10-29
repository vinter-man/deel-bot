"""Turns `/cost Bulgaria 60000 EUR` and `Germany 80k 5 people` into a `Query`, without an LLM.

One tokenizer serves both the commands and free text. Every token is classified — country,
amount, currency, people, months, filler — and anything left over is an error with a name and
the offending word, so the reply can say what was not understood rather than "invalid input".
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Literal

from deel_advisor.models import Country

Kind = Literal["cost", "compare", "plan"]
# (amount, currency) -> amount in EUR; the parser knows nothing about exchange rates itself.
InEur = Callable[[Decimal, str], Decimal]

MIN_SALARY = Decimal(1_000)
MAX_SALARY = Decimal(10_000_000)
MAX_PEOPLE = 10_000
MAX_MONTHS = 120
DEFAULT_MONTHS = 12

_SYMBOLS = {"€": "EUR", "$": "USD", "£": "GBP", "zł": "PLN"}
_CURRENCY_WORDS = {
    **dict.fromkeys(("euro", "euros", "евро", "євро", "eur"), "EUR"),
    **dict.fromkeys(("usd", "dollar", "dollars", "доллар", "долларов", "доларів", "долар"), "USD"),
    **dict.fromkeys(("gbp", "pound", "pounds", "фунт", "фунтов", "фунтів"), "GBP"),
    **dict.fromkeys(("pln", "zloty", "zł", "злотых", "злотих", "злотый"), "PLN"),
    # Not an ECB currency any more (Bulgaria uses the euro since 2026), but people still type it.
    **dict.fromkeys(("bgn", "лв", "лева", "leva"), "BGN"),
}
_PEOPLE_WORDS = {
    "people", "person", "persons", "ppl", "employee", "employees", "hire", "hires", "heads", "head",
    "чел", "человек", "человека", "людей", "люди", "сотрудник", "сотрудника", "сотрудников",
    "осіб", "особи", "особа", "працівників", "працівники", "співробітників", "співробітники",
}  # fmt: skip
_MONTH_WORDS = {
    "month", "months", "mo", "mos", "мес", "месяц", "месяца", "месяцев", "міс", "місяць", "місяці",
    "місяців",
}  # fmt: skip
_YEAR_WORDS = {"year", "years", "yr", "yrs", "год", "года", "лет", "рік", "роки", "років"}
# Marks the salary as monthly ("5000 per month", "5k/mo"); the horizon uses _MONTH_WORDS instead.
_MONTHLY_SALARY = {"monthly", "/mo", "/month", "ежемесячно", "щомісяця"}
_PER_WORDS = {"per", "a", "в", "на"}
_FILLER = {
    "vs", "versus", "and", "or", "with", "for", "in", "of", "gross", "salary", "annual", "yearly",
    "pa", "p.a.", "/yr", "/year", "brutto", "to", "compare", "plan", "cost", "people:", "x",
    "и", "или", "с", "со", "для", "по", "против", "зарплата", "зп", "брутто", "в", "на", "за",
    "і", "й", "та", "або", "з", "із", "проти", "у",
}  # fmt: skip

_AMOUNT = re.compile(r"^(?P<pre>[€$£])?(?P<num>\d+(?:[.,]\d+)*)(?P<mult>k|к|тыс|тис|m|м|млн)?(?P<post>[€$£]|zł)?$")
_TIMES = re.compile(r"^[x×](?P<n>\d+)$")
_ATTACHED_UNIT = re.compile(r"^(?P<n>\d+)(?P<unit>[^\d.,]+)$")
_MULTIPLIERS = {
    "k": 1_000, "к": 1_000, "тыс": 1_000, "тис": 1_000, "m": 1_000_000, "м": 1_000_000, "млн": 1_000_000,
}  # fmt: skip


class ParseError(Exception):
    """A user mistake. `code` picks the localized message, `params` fill it in."""

    def __init__(self, code: str, **params: str) -> None:
        super().__init__(code)
        self.code = code
        self.params = params


@dataclass(frozen=True, slots=True)
class Query:
    kind: Kind
    countries: tuple[Country, ...]
    salary: Decimal
    # None means "in the country's own currency".
    currency: str | None = None
    people: int = 1
    months: int = DEFAULT_MONTHS
    salary_was_monthly: bool = False


@dataclass(slots=True)
class _Found:
    countries: list[Country] = field(default_factory=list)
    salary: Decimal | None = None
    currency: str | None = None
    people: int | None = None
    months: int | None = None
    bare: list[int] = field(default_factory=list)
    monthly: bool = False

    def set_people(self, value: int, word: str) -> None:
        if self.people is not None:
            raise ParseError("twice", word=word)
        self.people = value

    def set_months(self, value: int, word: str) -> None:
        if self.months is not None:
            raise ParseError("twice", word=word)
        self.months = value


class CountryIndex:
    """Alias lookup. Multi-word names ("united kingdom") are matched longest-first."""

    def __init__(self, countries: Iterable[Country]) -> None:
        self.by_alias: dict[tuple[str, ...], Country] = {}
        for country in countries:
            for alias in (*country.aliases, country.country.lower(), country.code.lower()):
                self.by_alias[tuple(alias.split())] = country
        self.longest = max(len(key) for key in self.by_alias)

    def match(self, tokens: list[str], start: int) -> tuple[Country, int] | None:
        for size in range(min(self.longest, len(tokens) - start), 0, -1):
            country = self.by_alias.get(tuple(tokens[start : start + size]))
            if country is not None:
                return country, size
        return None

    def suggest(self, word: str) -> str | None:
        names = {" ".join(key): country.country for key, country in self.by_alias.items()}
        close = difflib.get_close_matches(word, names, n=1, cutoff=0.7)
        return names[close[0]] if close else None


def _number(text: str) -> Decimal | None:
    """`80000`, `80,000`, `80.000`, `1.200.000` (thousands), `80.5`, `80,5` (decimal).

    A single separator followed by exactly three digits is read as thousands: "80,000" is a
    salary far more often than eighty with three decimals.
    """
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", text):
        return Decimal(re.sub(r"[.,]", "", text))
    if re.fullmatch(r"\d+([.,]\d+)?", text):
        try:
            return Decimal(text.replace(",", "."))
        except InvalidOperation:  # pragma: no cover - the regex already guarantees a number
            return None
    return None


def _tokens(text: str) -> list[str]:
    raw = text.lower().replace(" ", " ").replace(" ", " ")
    # Split a glued symbol or slash off a word ("80k€" stays, "80k/mo" -> "80k /mo").
    raw = re.sub(r"(?<=\S)(/(?:mo|month|yr|year))\b", r" \1", raw)
    words = [w.strip(",;:!?()\"'") for w in raw.split()]
    words = [w for w in words if w]
    merged: list[str] = []
    first_number: int | None = None
    counted = _PEOPLE_WORDS | _MONTH_WORDS | _YEAR_WORDS
    for i, word in enumerate(words):
        # "80 000" typed with a space: glue three-digit groups back onto the first number, and
        # only the first — in "/plan Germany 60000 5 120" the 5 and the 120 are separate — and
        # never a group that counts something ("80 000 200 people").
        nxt = words[i + 1] if i + 1 < len(words) else ""
        if (
            first_number == len(merged) - 1
            and re.fullmatch(r"\d{3}", word)
            and nxt not in counted
            and re.fullmatch(r"[€$£]?\d{1,3}(\s\d{3})*", merged[-1])
        ):
            merged[-1] = f"{merged[-1]} {word}"
            continue
        if first_number is None and re.match(r"[€$£]?\d", word):
            first_number = len(merged)
        merged.append(word)
    return [w.replace(" ", "") for w in merged]


def _amount(token: str, currencies: Collection[str]) -> tuple[Decimal, str | None] | None:
    match = _AMOUNT.match(token)
    if not match:
        return None
    number = _number(match["num"])
    if number is None:
        return None
    if match["mult"]:
        number *= _MULTIPLIERS[match["mult"]]
    symbol = match["pre"] or match["post"]
    currency = _SYMBOLS[symbol] if symbol else None
    if currency is not None and currency not in currencies:
        raise ParseError("unknown_currency", currency=currency)
    return number, currency


def _currency(token: str, currencies: Collection[str]) -> str | None:
    code = _SYMBOLS.get(token) or _CURRENCY_WORDS.get(token)
    if code is None and re.fullmatch(r"[a-z]{3}", token):
        code = token.upper()
    if code is None or code in currencies:
        return code
    if code in _SYMBOLS.values() or code in _CURRENCY_WORDS.values():
        raise ParseError("unknown_currency", currency=code)
    return None  # some other three-letter word: let the caller decide what it is


def _scan(text: str, index: CountryIndex, currencies: Collection[str]) -> _Found:
    tokens = _tokens(text)
    found = _Found()
    salary_at = -1
    i = 0
    while i < len(tokens):
        token = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""

        hit = index.match(tokens, i)
        if hit is not None:
            found.countries.append(hit[0])
            i += hit[1]
            continue

        times = _TIMES.match(token)
        attached = _ATTACHED_UNIT.match(token)
        if times:
            found.set_people(int(times["n"]), token)
        elif attached and attached["unit"] in _PEOPLE_WORDS:
            found.set_people(int(attached["n"]), token)
        elif attached and attached["unit"] in _MONTH_WORDS | _YEAR_WORDS and found.salary is not None:
            factor = 12 if attached["unit"] in _YEAR_WORDS else 1
            found.set_months(int(attached["n"]) * factor, token)
        elif token.isdigit() and found.salary is not None and nxt in _PEOPLE_WORDS:
            found.set_people(int(token), f"{token} {nxt}")
            i += 1
        elif token.isdigit() and found.salary is not None and nxt in _MONTH_WORDS | _YEAR_WORDS:
            found.set_months(int(token) * (12 if nxt in _YEAR_WORDS else 1), f"{token} {nxt}")
            i += 1
        elif token in _MONTHLY_SALARY:
            found.monthly = True
        elif token in _PER_WORDS and nxt in _MONTH_WORDS:
            found.monthly = True  # "per month", "в месяц"
            i += 1
        elif token in _PER_WORDS and nxt in _YEAR_WORDS:
            i += 1  # "per year": the default, nothing to do
        elif token in _MULTIPLIERS and found.salary is not None and salary_at == i - 1:
            found.salary *= _MULTIPLIERS[token]  # "80 тыс", "1.2 млн"
        elif (code := _currency(token, currencies)) is not None:
            found.currency = code
        elif (amount := _amount(token, currencies)) is not None:
            value, currency = amount
            if found.salary is None:
                found.salary = value
                found.currency = currency or found.currency
                salary_at = i
            elif token.isdigit():
                found.bare.append(int(value))
            else:
                # "80k 90k", "5.5": a second amount is not a team size or a horizon.
                raise ParseError("unexpected", word=token)
        elif token in _FILLER or token in _PEOPLE_WORDS or token in {"-", "—", "/", "&", "+"}:
            pass
        elif re.match(r"-\d", token):
            raise ParseError("unexpected", word=token)  # a negative salary or count
        elif re.search(r"[^\W\d_]", token):
            # A country we do not cover, a typo, or a currency ECB does not publish.
            raise ParseError("unknown_word", word=token, suggestion=index.suggest(token) or "")
        else:
            raise ParseError("unexpected", word=token)
        i += 1
    return found


def parse(
    text: str,
    countries: CountryIndex,
    currencies: Collection[str],
    kind: Kind | None = None,
    in_eur: InEur | None = None,
) -> Query:
    """`kind` is fixed by a command; free text (`kind=None`) infers it from what was typed.

    `in_eur` converts the salary for the sanity bounds, so "80k JPY" is judged as ~€450.
    """
    if not text.strip():
        raise ParseError("empty")
    found = _scan(text, countries, currencies)

    if not found.countries:
        raise ParseError("no_country")
    if found.salary is None:
        raise ParseError("no_salary", example=f"{found.countries[0].country} 80000")

    # Bare integers after the salary: people, then months (`/plan Germany 80000 5 24`).
    for number in found.bare:
        if found.people is None:
            found.people = number
        elif found.months is None:
            found.months = number
        else:
            raise ParseError("unexpected", word=str(number))

    if kind is None:
        if len(found.countries) >= 2:
            kind = "compare"
        elif found.people is not None or found.months is not None:
            kind = "plan"
        else:
            kind = "cost"

    if kind == "cost" and (found.people is not None or found.months is not None):
        kind = "plan"  # "/cost Germany 80k 5 people" asks a planning question
    return build_query(
        kind,
        tuple(found.countries),
        found.salary * 12 if found.monthly else found.salary,
        currency=found.currency,
        people=found.people if found.people is not None else 1,
        months=found.months if found.months is not None else DEFAULT_MONTHS,
        salary_was_monthly=found.monthly,
        in_eur=in_eur,
    )


def build_query(
    kind: Kind,
    countries: tuple[Country, ...],
    salary: Decimal,
    *,
    currency: str | None = None,
    people: int = 1,
    months: int = DEFAULT_MONTHS,
    salary_was_monthly: bool = False,
    in_eur: InEur | None = None,
) -> Query:
    """The checks every query passes, whether it was typed or came back from a button."""
    expected = 2 if kind == "compare" else 1
    if len(countries) < expected:
        raise ParseError("need_two_countries")
    if len(countries) > expected:
        raise ParseError("too_many_countries")
    if kind == "compare" and countries[0].code == countries[1].code:
        raise ParseError("same_country")
    comparable = in_eur(salary, currency or countries[0].currency) if in_eur else salary
    if comparable < MIN_SALARY:
        raise ParseError("salary_too_low", minimum=f"{MIN_SALARY:,} EUR")
    if comparable > MAX_SALARY:
        raise ParseError("salary_too_high", maximum=f"{MAX_SALARY:,} EUR")
    if not 1 <= people <= MAX_PEOPLE:
        raise ParseError("people_range", maximum=str(MAX_PEOPLE))
    if not 1 <= months <= MAX_MONTHS:
        raise ParseError("months_range", maximum=str(MAX_MONTHS))
    return Query(kind, countries, salary, currency, people, months, salary_was_monthly)


def find_country(text: str, countries: CountryIndex) -> Country:
    """Exactly one country and nothing else, for `/sources`."""
    tokens = _tokens(text)
    if not tokens:
        raise ParseError("no_country")
    hit = countries.match(tokens, 0)
    if hit is None or hit[1] != len(tokens):
        word = " ".join(tokens)
        raise ParseError("unknown_word", word=word, suggestion=countries.suggest(word) or "")
    return hit[0]
