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

Kind = Literal["cost", "compare", "plan", "team"]
# (amount, currency) -> amount in EUR; the parser knows nothing about exchange rates itself.
InEur = Callable[[Decimal, str], Decimal]

MIN_SALARY = Decimal(1_000)
MAX_SALARY = Decimal(10_000_000)
MAX_PEOPLE = 10_000
MAX_MONTHS = 120
DEFAULT_MONTHS = 12
# A bare number this big after a country, with no other amount, is a salary typed too small.
SALARY_NOT_COUNT = 100

_SYMBOLS = {"€": "EUR", "$": "USD", "£": "GBP", "zł": "PLN"}
# The vocabulary is English plus the four languages of the countries the bot covers: German,
# Spanish, Polish and Bulgarian. Words are matched lower-cased and whole.
_CURRENCY_WORDS = {
    **dict.fromkeys(("euro", "euros", "eur", "евро"), "EUR"),
    **dict.fromkeys(
        ("usd", "dollar", "dollars", "dólar", "dólares", "dolar", "dolary", "dolarów", "долар", "долара"), "USD"
    ),
    **dict.fromkeys(
        ("gbp", "pound", "pounds", "pfund", "libra", "libras", "funt", "funty", "funtów", "паунд", "паунда"), "GBP"
    ),
    **dict.fromkeys(("pln", "zloty", "zł", "złoty", "złote", "złotych", "злоти"), "PLN"),
    # Not an ECB currency any more (Bulgaria uses the euro since 2026), but people still type it.
    **dict.fromkeys(("bgn", "лв", "лв.", "лева", "leva", "lewa"), "BGN"),
}  # fmt: skip
_PEOPLE_WORDS = {
    "people", "person", "persons", "ppl", "employee", "employees", "hire", "hires", "heads", "head",
    "personen", "leute", "mitarbeiter", "mitarbeitende",
    "persona", "personas", "empleado", "empleados", "empleada", "empleadas", "trabajadores",
    "osoba", "osoby", "osób", "osob", "pracownik", "pracownicy", "pracowników", "ludzi",
    "служител", "служители", "души", "човек", "човека", "хора",
}  # fmt: skip
_MONTH_WORDS = {
    "month", "months", "mo", "mos", "monat", "monate", "monaten", "mon", "mon.", "mes", "meses",
    "miesiąc", "miesiące", "miesięcy", "miesiącach", "mies", "mies.", "месец", "месеца", "месеци", "мес", "мес.",
}  # fmt: skip
_YEAR_WORDS = {
    "year", "years", "yr", "yrs", "jahr", "jahre", "jahren", "año", "años", "ano", "anos",
    "rok", "lata", "lat", "година", "години", "год", "год.",
}  # fmt: skip
# Marks the salary as monthly ("5000 per month", "5k/mo"); the horizon uses _MONTH_WORDS instead.
_MONTHLY_SALARY = {"monthly", "/mo", "/month", "monatlich", "mensual", "mensuales", "miesięcznie", "месечно"}
_PER_WORDS = {"per", "a", "pro", "al", "por", "na", "на"}
_FILLER = {
    "vs", "vs.", "versus", "and", "or", "with", "for", "in", "of", "gross", "salary", "annual", "yearly",
    "pa", "p.a.", "/yr", "/year", "brutto", "to", "compare", "plan", "cost", "people:", "x",
    "und", "oder", "mit", "für", "gegen", "im", "jährlich", "gehalt",
    "y", "o", "con", "para", "contra", "bruto", "brutos", "salario", "anual", "en", "al",
    "i", "lub", "z", "dla", "przez", "pensja", "rocznie", "w",
    "и", "или", "с", "за", "срещу", "бруто", "заплата", "годишно", "в",
}  # fmt: skip

