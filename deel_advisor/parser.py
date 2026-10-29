"""Turns `Germany 2 × 80k, UK 1 × £60k` into a `Team`, without an LLM.

One tokenizer serves `/team` and free text alike. Every token is classified — country, amount,
currency, people, months, filler — and anything left over is an error with a name and the
offending word, so the reply can say what was not understood rather than "invalid input".
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from deel_advisor.models import Country

# (amount, currency) -> amount in EUR; the parser knows nothing about exchange rates itself.
InEur = Callable[[Decimal, str], Decimal]

MIN_SALARY = Decimal(1_000)
MAX_SALARY = Decimal(10_000_000)
MAX_PEOPLE = 10_000
MAX_MONTHS = 120
DEFAULT_MONTHS = 12
# A number this big alone after a country is a salary typed too small, not a head count.
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
    "pa", "p.a.", "/yr", "/year", "brutto", "to", "people:", "x", "de", "es",
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
    """Alias lookup. Multi-word names ("united kingdom") are matched longest-first.

    A country code that is also an everyday word is not an alias: "de" is Spanish for "of"
    ("2 personas de 80k") and "es" for "is", so those two are filler, and Germany is "DEU".
    """

    def __init__(self, countries: Iterable[Country]) -> None:
        self.by_alias: dict[tuple[str, ...], Country] = {}
        for country in countries:
            for alias in (*country.aliases, country.country.lower(), country.code.lower()):
                if alias not in _FILLER:
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
    return [w for w in words if w]


# A three-digit group of a number typed with spaces, "000€" included.
_GROUP = re.compile(r"\d{3}(?:[€$£]|zł)?")


def _glue(tokens: list[str]) -> list[str]:
    """'80 000' typed with a space: three-digit groups back onto the number before them, but
    never a group that counts something ("80 000 200 people")."""
    counted = _PEOPLE_WORDS | _MONTH_WORDS | _YEAR_WORDS
    merged: list[str] = []
    for i, token in enumerate(tokens):
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if (
            merged
            and _GROUP.fullmatch(token)
            and nxt not in counted
            and re.fullmatch(r"[€$£]?\d{1,3}(\d{3})*", merged[-1])
        ):
            merged[-1] += token
            continue
        merged.append(token)
    return merged


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


def _scan(words: list[str], index: CountryIndex, currencies: Collection[str]) -> _Found:
    """Salary, currency, people and months from the words of one country's segment (or of what
    comes before the first country); `index` only suggests a country for an unknown word."""
    tokens = _glue([word for word in words if word not in _MARKS])
    found = _Found()
    salary_at: int | None = None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""

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


def _check_salary(salary: Decimal, currency: str, in_eur: InEur | None) -> None:
    comparable = in_eur(salary, currency) if in_eur else salary
    if comparable < MIN_SALARY:
        raise ParseError("salary_too_low", minimum=f"{MIN_SALARY:,} EUR")
    if comparable > MAX_SALARY:
        raise ParseError("salary_too_high", maximum=f"{MAX_SALARY:,} EUR")


# "2×80k", "2 x 80k", "2 @ 80k": the head count and the salary of one country.
# A plain "x" only between digits or with spaces round it, so "80k x3" stays three people.
# Cyrillic "х" too: Bulgarian keyboards type it for "times".
_BY = re.compile(r"(?<=\d)(?:\s*[×*@]\s*|[xх]|\s+[xх]\s+)(?=[€$£]?\d)")
_BY_MARK = "\ue001"
# "Spain 1 — 70k", "Spain, 70k": a salary set off from the last country is everybody's.
# Marked with a token of its own before the punctuation is lost in tokenizing.
# A hyphen only with spaces round it: "-80k" is a negative salary, an error of its own.
_APART = re.compile(r"(?<=\w)(?:\s*[,;:]\s+|\s+-\s+|\s*[—–]\s*)(?=[€$£]?\d)")
_APART_MARK = "\ue000"  # private-use characters: nothing a user types
_MARKS = {_APART_MARK, _BY_MARK}


def parse(text: str, countries: CountryIndex, currencies: Collection[str], in_eur: InEur | None = None) -> Team:
    """A team in one country or across several, one segment per country:

        Germany 2 × 80k                                     (one country: also a team)
        Germany 2 × 80k, UK 1 × £60k, Spain 1 × 50k        (each its own salary and currency)
        Germany 2, Spain 1, Poland 1 — 70k                  (one salary for all: in EUR)

        70k: Germany 2, Spain 1                             (the shared salary may lead)

    A salary glued to a head count (`Poland 1 × 200k`, `UK 2 £60k`) is that country's alone,
    even on the last country: the others then need one too.

    A segment runs from a country to the next one; inside it, a leading number is the head count
    and an amount is the salary, in the country's own currency unless one is given. A horizon
    (`24 months`) after a salary, usually at the end, applies to the whole team. `in_eur`
    converts each salary for the sanity bounds, so "80k JPY" is judged as ~€450.
    """
    if not text.strip():
        raise ParseError("empty")
    tokens, starts = _segments(text, countries)
    if not starts:
        try:
            _scan(tokens, countries, currencies)
        except ParseError as error:
            if error.code == "unknown_word":
                raise  # a typo gets its "did you mean"
        raise ParseError("no_country")
    if len({country.code for _, _, country in starts}) != len(starts):
        raise ParseError("same_country")
    lead = _scan(tokens[: starts[0][0]], countries, currencies)
    if lead.bare or lead.people is not None:
        raise ParseError("unexpected", word=tokens[0])  # head counts belong after their country
    months: int | None = lead.months

    parts: list[tuple[Country, int, _Found]] = []
    for n, (_, end, country) in enumerate(starts):
        segment = tokens[end : starts[n + 1][0] if n + 1 < len(starts) else len(tokens)]
        # "Spain — 70k": a salary set off after the country is a shared one; "Germany: 2 × 80k" is
        # just a colon before the country's own head count.
        apart = bool(segment) and segment[0] == _APART_MARK
        if apart:
            segment = segment[1:]
        count = _leading_count(segment, currencies, alone=len(starts) == 1)
        rest = segment[1:] if count is not None else segment
        if count is not None:
            apart = bool(rest) and rest[0] == _APART_MARK
        found = _scan(rest, countries, currencies)
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
        raise ParseError("no_salary", example=f"{parts[0][0].country} 2 × 80k")
    # One salary, up front or set off after the last country (`apart` is still the last
    # segment's), is everybody's. With a single country it is simply that country's.
    alone = len(parts) == 1
    shared = not alone and len(salaried) == 1 and (salaried[0] is lead or (salaried[0] is parts[-1][2] and apart))
    members = []
    for country, count, found in parts:
        source = salaried[0] if shared or alone else found
        if source.salary is None:
            raise ParseError("team_salary", country=country.code)  # named in the reader's language
        # One salary for everybody is in euros unless it says otherwise; a salary of its own is
        # in the country's currency.
        currency = source.currency or ("EUR" if shared else country.currency)
        salary = source.salary * 12 if source.monthly else source.salary
        _check_salary(salary, currency, in_eur)
        members.append(Member(country, count, salary, currency))
    team = Team(tuple(members), months if months is not None else DEFAULT_MONTHS)
    return check_team(team)


def _segments(text: str, countries: CountryIndex) -> tuple[list[str], list[tuple[int, int, Country]]]:
    """Tokens, and where each country starts and ends among them."""
    tokens = _tokens(_APART.sub(f" {_APART_MARK} ", _BY.sub(f" {_BY_MARK} ", text)))
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


def _leading_count(segment: list[str], currencies: Collection[str], *, alone: bool) -> int | None:
    """A head count at the start of a segment: a small number not followed by an amount word.

    Zero is a head count too, so that "Germany 0 × 80k" is told the range rather than puzzled over.
    For a country on its own (`alone`), a number of 100 or more with nothing after it is a salary
    typed too small ("Germany 500"); in a team it is that country's head count.
    """
    if not segment or not segment[0].isdecimal():
        return None
    count, rest = int(segment[0]), segment[1:]
    if rest and rest[0] == _BY_MARK:
        return count  # "2 × 150 000", "1500 × 60k": the × says it, however big (check_team bounds it)
    if count >= MIN_SALARY:
        return None
    if not rest:
        return None if alone and count >= SALARY_NOT_COUNT else count
    if rest[0] in _AMOUNT_WORDS or _currency(rest[0], currencies) is not None:
        return None  # "80 tys.", "900 /mo", "500 EUR"
    # "150 000" is one amount, and so is "80 000 200 people"; in "2 150 000" the 2 is a head count
    # (and "1 200 000" is one person at 200,000: with a head count after every country, that is
    # the likelier reading).
    counted = _PEOPLE_WORDS | _MONTH_WORDS | _YEAR_WORDS
    second_group = len(rest) > 1 and _GROUP.fullmatch(rest[1]) and (len(rest) < 3 or rest[2] not in counted)
    if _GROUP.fullmatch(rest[0]) and not second_group:
        return None
    return count


def check_team(team: Team) -> Team:
    """The bounds a team must meet, typed or rebuilt from a button."""
    if not team.members:
        raise ParseError("no_country")
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