_AMOUNT = re.compile(
    r"^(?P<pre>[€$£])?(?P<num>\d+(?:[.,]\d+)*)(?P<mult>k|tys|tsd|хил|mln|mio|млн|mil|m)?(?P<post>[€$£]|zł)?$"
)
_TIMES = re.compile(r"^[x×](?P<n>\d+)$")
_ATTACHED_UNIT = re.compile(r"^(?P<n>\d+)(?P<unit>[^\d.,]+)$")
_MULTIPLIERS = {
    "k": 1_000,
    "tys": 1_000,
    "tys.": 1_000,
    "tsd": 1_000,
    "tsd.": 1_000,
    "mil": 1_000,
    "хил": 1_000,
    "хил.": 1_000,
    "m": 1_000_000,
    "mln": 1_000_000,
    "mio": 1_000_000,
    "mio.": 1_000_000,
    "млн": 1_000_000,
    "млн.": 1_000_000,
}
# Words after a number that make it an amount rather than a head count: "80 tys.", "900 /mo".
_AMOUNT_WORDS = {*_MULTIPLIERS, *_MONTHLY_SALARY, *_PER_WORDS}


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


@dataclass(frozen=True, slots=True)
class Member:
    """One country of a team: how many people, at what annual salary, in which currency."""

    country: Country
    count: int
    salary: Decimal
    currency: str


@dataclass(frozen=True, slots=True)
class Team:
    members: tuple[Member, ...]
    months: int = DEFAULT_MONTHS

    @property
    def people(self) -> int:
        return sum(m.count for m in self.members)


@dataclass(slots=True)
class _Found:
    countries: list[Country] = field(default_factory=list)
    salary: Decimal | None = None
    currency: str | None = None
    people: int | None = None
    months: int | None = None
    bare: list[int] = field(default_factory=list)
    monthly: bool = False
    # A small number right after a country is its head count: "Germany 2 Spain 1".
    counts: list[int | None] = field(default_factory=list)

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
    raw = text.lower()  # str.split() below also splits on no-break spaces ("80\u202f000")
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
    salary_at: int | None = None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""

        hit = index.match(tokens, i)
        if hit is not None:
            found.countries.append(hit[0])
            i += hit[1]
            count = tokens[i] if i < len(tokens) else ""
            after = tokens[i + 1] if i + 1 < len(tokens) else ""
            # Not a count when the next word makes it an amount: "80 tys.", "900 /mo", "500 EUR".
            amount_follows = after in _AMOUNT_WORDS or _currency(after, currencies) is not None
            if count.isdecimal() and 1 <= int(count) < MIN_SALARY and not amount_follows:
                found.counts.append(int(count))  # a following "people" is skipped as filler
                i += 1
            else:
                found.counts.append(None)
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
        elif token.isdecimal() and found.salary is not None and nxt in _PEOPLE_WORDS:
            found.set_people(int(token), f"{token} {nxt}")
            i += 1
        elif token.isdecimal() and found.salary is not None and nxt in _MONTH_WORDS | _YEAR_WORDS:
            found.set_months(int(token) * (12 if nxt in _YEAR_WORDS else 1), f"{token} {nxt}")
            i += 1
        elif token in _MONTHLY_SALARY:
            found.monthly = True
        elif token in _PER_WORDS and nxt in _MONTH_WORDS:
            found.monthly = True  # "per month", "на месец"
            i += 1
        elif token in _PER_WORDS and nxt in _YEAR_WORDS:
            i += 1  # "per year": the default, nothing to do
        elif token in _MULTIPLIERS and found.salary is not None and salary_at == i - 1:
            found.salary *= _MULTIPLIERS[token]  # "80 tys.", "1,2 Mio."
        elif (code := _currency(token, currencies)) is not None:
            found.currency = code
        elif (amount := _amount(token, currencies)) is not None:
            value, currency = amount
            if found.salary is None:
                found.salary = value
                found.currency = currency or found.currency
                salary_at = i
            elif token.isdecimal():
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
) -> Query | Team:
    """`kind` is fixed by a command; free text (`kind=None`) infers it from what was typed.

    `in_eur` converts the salary for the sanity bounds, so "80k JPY" is judged as ~€450.
    """
    if not text.strip():
        raise ParseError("empty")
    if kind == "team" or (kind is None and _looks_like_team(text, countries, currencies)):
        return parse_team(text, countries, currencies, in_eur)  # "Germany 2 × 80k, Spain 1 × 50k"
    found = _scan(text, countries, currencies)

    if not found.countries:
        raise ParseError("no_country")
    counts = [(i, c) for i, c in enumerate(found.counts) if c is not None]
    if found.salary is None and counts and counts[-1][1] >= SALARY_NOT_COUNT:
        # "Testland 500": the only number was read as a head count, but it is a (too small)
        # salary. "Germany 2" stays a head count, and the error asks for the salary.
        last, value = counts[-1]
        found.salary, found.counts[last] = Decimal(value), None
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

    counted = any(c is not None for c in found.counts)
    single = found.counts[0] if len(found.counts) == 1 else None
    if single is not None:
        found.set_people(single, str(single))  # "Germany 2 80k" is "Germany 80k 2 people"
    elif counted:
        # Head counts with /compare (or /cost, /plan): a team question asked of the wrong command.
        raise ParseError("unexpected", word=str(next(c for c in found.counts if c is not None)))
    if kind is None:
        kind = "compare" if len(found.countries) >= 2 else "cost"
    if kind == "cost" and (found.people is not None or found.months is not None):
        kind = "plan"  # "Germany 80k 5 people", or "/cost Germany 80k 5 people", asks a planning question
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
    _check_salary(salary, currency or countries[0].currency, in_eur)
    if not 1 <= people <= MAX_PEOPLE:
        raise ParseError("people_range", maximum=str(MAX_PEOPLE))
    if not 1 <= months <= MAX_MONTHS:
        raise ParseError("months_range", maximum=str(MAX_MONTHS))
    return Query(kind, countries, salary, currency, people, months, salary_was_monthly)


def _check_salary(salary: Decimal, currency: str, in_eur: InEur | None) -> None:
    comparable = in_eur(salary, currency) if in_eur else salary
    if comparable < MIN_SALARY:
        raise ParseError("salary_too_low", minimum=f"{MIN_SALARY:,} EUR")
    if comparable > MAX_SALARY:
        raise ParseError("salary_too_high", maximum=f"{MAX_SALARY:,} EUR")


# "2×80k", "2 x 80k", "2 @ 80k": the head count and the salary of one country.
_BY = re.compile(r"(?<=\d)\s*[×x*@]\s*(?=[€$£]?\d)")
# "Spain 1 — 70k", "Spain, 70k": a salary set off from the last country is everybody's.
# Marked with a token of its own before the punctuation is lost in tokenizing.
_APART = re.compile(r"(?<=\w)(?:\s*[,;:]\s+|\s+-\s*|\s*[—–]\s*)(?=[€$£]?\d)")
_APART_MARK = "\ue000"  # a private-use character: nothing a user types


def parse_team(text: str, countries: CountryIndex, currencies: Collection[str], in_eur: InEur | None = None) -> Team:
    """A team across countries, one segment per country:

        Germany 2 × 80k, UK 1 × £60k, Spain 1 × 50k        (each its own salary and currency)
        Germany 2, Spain 1, Poland 1 — 70k                  (one salary for all: in EUR)

        70k: Germany 2, Spain 1                             (the shared salary may lead)

    A salary glued to a head count (`Poland 1 × 200k`, `UK 2 £60k`) is that country's alone,
    even on the last country: the others then need one too.

    A segment runs from a country to the next one; inside it, a leading number is the head count
    and an amount is the salary, in the country's own currency unless one is given. A horizon
    (`24 months`) after a salary, usually at the end, applies to the whole team.
    """
    tokens, starts = _segments(text, countries)
    if len(starts) < 2:
        raise ParseError("team_needs_two")
    if len({country.code for _, _, country in starts}) != len(starts):
        raise ParseError("same_country")
    lead = _scan(" ".join(tokens[: starts[0][0]]), countries, currencies) if starts[0][0] else _Found()
    if lead.bare or lead.people is not None:
        raise ParseError("unexpected", word=tokens[0])  # head counts belong after their country
    months: int | None = lead.months

    parts: list[tuple[Country, int, _Found]] = []
    for n, (_, end, country) in enumerate(starts):
        segment = tokens[end : starts[n + 1][0] if n + 1 < len(starts) else len(tokens)]
        count = _leading_count(segment, currencies)
        if count is not None:
            segment = segment[1:]
        apart = bool(segment) and segment[0] == _APART_MARK
        segment = [token for token in segment if token != _APART_MARK]
        found = _scan(" ".join(segment), countries, currencies) if segment else _Found()
        if found.bare:
            raise ParseError("unexpected", word=str(found.bare[0]))
        if found.people is not None:
            if count is not None:
                raise ParseError("twice", word=f"{count} … {found.people}")
            count = found.people
        if found.months is not None:
            if months is not None and months != found.months:
                raise ParseError("twice", word=str(found.months))
            months = found.months
        parts.append((country, 1 if count is None else count, found))

    salaried = [found for _, _, found in parts if found.salary is not None]
    if lead.salary is not None:
        if salaried:
            raise ParseError("unexpected", word=tokens[0])  # "70k Germany 2 × 80k": whose salary?
        salaried = [lead]
    if not salaried:
        raise ParseError("no_salary", example="Germany 2 × 80k, Spain 1 × 50k")
    # One salary, up front or set off after the last country (`apart` is still the last
    # segment's), is everybody's.
    shared = len(salaried) == 1 and (salaried[0] is lead or (salaried[0] is parts[-1][2] and apart))
    members = []
    for country, count, found in parts:
        source = salaried[0] if shared else found
        if source.salary is None:
            raise ParseError("team_salary", country=country.code)  # named in the reader's language
        # One salary for everybody is in euros unless it says otherwise; a salary of its own is
        # in the country's currency, as in /plan.
        currency = source.currency or ("EUR" if shared else country.currency)
        salary = source.salary * 12 if source.monthly else source.salary
        _check_salary(salary, currency, in_eur)
        members.append(Member(country, count, salary, currency))
    team = Team(tuple(members), months if months is not None else DEFAULT_MONTHS)
    return check_team(team)


def _segments(text: str, countries: CountryIndex) -> tuple[list[str], list[tuple[int, int, Country]]]:
    """Tokens, and where each country starts and ends among them."""
    tokens = _tokens(_APART.sub(f" {_APART_MARK} ", _BY.sub(" ", text)))
    starts: list[tuple[int, int, Country]] = []
    i = 0
    while i < len(tokens):
        hit = countries.match(tokens, i)
        if hit is None:
            i += 1
            continue
        starts.append((i, i + hit[1], hit[0]))
        i += hit[1]
    return tokens, starts


def _leading_count(segment: list[str], currencies: Collection[str]) -> int | None:
    """A head count at the start of a segment: a small number not followed by an amount word.

    Zero is a head count too, so that "Germany 0 × 80k" is told the range rather than puzzled over.
    """
    if not segment or not segment[0].isdecimal() or int(segment[0]) >= MIN_SALARY:
        return None
    after = segment[1] if len(segment) > 1 else ""
    if after in _AMOUNT_WORDS or _currency(after, currencies) is not None:
        return None
    return int(segment[0])


def _looks_like_team(text: str, countries: CountryIndex, currencies: Collection[str]) -> bool:
    """Two or more countries, and either a head count right after one of them or a salary after
    two of them ("Germany 80k, Spain 50k"): a comparison has one salary for both."""
    tokens, starts = _segments(text, countries)
    if len(starts) < 2:
        return False
    bounds = [*(start for start, _, _ in starts[1:]), len(tokens)]
    segments = [tokens[end:stop] for (_, end, _), stop in zip(starts, bounds, strict=True)]
    if any(_leading_count(segment, currencies) is not None for segment in segments):
        return True
    return sum(any(_amount(token, currencies) for token in segment) for segment in segments) >= 2


def check_team(team: Team) -> Team:
    """The bounds a team must meet, typed or rebuilt from a button."""
    if len(team.members) < 2:
        raise ParseError("team_needs_two")
    if min(m.count for m in team.members) < 1 or team.people > MAX_PEOPLE:
        raise ParseError("people_range", maximum=str(MAX_PEOPLE))
    if not 1 <= team.months <= MAX_MONTHS:
        raise ParseError("months_range", maximum=str(MAX_MONTHS))
    return team


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
