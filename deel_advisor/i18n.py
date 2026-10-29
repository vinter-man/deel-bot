"""The bot's copy in the languages of the countries it covers: English, German, Spanish, Polish
and Bulgarian.

Plain dictionaries rather than gettext: five languages and ~90 strings do not need a build
step, and a test makes sure every key exists in every language with the same placeholders.
"""

from __future__ import annotations

from typing import Final, Literal

Lang = Literal["en", "de", "es", "pl", "bg"]
LANGS: Final[tuple[Lang, ...]] = ("en", "de", "es", "pl", "bg")
DEFAULT: Final[Lang] = "en"
LANG_NAMES: Final[dict[Lang, str]] = {
    "en": "🇬🇧 English",
    "de": "🇩🇪 Deutsch",
    "es": "🇪🇸 Español",
    "pl": "🇵🇱 Polski",
    "bg": "🇧🇬 Български",
}


def pick_lang(code: str | None) -> Lang:
    """A Telegram `language_code` (`de`, `pl-PL`, …) to one of ours, else English."""
    if code:
        base = code.split("-")[0].lower()
        for lang in LANGS:
            if base == lang:
                return lang
    return DEFAULT


Category = Literal["one", "few", "many"]


def category(lang: Lang, n: int) -> Category:
    """CLDR plural category. Polish alone has "few": 2–4, except 12–14 (22 osoby, 25 osób)."""
    if n == 1:
        return "one"
    if lang == "pl" and 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "few"
    return "many"


Forms = dict[Category, str]


def _forms(one: str, few: str, many: str | None = None) -> Forms:
    return {"one": one, "few": few, "many": few if many is None else many}


# A noun after a number takes a different form depending on what the sentence does with it:
# Polish "5 osób" but "dla 1 osoby", German "12 Monate" but "nach 2 Monaten". The templates only
# put a count in one of these four slots, and each slot has its own forms.
_PEOPLE: Final[dict[Lang, Forms]] = {  # a headline count: "5 people"
    "en": _forms("person", "people"),
    "de": _forms("Person", "Personen"),
    "es": _forms("persona", "personas"),
    "pl": _forms("osoba", "osoby", "osób"),
    "bg": _forms("служител", "служители"),
}
_PEOPLE_FOR: Final[dict[Lang, Forms]] = {  # after "for", "from", "with": "dla 3 osób"
    "en": _forms("person", "people"),
    "de": _forms("Person", "Personen"),
    "es": _forms("persona", "personas"),
    "pl": _forms("osoby", "osób"),
    "bg": _forms("служител", "служители"),
}
_MONTHS: Final[dict[Lang, Forms]] = {  # a duration: "over 12 months", "przez 2 miesiące"
    "en": _forms("month", "months"),
    "de": _forms("Monat", "Monate"),
    "es": _forms("mes", "meses"),
    "pl": _forms("miesiąc", "miesiące", "miesięcy"),
    "bg": _forms("месец", "месеца"),
}
_WEEKS: Final[dict[Lang, Forms]] = {  # a duration: "7 weeks to set up", "15 tygodni"
    "en": _forms("week", "weeks"),
    "de": _forms("Woche", "Wochen"),
    "es": _forms("semana", "semanas"),
    "pl": _forms("tydzień", "tygodnie", "tygodni"),
    "bg": _forms("седмица", "седмици"),
}
_MONTHS_AFTER: Final[dict[Lang, Forms]] = {  # "after 2 months": "nach 2 Monaten", "po 2 miesiącach"
    "en": _forms("month", "months"),
    "de": _forms("Monat", "Monaten"),
    "es": _forms("mes", "meses"),
    "pl": _forms("miesiącu", "miesiącach"),
    "bg": _forms("месец", "месеца"),
}


def _count(table: dict[Lang, Forms], lang: Lang, n: int) -> str:
    return f"{n} {table[lang][category(lang, n)]}"


def people(lang: Lang, n: int) -> str:
    return _count(_PEOPLE, lang, n)


def people_for(lang: Lang, n: int) -> str:
    return _count(_PEOPLE_FOR, lang, n)


def months(lang: Lang, n: int) -> str:
    return _count(_MONTHS, lang, n)


def weeks(lang: Lang, n: int) -> str:
    return _count(_WEEKS, lang, n)


def months_after(lang: Lang, n: int) -> str:
    return _count(_MONTHS_AFTER, lang, n)


_PROMPT = "🌐 Choose your language · Sprache wählen · Elige idioma · Wybierz język · Изберете език"

MESSAGES: Final[dict[Lang, dict[str, str]]] = {
    "en": {
        "lang.prompt": _PROMPT,
        "lang.set": "Language: English. Change it any time with /lang.",
        "start": (
            "👋 <b>Hire-or-Entity Advisor</b> <i>(unofficial)</i>\n\n"
            "Tell me a country, an annual gross salary and a team size — I'll show the full "
            "employer cost, EOR versus your own entity, and when an entity starts to pay off.\n\n"
            "Try: <code>Germany 80k 5 people</code>\n\n"
            "{countries}\n/help — all commands"
        ),
        "help": (
            "<b>Commands</b>\n"
            "/cost <code>country salary [currency]</code> — employer cost with a breakdown\n"
            "/plan <code>country salary people [months]</code> — EOR vs own entity, break-even\n"
            "/compare <code>country1 country2 salary</code> — two countries side by side\n"
            "/team <code>country count … salary</code> — a team across countries: EOR vs one entity each\n"
            "/sources <code>country</code> — where every figure comes from\n"
            "/lang — change language\n\n"
            "Or just type: <code>Bulgaria 60000 EUR</code>, <code>Spain 50k 3 people 24 months</code>, "
            "<code>Germany vs Poland 70k</code>.\n"
            "Salaries are <b>annual gross</b>; for a monthly one add <code>/mo</code>.\n\n"
            "{countries}\n\n"
            "<i>Unofficial, estimates only, not legal or tax advice.</i>"
        ),
        "countries": "Countries: {list}",
        "cost.header": "{flag} <b>{country}</b> · {salary} gross a year",
        "cost.monthly_input": "{monthly} a month × 12",
        "cost.converted": "≈ {amount} at the ECB rate of {date}",
        "cost.total": "Employer cost: <b>{annual}</b> a year · {monthly} a month",
        "cost.burden": "On top of salary: +{amount} a year ({rate})",
        "cost.capped": "capped",
        "cost.footer": (
            "<i>{year} rates, in force since {since}. Payslip lines rounded to the cent, shown in whole units.</i>"
        ),
        "cost.estimate_note": "<i>~ typical rate, depends on the employer.</i>",
        "cost.cap_since": "<i>Contribution ceiling from {date}, applied to every month.</i>",
        "cost.below_min_wage": "⚠️ Below the {year} minimum wage ({minimum} a year).",
        "cost.monthly_hint": "I expect an <b>annual</b> salary; for a monthly one write <code>{example}</code>.",
        "plan.header": "{flag} <b>{country}</b> · {team} × {salary} a year · {months}",
        "plan.eor": "<b>EOR ({provider})</b>: {total}",
        "plan.eor_detail": "fee {fee} per person a month",
        "plan.eor_fx": "({price} list price, ECB rate of {date})",
        "plan.entity": "<b>Own entity</b>: {total}",
        "plan.entity_detail": "setup {setup} + closing {exit} · {fixed} a month + {per_employee} per person a month",
        "plan.entity_deel": "<b>Own entity on Deel Payroll</b>: {total}",
        "plan.entity_bridge": "{weeks} to set up, on EOR meanwhile: {amount}",
        "plan.switch": "💡 Time to move to your own entity: Deel Payroll can run its payroll for {fee} per person a month (included above).",
        "plan.same": "Salary + contributions, identical either way: {amount}",
        "plan.eor_cheaper": "💡 For {team} over {months} EOR is cheaper by ~{diff}.",
        "plan.entity_cheaper": "💡 For {team} over {months} your own entity is cheaper by ~{diff}.",
        "plan.even": "💡 For {team} over {months} both cost about the same.",
        "plan.pays_off_people": "An entity pays off from {team} (over {months}).",
        "plan.pays_off_months": "With {team} it pays off after {months}.",
        "plan.never_months": "With {team} it never pays off: the fixed costs eat the saving.",
        "plan.never_people": "At these prices an entity never pays off.",
        "plan.note": "<i>Every line has a source (/sources). Not priced, and all in the EOR's favour: your team's own time on the entity, the months a liquidation takes, and the misclassification and permanent-establishment risk an EOR carries for you.</i>",
        "team.header": "🌍 <b>Team in {countries} countries</b> · {team} × {salary} a year · {months}",
        "team.row_eor": "{flag} <b>{country}</b> × {count}: EOR {eor} · own entity {entity} ✅ EOR",
        "team.row_entity": "{flag} <b>{country}</b> × {count}: EOR {eor} · own entity {entity} ✅ entity",
        "team.total": "<b>Total</b>: EOR (Deel) {eor} · {entities} own entities {entity}",
        "team.eor_saves": "💡 Over {months} EOR saves ~{diff} — and no company to open, run and close in {entities} countries.",
        "team.entities_win": "💡 Over {months} own entities would be ~{diff} cheaper — Deel Payroll can run their payroll.",
        "team.mix": "💡 Cheapest mix: EOR in {eor}, own entity on Deel Payroll in {entity} — {total}.",
        "team.breakeven": "An own entity pays off from: {list} people (over {months}).",
        "team.same": "Salary + contributions, identical either way: {amount}",
        "compare.header": "<b>{a} vs {b}</b> · {salary} gross a year",
        "compare.row": "{flag} <b>{country}</b>: {total} a year · +{rate}",
        "compare.row_local": "in {currency}: {total}",
        "compare.row_eor": "EOR {fee} a month · entity from {team} (12 mo)",
        "compare.row_never": "EOR {fee} a month · entity never pays off",
        "compare.cheaper": "💡 Cheaper: {country}, by ~{diff} a year ({rate} less).",
        "compare.fx": "<i>Converted at ECB rates of {date}.</i>",
        "sources.header": "{flag} <b>{country}: sources</b>",
        "sources.rates": "<b>Rates {year}</b>, in force since {since} · checked {checked}",
        "sources.entity": "<b>Own entity</b> (estimates unless marked official)",
        "sources.official": "official",
        "sources.per_person": "/mo per person",
        "sources.replaced": "in the totals: Deel Payroll",
        "sources.notes": "<b>Notes</b>",
        "sources.capital": "Share capital {amount}: stays the company's, not a cost",
        "sources.eor": '<b>EOR price</b>: {provider} from {fee} a month · <a href="{url}">pricing</a>, checked {checked}',
        "sources.setup_time": "Setup until the first payroll: {weeks}",
        "sources.exit": "Closing:",
        "sources.payroll": '<b>Deel Payroll</b> for your own entity: from {fee} per person a month · <a href="{url}">pricing</a>, checked {checked}',
        "sources.guide": '<b>Deel guide</b> · <a href="{url}">page</a>, checked {checked}',
        "sources.guide_ok": "✅ {label}: {value}",
        "sources.guide_bad": "📝 {label}: Deel {deel}, official {official}",
        "sources.fx": "FX: ECB reference rates of {date}.",
        "warn.year": "⚠️ These are {year} rates; {current} figures may differ.",
        "warn.unchecked": "⚠️ Official figures last checked {date}.",
        "warn.mismatch": '📝 Deel\'s guide still shows {label}: {deel}; the official figure since {since} is {official} (<a href="{url}">source</a>).',
        "warn.fx_old": "⚠️ Exchange rates are from {date}.",
        "btn.compare": "🔁 Compare with another country",
        "btn.plan": "👥 Plan for N people",
        "btn.sources": "📚 Sources",
        "btn.months": "{n} mo",
        "pick.country": "Compare {country} with:",
        "pick.people": "How many people?",
        "err.empty": "Send a country and an annual salary, e.g. <code>Germany 80k</code>.",
        "err.no_country": "Which country? {countries}",
        "err.no_salary": "I need an annual gross salary too, e.g. <code>{example}</code>.",
        "err.unknown_word": "I don't know “{word}”.",
        "err.unknown_word_suggest": "I don't know “{word}”. Did you mean <b>{suggestion}</b>?",
        "err.unknown_currency": "No ECB rate for {currency}. Use EUR, USD, GBP, PLN or another ECB currency.",
        "err.salary_too_low": "That salary looks too small for a year (minimum {minimum}). Monthly? Add <code>/mo</code>.",
        "err.salary_too_high": "That salary is above {maximum} — probably a typo.",
        "err.people_range": "Team size must be between 1 and {maximum}.",
        "err.months_range": "The horizon must be between 1 and {maximum} months.",
        "err.need_two_countries": "Name two countries: <code>/compare Germany Poland 60000</code>.",
        "err.too_many_countries": "One country at a time here; to compare two use /compare.",
        "err.same_country": "Those are the same country — pick two different ones.",
        "err.unexpected": "I didn't understand “{word}”.",
        "err.twice": "“{word}” says the same thing twice — keep one.",
        "err.team_needs_two": "A team spans at least two countries: <code>/team Germany 2 Spain 1 70k</code>.",
        "err.stale_button": "That button belongs to an old message. Send the query again.",
        "err.internal": "Something went wrong on my side. Please try again in a minute.",
        "usage.cost": "Usage: <code>/cost Bulgaria 60000 EUR</code>",
        "usage.plan": "Usage: <code>/plan Germany 80000 5 12</code> (country, salary, people, months)",
        "usage.compare": "Usage: <code>/compare Germany Poland 60000</code>",
        "usage.sources": "Usage: <code>/sources Spain</code>",
        "usage.team": "Usage: <code>/team Germany 2 UK 1 Spain 1 70k</code> (a head count after each country)",
        "usage.free": "Try <code>Germany 80k</code> or /help.",
        "stats": "<b>Since start</b> ({since})\n{lines}",
    },
    "de": {
        "lang.prompt": _PROMPT,
        "lang.set": "Sprache: Deutsch. Ändern kannst du sie jederzeit mit /lang.",
        "start": (
            "👋 <b>Hire-or-Entity Advisor</b> <i>(inoffiziell)</i>\n\n"
            "Nenne mir ein Land, ein Bruttojahresgehalt und eine Teamgröße – ich zeige die vollen "
            "Arbeitgeberkosten, EOR im Vergleich zur eigenen Gesellschaft und ab wann sich die "
            "Gesellschaft rechnet.\n\n"
            "Probier: <code>Deutschland 80k 5 Personen</code>\n\n"
            "{countries}\n/help – alle Befehle"
        ),
        "help": (
            "<b>Befehle</b>\n"
            "/cost <code>Land Gehalt [Währung]</code> – Arbeitgeberkosten mit Aufschlüsselung\n"
            "/plan <code>Land Gehalt Personen [Monate]</code> – EOR oder eigene Gesellschaft, Break-even\n"
            "/compare <code>Land1 Land2 Gehalt</code> – zwei Länder nebeneinander\n"
            "/team <code>Land Anzahl … Gehalt</code> – ein Team über mehrere Länder: EOR oder je eine Gesellschaft\n"
            "/sources <code>Land</code> – woher jede Zahl stammt\n"
            "/lang – Sprache ändern\n\n"
            "Oder einfach schreiben: <code>Bulgarien 60000 EUR</code>, <code>Spanien 50k 3 Personen 24 Monate</code>, "
            "<code>Deutschland vs Polen 70k</code>.\n"
            "Gehälter sind <b>Jahresbrutto</b>; für ein Monatsgehalt <code>/mo</code> anhängen.\n\n"
            "{countries}\n\n"
            "<i>Inoffiziell, nur Schätzungen, keine Rechts- oder Steuerberatung.</i>"
        ),
        "countries": "Länder: {list}",
        "cost.header": "{flag} <b>{country}</b> · {salary} brutto im Jahr",
        "cost.monthly_input": "{monthly} im Monat × 12",
        "cost.converted": "≈ {amount} zum EZB-Kurs vom {date}",
        "cost.total": "Arbeitgeberkosten: <b>{annual}</b> im Jahr · {monthly} im Monat",
        "cost.burden": "Zusätzlich zum Gehalt: +{amount} im Jahr ({rate})",
        "cost.capped": "gedeckelt",
        "cost.footer": (
            "<i>Sätze {year}, gültig seit {since}. Abrechnungszeilen auf den Cent gerundet, "
            "in ganzen Beträgen angezeigt.</i>"
        ),
        "cost.estimate_note": "<i>~ typischer Satz, hängt vom Arbeitgeber ab.</i>",
        "cost.cap_since": "<i>Beitragsbemessungsgrenze ab {date}, auf jeden Monat angewandt.</i>",
        "cost.below_min_wage": "⚠️ Unter dem Mindestlohn {year} ({minimum} im Jahr).",
        "cost.monthly_hint": "Ich erwarte ein <b>Jahresgehalt</b>; für ein Monatsgehalt schreib <code>{example}</code>.",
        "plan.header": "{flag} <b>{country}</b> · {team} × {salary} im Jahr · {months}",
        "plan.eor": "<b>EOR ({provider})</b>: {total}",
        "plan.eor_detail": "Gebühr {fee} pro Person und Monat",
        "plan.eor_fx": "(Listenpreis {price}, EZB-Kurs vom {date})",
        "plan.entity": "<b>Eigene Gesellschaft</b>: {total}",
        "plan.entity_detail": "Gründung {setup} + Schließung {exit} · {fixed} im Monat + {per_employee} pro Person und Monat",
        "plan.entity_deel": "<b>Eigene Gesellschaft mit Deel Payroll</b>: {total}",
        "plan.entity_bridge": "{weeks} bis zur Gründung, solange über EOR: {amount}",
        "plan.switch": "💡 Zeit für die eigene Gesellschaft: Deel Payroll kann ihre Lohnabrechnung für {fee} pro Person und Monat übernehmen (oben enthalten).",
        "plan.same": "Gehalt + Beiträge, in beiden Fällen gleich: {amount}",
        "plan.eor_cheaper": "💡 Für {team} über {months} ist EOR um ~{diff} günstiger.",
        "plan.entity_cheaper": "💡 Für {team} über {months} ist die eigene Gesellschaft um ~{diff} günstiger.",
        "plan.even": "💡 Für {team} über {months} kosten beide etwa gleich viel.",
        "plan.pays_off_people": "Eine Gesellschaft rechnet sich ab {team} (über {months}).",
        "plan.pays_off_months": "Mit {team} rechnet sie sich nach {months}.",
        "plan.never_months": "Mit {team} rechnet sie sich nie: Die Fixkosten fressen die Ersparnis.",
        "plan.never_people": "Zu diesen Preisen rechnet sich eine Gesellschaft nie.",
        "plan.note": "<i>Jede Zeile hat eine Quelle (/sources). Nicht eingepreist, und alles zugunsten des EOR: die Zeit deines Teams für die Gesellschaft, die Monate einer Liquidation und das Risiko von Scheinselbstständigkeit und Betriebsstätte, das ein EOR für dich trägt.</i>",
        "team.header": "🌍 <b>Team in {countries} Ländern</b> · {team} × {salary} im Jahr · {months}",
        "team.row_eor": "{flag} <b>{country}</b> × {count}: EOR {eor} · eigene Gesellschaft {entity} ✅ EOR",
        "team.row_entity": "{flag} <b>{country}</b> × {count}: EOR {eor} · eigene Gesellschaft {entity} ✅ Gesellschaft",
        "team.total": "<b>Gesamt</b>: EOR (Deel) {eor} · {entities} eigene Gesellschaften {entity}",
        "team.eor_saves": "💡 Über {months} spart EOR ~{diff} – und keine Gesellschaft zu gründen, zu führen und zu schließen in {entities} Ländern.",
        "team.entities_win": "💡 Über {months} wären eigene Gesellschaften ~{diff} günstiger – Deel Payroll kann ihre Abrechnung übernehmen.",
        "team.mix": "💡 Günstigste Kombination: EOR in {eor}, eigene Gesellschaft mit Deel Payroll in {entity} – {total}.",
        "team.breakeven": "Eine eigene Gesellschaft rechnet sich ab: {list} Personen (über {months}).",
        "team.same": "Gehalt + Beiträge, in beiden Fällen gleich: {amount}",
        "compare.header": "<b>{a} vs. {b}</b> · {salary} brutto im Jahr",
        "compare.row": "{flag} <b>{country}</b>: {total} im Jahr · +{rate}",
        "compare.row_local": "in {currency}: {total}",
        "compare.row_eor": "EOR {fee} im Monat · Gesellschaft ab {team} (12 Mon.)",
        "compare.row_never": "EOR {fee} im Monat · Gesellschaft rechnet sich nie",
        "compare.cheaper": "💡 Günstiger: {country}, um ~{diff} im Jahr ({rate} weniger).",
        "compare.fx": "<i>Umgerechnet zu EZB-Kursen vom {date}.</i>",
        "sources.header": "{flag} <b>{country}: Quellen</b>",
        "sources.rates": "<b>Sätze {year}</b>, gültig seit {since} · geprüft am {checked}",
        "sources.entity": "<b>Eigene Gesellschaft</b> (Schätzungen, sofern nicht als amtlich markiert)",
        "sources.official": "amtlich",
        "sources.per_person": "/Mon. pro Person",
        "sources.replaced": "in den Summen: Deel Payroll",
        "sources.notes": "<b>Hinweise</b> (auf Englisch)",
        "sources.capital": "Stammkapital {amount}: bleibt in der Gesellschaft, keine Kosten",
        "sources.eor": '<b>EOR-Preis</b>: {provider} ab {fee} im Monat · <a href="{url}">Preise</a>, geprüft am {checked}',
        "sources.setup_time": "Gründung bis zur ersten Abrechnung: {weeks}",
        "sources.exit": "Schließung:",
        "sources.payroll": '<b>Deel Payroll</b> für die eigene Gesellschaft: ab {fee} pro Person und Monat · <a href="{url}">Preise</a>, geprüft am {checked}',
        "sources.guide": '<b>Deel-Leitfaden</b> · <a href="{url}">Seite</a>, geprüft am {checked}',
        "sources.guide_ok": "✅ {label}: {value}",
        "sources.guide_bad": "📝 {label}: Deel {deel}, amtlich {official}",
        "sources.fx": "Wechselkurse: EZB-Referenzkurse vom {date}.",
        "warn.year": "⚠️ Das sind Sätze für {year}; für {current} können die Zahlen abweichen.",
        "warn.unchecked": "⚠️ Amtliche Zahlen zuletzt geprüft am {date}.",
        "warn.mismatch": '📝 Im Deel-Leitfaden steht noch {label} {deel}; amtlich seit {since}: {official} (<a href="{url}">Quelle</a>).',
        "warn.fx_old": "⚠️ Wechselkurse vom {date}.",
        "btn.compare": "🔁 Mit anderem Land vergleichen",
        "btn.plan": "👥 Für N Personen rechnen",
        "btn.sources": "📚 Quellen",
        "btn.months": "{n} Mon.",
        "pick.country": "{country} vergleichen mit:",
        "pick.people": "Wie viele Personen?",
        "err.empty": "Schick ein Land und ein Jahresgehalt, z. B. <code>Deutschland 80k</code>.",
        "err.no_country": "Welches Land? {countries}",
        "err.no_salary": "Ich brauche auch ein Bruttojahresgehalt, z. B. <code>{example}</code>.",
        "err.unknown_word": "„{word}“ kenne ich nicht.",
        "err.unknown_word_suggest": "„{word}“ kenne ich nicht. Meintest du <b>{suggestion}</b>?",
        "err.unknown_currency": "Für {currency} gibt es keinen EZB-Kurs. Nimm EUR, USD, GBP, PLN oder eine andere EZB-Währung.",
        "err.salary_too_low": "Für ein Jahresgehalt zu niedrig (mindestens {minimum}). Monatlich? <code>/mo</code> anhängen.",
        "err.salary_too_high": "Das Gehalt liegt über {maximum} – wohl ein Tippfehler.",
        "err.people_range": "Die Teamgröße muss zwischen 1 und {maximum} liegen.",
        "err.months_range": "Der Zeitraum muss zwischen 1 und {maximum} Monaten liegen.",
        "err.need_two_countries": "Nenne zwei Länder: <code>/compare Germany Poland 60000</code>.",
        "err.too_many_countries": "Hier geht nur ein Land; zum Vergleichen gibt es /compare.",
        "err.same_country": "Das ist zweimal dasselbe Land – wähle zwei verschiedene.",
        "err.unexpected": "„{word}“ habe ich nicht verstanden.",
        "err.twice": "„{word}“ sagt etwas zum zweiten Mal – lass eins weg.",
        "err.team_needs_two": "Ein Team umfasst mindestens zwei Länder: <code>/team Germany 2 Spain 1 70k</code>.",
        "err.stale_button": "Diese Schaltfläche gehört zu einer alten Nachricht. Schick die Anfrage noch einmal.",
        "err.internal": "Bei mir ist etwas schiefgelaufen. Versuch es in einer Minute noch einmal.",
        "usage.cost": "Beispiel: <code>/cost Bulgaria 60000 EUR</code>",
        "usage.plan": "Beispiel: <code>/plan Germany 80000 5 12</code> (Land, Gehalt, Personen, Monate)",
        "usage.compare": "Beispiel: <code>/compare Germany Poland 60000</code>",
        "usage.sources": "Beispiel: <code>/sources Spain</code>",
        "usage.team": "Beispiel: <code>/team Germany 2 UK 1 Spain 1 70k</code> (nach jedem Land die Personenzahl)",
        "usage.free": "Probier <code>Deutschland 80k</code> oder /help.",
        "stats": "<b>Seit dem Start</b> ({since})\n{lines}",
    },
    "es": {
        "lang.prompt": _PROMPT,
        "lang.set": "Idioma: español. Cámbialo cuando quieras con /lang.",
        "start": (
            "👋 <b>Hire-or-Entity Advisor</b> <i>(no oficial)</i>\n\n"
            "Dime un país, un salario bruto anual y el tamaño del equipo: te muestro el coste total "
            "para la empresa, EOR frente a sociedad propia y desde cuándo compensa la sociedad.\n\n"
            "Prueba: <code>España 80k 5 personas</code>\n\n"
            "{countries}\n/help — todos los comandos"
        ),
        "help": (
            "<b>Comandos</b>\n"
            "/cost <code>país salario [moneda]</code> — coste para la empresa, desglosado\n"
            "/plan <code>país salario personas [meses]</code> — EOR o sociedad propia, punto de equilibrio\n"
            "/compare <code>país1 país2 salario</code> — dos países lado a lado\n"
            "/team <code>país número … salario</code> — un equipo en varios países: EOR o una sociedad en cada uno\n"
            "/sources <code>país</code> — de dónde sale cada cifra\n"
            "/lang — cambiar idioma\n\n"
            "O escribe sin más: <code>Bulgaria 60000 EUR</code>, <code>España 50k 3 personas 24 meses</code>, "
            "<code>Alemania vs Polonia 70k</code>.\n"
            "Los salarios son <b>brutos anuales</b>; para uno mensual añade <code>/mo</code>.\n\n"
            "{countries}\n\n"
            "<i>No oficial, solo estimaciones, no es asesoramiento legal ni fiscal.</i>"
        ),
        "countries": "Países: {list}",
        "cost.header": "{flag} <b>{country}</b> · {salary} brutos al año",
        "cost.monthly_input": "{monthly} al mes × 12",
        "cost.converted": "≈ {amount} al tipo del BCE del {date}",
        "cost.total": "Coste para la empresa: <b>{annual}</b> al año · {monthly} al mes",
        "cost.burden": "Además del salario: +{amount} al año ({rate})",
        "cost.capped": "con tope",
        "cost.footer": (
            "<i>Tipos de {year}, vigentes desde el {since}. Líneas de nómina redondeadas al céntimo, "
            "mostradas en unidades enteras.</i>"
        ),
        "cost.estimate_note": "<i>~ tipo habitual, depende de la empresa.</i>",
        "cost.cap_since": "<i>Base máxima desde el {date}, aplicada a todos los meses.</i>",
        "cost.below_min_wage": "⚠️ Por debajo del salario mínimo de {year} ({minimum} al año).",
        "cost.monthly_hint": "Espero un salario <b>anual</b>; para uno mensual escribe <code>{example}</code>.",
        "plan.header": "{flag} <b>{country}</b> · {team} × {salary} al año · {months}",
        "plan.eor": "<b>EOR ({provider})</b>: {total}",
        "plan.eor_detail": "cuota de {fee} por persona al mes",
        "plan.eor_fx": "(precio de lista {price}, tipo del BCE del {date})",
        "plan.entity": "<b>Sociedad propia</b>: {total}",
        "plan.entity_detail": "constitución {setup} + cierre {exit} · {fixed} al mes + {per_employee} por persona al mes",
        "plan.entity_deel": "<b>Sociedad propia con Deel Payroll</b>: {total}",
        "plan.entity_bridge": "{weeks} para constituirla, mientras tanto con EOR: {amount}",
        "plan.switch": "💡 Es momento de tu propia sociedad: Deel Payroll puede gestionar sus nóminas por {fee} por persona al mes (incluido arriba).",
        "plan.same": "Salario + cotizaciones, igual en ambos casos: {amount}",
        "plan.eor_cheaper": "💡 Para {team} durante {months}, el EOR sale ~{diff} más barato.",
        "plan.entity_cheaper": "💡 Para {team} durante {months}, la sociedad propia sale ~{diff} más barata.",
        "plan.even": "💡 Para {team} durante {months}, ambas opciones cuestan más o menos lo mismo.",
        "plan.pays_off_people": "Una sociedad compensa a partir de {team} (en {months}).",
        "plan.pays_off_months": "Con {team}, se amortiza en {months}.",
        "plan.never_months": "Con {team} no se amortiza nunca: los costes fijos se comen el ahorro.",
        "plan.never_people": "A estos precios, una sociedad no compensa nunca.",
        "plan.note": "<i>Cada línea tiene su fuente (/sources). Sin incluir, y todo a favor del EOR: el tiempo de tu equipo dedicado a la sociedad, los meses que dura una liquidación y el riesgo de falsos autónomos y de establecimiento permanente que el EOR asume por ti.</i>",
        "team.header": "🌍 <b>Equipo en {countries} países</b> · {team} × {salary} al año · {months}",
        "team.row_eor": "{flag} <b>{country}</b> × {count}: EOR {eor} · sociedad propia {entity} ✅ EOR",
        "team.row_entity": "{flag} <b>{country}</b> × {count}: EOR {eor} · sociedad propia {entity} ✅ sociedad",
        "team.total": "<b>Total</b>: EOR (Deel) {eor} · {entities} sociedades propias {entity}",
        "team.eor_saves": "💡 En {months}, el EOR ahorra ~{diff}, sin ninguna sociedad que abrir, gestionar y cerrar en {entities} países.",
        "team.entities_win": "💡 En {months}, las sociedades propias saldrían ~{diff} más baratas; Deel Payroll puede gestionar sus nóminas.",
        "team.mix": "💡 La combinación más barata: EOR en {eor}, sociedad propia con Deel Payroll en {entity}: {total}.",
        "team.breakeven": "Una sociedad propia compensa a partir de: {list} personas (en {months}).",
        "team.same": "Salario + cotizaciones, igual en ambos casos: {amount}",
        "compare.header": "<b>{a} vs. {b}</b> · {salary} brutos al año",
        "compare.row": "{flag} <b>{country}</b>: {total} al año · +{rate}",
        "compare.row_local": "en {currency}: {total}",
        "compare.row_eor": "EOR {fee} al mes · sociedad desde {team} (12 meses)",
        "compare.row_never": "EOR {fee} al mes · la sociedad no compensa nunca",
        "compare.cheaper": "💡 Más barato: {country}, ~{diff} menos al año ({rate} menos).",
        "compare.fx": "<i>Convertido a tipos del BCE del {date}.</i>",
        "sources.header": "{flag} <b>{country}: fuentes</b>",
        "sources.rates": "<b>Tipos {year}</b>, vigentes desde el {since} · revisado el {checked}",
        "sources.entity": "<b>Sociedad propia</b> (estimaciones salvo las marcadas como oficiales)",
        "sources.official": "oficial",
        "sources.per_person": "/mes por persona",
        "sources.replaced": "en los totales: Deel Payroll",
        "sources.notes": "<b>Notas</b> (en inglés)",
        "sources.capital": "Capital social {amount}: se queda en la sociedad, no es un coste",
        "sources.eor": '<b>Precio EOR</b>: {provider} desde {fee} al mes · <a href="{url}">precios</a>, revisado el {checked}',
        "sources.setup_time": "Constitución hasta la primera nómina: {weeks}",
        "sources.exit": "Cierre:",
        "sources.payroll": '<b>Deel Payroll</b> para tu propia sociedad: desde {fee} por persona al mes · <a href="{url}">precios</a>, revisado el {checked}',
        "sources.guide": '<b>Guía de Deel</b> · <a href="{url}">página</a>, revisada el {checked}',
        "sources.guide_ok": "✅ {label}: {value}",
        "sources.guide_bad": "📝 {label}: Deel {deel}, oficial {official}",
        "sources.fx": "Divisas: tipos de referencia del BCE del {date}.",
        "warn.year": "⚠️ Son tipos de {year}; las cifras de {current} pueden ser distintas.",
        "warn.unchecked": "⚠️ Cifras oficiales revisadas por última vez el {date}.",
        "warn.mismatch": '📝 La guía de Deel aún indica {label}: {deel}; la cifra oficial desde el {since} es {official} (<a href="{url}">fuente</a>).',
        "warn.fx_old": "⚠️ Los tipos de cambio son del {date}.",
        "btn.compare": "🔁 Comparar con otro país",
        "btn.plan": "👥 Calcular para N personas",
        "btn.sources": "📚 Fuentes",
        "btn.months": "{n} meses",
        "pick.country": "¿Con qué país comparar {country}?",
        "pick.people": "¿Cuántas personas?",
        "err.empty": "Envía un país y un salario anual, p. ej. <code>España 80k</code>.",
        "err.no_country": "¿Qué país? {countries}",
        "err.no_salary": "También necesito un salario bruto anual, p. ej. <code>{example}</code>.",
        "err.unknown_word": "No conozco «{word}».",
        "err.unknown_word_suggest": "No conozco «{word}». ¿Querías decir <b>{suggestion}</b>?",
        "err.unknown_currency": "No hay tipo del BCE para {currency}. Usa EUR, USD, GBP, PLN u otra moneda del BCE.",
        "err.salary_too_low": "Parece poco para un salario anual (mínimo {minimum}). ¿Es mensual? Añade <code>/mo</code>.",
        "err.salary_too_high": "El salario supera {maximum}; seguramente es una errata.",
        "err.people_range": "El tamaño del equipo debe estar entre 1 y {maximum}.",
        "err.months_range": "El horizonte debe estar entre 1 y {maximum} meses.",
        "err.need_two_countries": "Indica dos países: <code>/compare Germany Poland 60000</code>.",
        "err.too_many_countries": "Aquí va un solo país; para comparar dos usa /compare.",
        "err.same_country": "Es el mismo país dos veces; elige dos distintos.",
        "err.unexpected": "No he entendido «{word}».",
        "err.twice": "«{word}» repite algo que ya has dicho; deja solo uno.",
        "err.team_needs_two": "Un equipo abarca al menos dos países: <code>/team Germany 2 Spain 1 70k</code>.",
        "err.stale_button": "Ese botón es de un mensaje antiguo. Vuelve a enviar la consulta.",
        "err.internal": "Algo ha fallado por mi parte. Inténtalo de nuevo en un minuto.",
        "usage.cost": "Ejemplo: <code>/cost Bulgaria 60000 EUR</code>",
        "usage.plan": "Ejemplo: <code>/plan Germany 80000 5 12</code> (país, salario, personas, meses)",
        "usage.compare": "Ejemplo: <code>/compare Germany Poland 60000</code>",
        "usage.sources": "Ejemplo: <code>/sources Spain</code>",
        "usage.team": "Ejemplo: <code>/team Germany 2 UK 1 Spain 1 70k</code> (el número de personas tras cada país)",
        "usage.free": "Prueba <code>España 80k</code> o /help.",
        "stats": "<b>Desde el inicio</b> ({since})\n{lines}",
    },
    "pl": {
        "lang.prompt": _PROMPT,
        "lang.set": "Język: polski. Zmienisz go w każdej chwili przez /lang.",
        "start": (
            "👋 <b>Hire-or-Entity Advisor</b> <i>(nieoficjalny)</i>\n\n"
            "Podaj kraj, roczne wynagrodzenie brutto i wielkość zespołu — pokażę pełny koszt "
            "pracodawcy, EOR w porównaniu z własną spółką i od kiedy spółka zaczyna się opłacać.\n\n"
            "Spróbuj: <code>Polska 80k 5 osób</code>\n\n"
            "{countries}\n/help — wszystkie polecenia"
        ),
        "help": (
            "<b>Polecenia</b>\n"
            "/cost <code>kraj pensja [waluta]</code> — koszt pracodawcy z rozbiciem\n"
            "/plan <code>kraj pensja osoby [miesiące]</code> — EOR czy własna spółka, próg opłacalności\n"
            "/compare <code>kraj1 kraj2 pensja</code> — dwa kraje obok siebie\n"
            "/team <code>kraj liczba … pensja</code> — zespół w kilku krajach: EOR czy spółka w każdym\n"
            "/sources <code>kraj</code> — skąd pochodzi każda liczba\n"
            "/lang — zmiana języka\n\n"
            "Możesz też po prostu napisać: <code>Bułgaria 60000 EUR</code>, "
            "<code>Hiszpania 50k 3 osoby 24 miesiące</code>, <code>Niemcy vs Polska 70k</code>.\n"
            "Wynagrodzenie to <b>roczne brutto</b>; dla miesięcznego dodaj <code>/mo</code>.\n\n"
            "{countries}\n\n"
            "<i>Nieoficjalne, tylko szacunki, nie jest to porada prawna ani podatkowa.</i>"
        ),
        "countries": "Kraje: {list}",
        "cost.header": "{flag} <b>{country}</b> · {salary} brutto rocznie",
        "cost.monthly_input": "{monthly} miesięcznie × 12",
        "cost.converted": "≈ {amount} po kursie EBC z {date}",
        "cost.total": "Koszt pracodawcy: <b>{annual}</b> rocznie · {monthly} miesięcznie",
        "cost.burden": "Ponad wynagrodzenie: +{amount} rocznie ({rate})",
        "cost.capped": "limit",
        "cost.footer": (
            "<i>Stawki na {year}, obowiązują od {since}. Pozycje listy płac zaokrąglone do grosza, "
            "pokazane w pełnych kwotach.</i>"
        ),
        "cost.estimate_note": "<i>~ typowa stawka, zależy od pracodawcy.</i>",
        "cost.cap_since": "<i>Limit składek od {date}, zastosowany do każdego miesiąca.</i>",
        "cost.below_min_wage": "⚠️ Poniżej płacy minimalnej na {year} ({minimum} rocznie).",
        "cost.monthly_hint": "Oczekuję wynagrodzenia <b>rocznego</b>; dla miesięcznego napisz <code>{example}</code>.",
        "plan.header": "{flag} <b>{country}</b> · {team} × {salary} rocznie · {months}",
        "plan.eor": "<b>EOR ({provider})</b>: {total}",
        "plan.eor_detail": "opłata {fee} za osobę miesięcznie",
        "plan.eor_fx": "(cena katalogowa {price}, kurs EBC z {date})",
        "plan.entity": "<b>Własna spółka</b>: {total}",
        "plan.entity_detail": "założenie {setup} + likwidacja {exit} · {fixed} miesięcznie + {per_employee} za osobę miesięcznie",
        "plan.entity_deel": "<b>Własna spółka z Deel Payroll</b>: {total}",
        "plan.entity_bridge": "{weeks} na założenie, w tym czasie przez EOR: {amount}",
        "plan.switch": "💡 Czas na własną spółkę: Deel Payroll może prowadzić jej płace za {fee} za osobę miesięcznie (wliczone wyżej).",
        "plan.same": "Wynagrodzenie + składki, tak samo w obu wariantach: {amount}",
        "plan.eor_cheaper": "💡 Dla {team} przez {months} EOR jest tańszy o ~{diff}.",
        "plan.entity_cheaper": "💡 Dla {team} przez {months} własna spółka jest tańsza o ~{diff}.",
        "plan.even": "💡 Dla {team} przez {months} oba warianty kosztują mniej więcej tyle samo.",
        "plan.pays_off_people": "Spółka opłaca się od {team} (przez {months}).",
        "plan.pays_off_months": "Dla {team} zwraca się po {months}.",
        "plan.never_months": "Dla {team} nigdy się nie zwraca: koszty stałe zjadają oszczędność.",
        "plan.never_people": "Przy tych cenach spółka nigdy się nie opłaca.",
        "plan.note": "<i>Każda pozycja ma źródło (/sources). Nie wliczono, a wszystko to przemawia za EOR: czasu twojego zespołu poświęconego spółce, miesięcy trwania likwidacji oraz ryzyka błędnej kwalifikacji i zakładu podatkowego, które EOR bierze na siebie.</i>",
        "team.header": "🌍 <b>Zespół w {countries} krajach</b> · {team} × {salary} rocznie · {months}",
        "team.row_eor": "{flag} <b>{country}</b> × {count}: EOR {eor} · własna spółka {entity} ✅ EOR",
        "team.row_entity": "{flag} <b>{country}</b> × {count}: EOR {eor} · własna spółka {entity} ✅ spółka",
        "team.total": "<b>Razem</b>: EOR (Deel) {eor} · własne spółki ({entities}) {entity}",
        "team.eor_saves": "💡 Przez {months} EOR oszczędza ~{diff} — i nie trzeba zakładać, prowadzić ani likwidować spółek w {entities} krajach.",
        "team.entities_win": "💡 Przez {months} własne spółki byłyby tańsze o ~{diff} — Deel Payroll może prowadzić ich płace.",
        "team.mix": "💡 Najtańsze połączenie: EOR w {eor}, własna spółka z Deel Payroll w {entity} — {total}.",
        "team.breakeven": "Własna spółka opłaca się od: {list} os. (przez {months}).",
        "team.same": "Wynagrodzenie + składki, tak samo w obu wariantach: {amount}",
        "compare.header": "<b>{a} vs {b}</b> · {salary} brutto rocznie",
        "compare.row": "{flag} <b>{country}</b>: {total} rocznie · +{rate}",
        "compare.row_local": "w {currency}: {total}",
        "compare.row_eor": "EOR {fee} miesięcznie · spółka od {team} (12 mies.)",
        "compare.row_never": "EOR {fee} miesięcznie · spółka nigdy się nie opłaca",
        "compare.cheaper": "💡 Taniej: {country}, o ~{diff} rocznie ({rate} mniej).",
        "compare.fx": "<i>Przeliczone po kursach EBC z {date}.</i>",
        "sources.header": "{flag} <b>{country}: źródła</b>",
        "sources.rates": "<b>Stawki {year}</b>, obowiązują od {since} · sprawdzono {checked}",
        "sources.entity": "<b>Własna spółka</b> (szacunki, chyba że oznaczono jako oficjalne)",
        "sources.official": "oficjalne",
        "sources.per_person": "/mies. za osobę",
        "sources.replaced": "w sumach: Deel Payroll",
        "sources.notes": "<b>Uwagi</b> (po angielsku)",
        "sources.capital": "Kapitał zakładowy {amount}: zostaje w spółce, to nie koszt",
        "sources.eor": '<b>Cena EOR</b>: {provider} od {fee} miesięcznie · <a href="{url}">cennik</a>, sprawdzono {checked}',
        "sources.setup_time": "Założenie do pierwszej listy płac: {weeks}",
        "sources.exit": "Likwidacja:",
        "sources.payroll": '<b>Deel Payroll</b> dla własnej spółki: od {fee} za osobę miesięcznie · <a href="{url}">cennik</a>, sprawdzono {checked}',
        "sources.guide": '<b>Przewodnik Deel</b> · <a href="{url}">strona</a>, sprawdzono {checked}',
        "sources.guide_ok": "✅ {label}: {value}",
        "sources.guide_bad": "📝 {label}: Deel {deel}, oficjalnie {official}",
        "sources.fx": "Kursy: kursy referencyjne EBC z {date}.",
        "warn.year": "⚠️ To stawki na {year}; w {current} liczby mogą być inne.",
        "warn.unchecked": "⚠️ Oficjalne dane ostatnio sprawdzono {date}.",
        "warn.mismatch": '📝 Przewodnik Deel nadal podaje {label}: {deel}; oficjalnie od {since}: {official} (<a href="{url}">źródło</a>).',
        "warn.fx_old": "⚠️ Kursy walut z {date}.",
        "btn.compare": "🔁 Porównaj z innym krajem",
        "btn.plan": "👥 Policz dla N osób",
        "btn.sources": "📚 Źródła",
        "btn.months": "{n} mies.",
        "pick.country": "{country} — porównaj z:",
        "pick.people": "Ile osób?",
        "err.empty": "Wyślij kraj i roczne wynagrodzenie, np. <code>Polska 80k</code>.",
        "err.no_country": "Który kraj? {countries}",
        "err.no_salary": "Potrzebuję też rocznego wynagrodzenia brutto, np. <code>{example}</code>.",
        "err.unknown_word": "Nie znam „{word}”.",
        "err.unknown_word_suggest": "Nie znam „{word}”. Chodziło o <b>{suggestion}</b>?",
        "err.unknown_currency": "Brak kursu EBC dla {currency}. Użyj EUR, USD, GBP, PLN lub innej waluty EBC.",
        "err.salary_too_low": "To za mało na roczne wynagrodzenie (minimum {minimum}). Miesięczne? Dodaj <code>/mo</code>.",
        "err.salary_too_high": "Wynagrodzenie powyżej {maximum} — pewnie literówka.",
        "err.people_range": "Wielkość zespołu musi wynosić od 1 do {maximum}.",
        "err.months_range": "Okres musi wynosić od 1 do {maximum} miesięcy.",
        "err.need_two_countries": "Podaj dwa kraje: <code>/compare Germany Poland 60000</code>.",
        "err.too_many_countries": "Tu tylko jeden kraj; do porównania dwóch służy /compare.",
        "err.same_country": "To ten sam kraj — wybierz dwa różne.",
        "err.unexpected": "Nie rozumiem „{word}”.",
        "err.twice": "„{word}” powtarza coś, co już podano — zostaw jedno.",
        "err.team_needs_two": "Zespół obejmuje co najmniej dwa kraje: <code>/team Germany 2 Spain 1 70k</code>.",
        "err.stale_button": "Ten przycisk pochodzi ze starej wiadomości. Wyślij zapytanie jeszcze raz.",
        "err.internal": "Coś poszło nie tak po mojej stronie. Spróbuj ponownie za minutę.",
        "usage.cost": "Przykład: <code>/cost Bulgaria 60000 EUR</code>",
        "usage.plan": "Przykład: <code>/plan Germany 80000 5 12</code> (kraj, pensja, osoby, miesiące)",
        "usage.compare": "Przykład: <code>/compare Germany Poland 60000</code>",
        "usage.sources": "Przykład: <code>/sources Spain</code>",
        "usage.team": "Przykład: <code>/team Germany 2 UK 1 Spain 1 70k</code> (po każdym kraju liczba osób)",
        "usage.free": "Spróbuj <code>Polska 80k</code> lub /help.",
        "stats": "<b>Od startu</b> ({since})\n{lines}",
    },
    "bg": {
        "lang.prompt": _PROMPT,
        "lang.set": "Език: български. Можете да го смените по всяко време с /lang.",
        "start": (
            "👋 <b>Hire-or-Entity Advisor</b> <i>(неофициален)</i>\n\n"
            "Напишете държава, годишна брутна заплата и размер на екипа — ще покажа пълния разход "
            "на работодателя, EOR срещу собствено дружество и откога дружеството започва да се изплаща.\n\n"
            "Опитайте: <code>България 60k 5 служители</code>\n\n"
            "{countries}\n/help — всички команди"
        ),
        "help": (
            "<b>Команди</b>\n"
            "/cost <code>държава заплата [валута]</code> — разход на работодателя с разбивка\n"
            "/plan <code>държава заплата хора [месеци]</code> — EOR или собствено дружество, точка на изплащане\n"
            "/compare <code>държава1 държава2 заплата</code> — две държави една до друга\n"
            "/team <code>държава брой … заплата</code> — екип в няколко държави: EOR или дружество във всяка\n"
            "/sources <code>държава</code> — откъде е всяка цифра\n"
            "/lang — смяна на езика\n\n"
            "Или просто напишете: <code>България 60000 EUR</code>, <code>Испания 50k 3 служители 24 месеца</code>, "
            "<code>Германия vs Полша 70k</code>.\n"
            "Заплатите са <b>годишни брутни</b>; за месечна добавете <code>/mo</code>.\n\n"
            "{countries}\n\n"
            "<i>Неофициално, само оценки, не е правен или данъчен съвет.</i>"
        ),
        "countries": "Държави: {list}",
        "cost.header": "{flag} <b>{country}</b> · {salary} бруто годишно",
        "cost.monthly_input": "{monthly} месечно × 12",
        "cost.converted": "≈ {amount} по курса на ЕЦБ от {date}",
        "cost.total": "Разход на работодателя: <b>{annual}</b> годишно · {monthly} месечно",
        "cost.burden": "Над заплатата: +{amount} годишно ({rate})",
        "cost.capped": "таван",
        "cost.footer": (
            "<i>Ставки за {year}, в сила от {since}. Редовете от фиша са закръглени до цент, показани в цели суми.</i>"
        ),
        "cost.estimate_note": "<i>~ типична ставка, зависи от работодателя.</i>",
        "cost.cap_since": "<i>Максимален осигурителен доход от {date}, приложен към всеки месец.</i>",
        "cost.below_min_wage": "⚠️ Под минималната заплата за {year} ({minimum} годишно).",
        "cost.monthly_hint": "Очаквам <b>годишна</b> заплата; за месечна напишете <code>{example}</code>.",
        "plan.header": "{flag} <b>{country}</b> · {team} × {salary} годишно · {months}",
        "plan.eor": "<b>EOR ({provider})</b>: {total}",
        "plan.eor_detail": "такса {fee} на служител месечно",
        "plan.eor_fx": "(списъчна цена {price}, курс на ЕЦБ от {date})",
        "plan.entity": "<b>Собствено дружество</b>: {total}",
        "plan.entity_detail": "учредяване {setup} + закриване {exit} · {fixed} месечно + {per_employee} на служител месечно",
        "plan.entity_deel": "<b>Собствено дружество с Deel Payroll</b>: {total}",
        "plan.entity_bridge": "{weeks} за учредяване, междувременно чрез EOR: {amount}",
        "plan.switch": "💡 Време е за собствено дружество: Deel Payroll може да поеме ведомостите му за {fee} на служител месечно (включено по-горе).",
        "plan.same": "Заплата + осигуровки, еднакви и в двата варианта: {amount}",
        "plan.eor_cheaper": "💡 За {team} за {months} EOR е по-евтино с ~{diff}.",
        "plan.entity_cheaper": "💡 За {team} за {months} собственото дружество е по-евтино с ~{diff}.",
        "plan.even": "💡 За {team} за {months} двата варианта струват почти еднакво.",
        "plan.pays_off_people": "Дружеството се изплаща от {team} нагоре (за {months}).",
        "plan.pays_off_months": "При {team} се изплаща след {months}.",
        "plan.never_months": "При {team} никога не се изплаща: постоянните разходи изяждат спестеното.",
        "plan.never_people": "При тези цени дружеството никога не се изплаща.",
        "plan.note": "<i>Всеки ред има източник (/sources). Не са включени, и всичко е в полза на EOR: времето на екипа ви за дружеството, месеците, които отнема ликвидацията, и рискът от прекласифициране и място на стопанска дейност, който EOR поема вместо вас.</i>",
        "team.header": "🌍 <b>Екип в {countries} държави</b> · {team} × {salary} годишно · {months}",
        "team.row_eor": "{flag} <b>{country}</b> × {count}: EOR {eor} · собствено дружество {entity} ✅ EOR",
        "team.row_entity": "{flag} <b>{country}</b> × {count}: EOR {eor} · собствено дружество {entity} ✅ дружество",
        "team.total": "<b>Общо</b>: EOR (Deel) {eor} · собствени дружества ({entities}) {entity}",
        "team.eor_saves": "💡 За {months} EOR спестява ~{diff} — и няма дружества за учредяване, поддръжка и закриване в {entities} държави.",
        "team.entities_win": "💡 За {months} собствените дружества биха били по-евтини с ~{diff} — Deel Payroll може да поеме ведомостите им.",
        "team.mix": "💡 Най-евтината комбинация: EOR в {eor}, собствено дружество с Deel Payroll в {entity} — {total}.",
        "team.breakeven": "Собствено дружество се изплаща от: {list} служители (за {months}).",
        "team.same": "Заплата + осигуровки, еднакви и в двата варианта: {amount}",
        "compare.header": "<b>{a} vs {b}</b> · {salary} бруто годишно",
        "compare.row": "{flag} <b>{country}</b>: {total} годишно · +{rate}",
        "compare.row_local": "в {currency}: {total}",
        "compare.row_eor": "EOR {fee} месечно · дружество от {team} (12 мес.)",
        "compare.row_never": "EOR {fee} месечно · дружеството не се изплаща",
        "compare.cheaper": "💡 По-евтино: {country}, с ~{diff} годишно ({rate} по-малко).",
        "compare.fx": "<i>Превърнато по курсовете на ЕЦБ от {date}.</i>",
        "sources.header": "{flag} <b>{country}: източници</b>",
        "sources.rates": "<b>Ставки {year}</b>, в сила от {since} · проверено {checked}",
        "sources.entity": "<b>Собствено дружество</b> (оценки, освен отбелязаните като официални)",
        "sources.official": "официално",
        "sources.per_person": "/мес. на служител",
        "sources.replaced": "в сумите: Deel Payroll",
        "sources.notes": "<b>Бележки</b> (на английски)",
        "sources.capital": "Капитал {amount}: остава в дружеството, не е разход",
        "sources.eor": '<b>Цена на EOR</b>: {provider} от {fee} месечно · <a href="{url}">цени</a>, проверено {checked}',
        "sources.setup_time": "Учредяване до първата ведомост: {weeks}",
        "sources.exit": "Закриване:",
        "sources.payroll": '<b>Deel Payroll</b> за собствено дружество: от {fee} на служител месечно · <a href="{url}">цени</a>, проверено {checked}',
        "sources.guide": '<b>Ръководство на Deel</b> · <a href="{url}">страница</a>, проверено {checked}',
        "sources.guide_ok": "✅ {label}: {value}",
        "sources.guide_bad": "📝 {label}: Deel {deel}, официално {official}",
        "sources.fx": "Валутни курсове: референтни курсове на ЕЦБ от {date}.",
        "warn.year": "⚠️ Това са ставки за {year}; за {current} цифрите може да са други.",
        "warn.unchecked": "⚠️ Официалните цифри са проверени последно на {date}.",
        "warn.mismatch": '📝 В ръководството на Deel все още е {label} {deel}; официално от {since}: {official} (<a href="{url}">източник</a>).',
        "warn.fx_old": "⚠️ Валутните курсове са от {date}.",
        "btn.compare": "🔁 Сравни с друга държава",
        "btn.plan": "👥 Изчисли за N служители",
        "btn.sources": "📚 Източници",
        "btn.months": "{n} мес.",
        "pick.country": "{country} — сравни с:",
        "pick.people": "Колко служители?",
        "err.empty": "Изпратете държава и годишна заплата, напр. <code>България 60k</code>.",
        "err.no_country": "Коя държава? {countries}",
        "err.no_salary": "Нужна е и годишна брутна заплата, напр. <code>{example}</code>.",
        "err.unknown_word": "Не познавам „{word}“.",
        "err.unknown_word_suggest": "Не познавам „{word}“. Може би <b>{suggestion}</b>?",
        "err.unknown_currency": "Няма курс на ЕЦБ за {currency}. Използвайте EUR, USD, GBP, PLN или друга валута на ЕЦБ.",
        "err.salary_too_low": "Твърде малко за годишна заплата (минимум {minimum}). Месечна ли е? Добавете <code>/mo</code>.",
        "err.salary_too_high": "Заплатата е над {maximum} — вероятно грешка.",
        "err.people_range": "Размерът на екипа трябва да е между 1 и {maximum}.",
        "err.months_range": "Периодът трябва да е между 1 и {maximum} месеца.",
        "err.need_two_countries": "Посочете две държави: <code>/compare Germany Poland 60000</code>.",
        "err.too_many_countries": "Тук само една държава; за сравнение на две има /compare.",
        "err.same_country": "Това е една и съща държава — изберете две различни.",
        "err.unexpected": "Не разбрах „{word}“.",
        "err.twice": "„{word}“ повтаря вече казаното — оставете едно.",
        "err.team_needs_two": "Екипът обхваща поне две държави: <code>/team Germany 2 Spain 1 70k</code>.",
        "err.stale_button": "Този бутон е от старо съобщение. Изпратете заявката отново.",
        "err.internal": "Нещо се обърка при мен. Опитайте пак след минута.",
        "usage.cost": "Пример: <code>/cost Bulgaria 60000 EUR</code>",
        "usage.plan": "Пример: <code>/plan Germany 80000 5 12</code> (държава, заплата, хора, месеци)",
        "usage.compare": "Пример: <code>/compare Germany Poland 60000</code>",
        "usage.sources": "Пример: <code>/sources Spain</code>",
        "usage.team": "Пример: <code>/team Germany 2 UK 1 Spain 1 70k</code> (след всяка държава броят хора)",
        "usage.free": "Опитайте <code>България 60k</code> или /help.",
        "stats": "<b>От старта</b> ({since})\n{lines}",
    },
}

# What each comparable figure is called. Keys match `figures` in the country files.
FIGURES: Final[dict[Lang, dict[str, str]]] = {
    "en": {
        "minimum_wage": "minimum wage",
        "pension_rate": "pension rate",
        "unemployment_rate": "unemployment rate",
        "health_rate": "health insurance rate",
        "care_rate": "long-term care rate",
        "insolvency_rate": "insolvency levy",
        "disability_rate": "disability rate",
        "labour_fund_rate": "labour fund rate",
        "fgsp_rate": "guaranteed benefits fund rate",
        "upf_rate": "universal pension fund rate",
        "sickness_rate": "sickness and maternity rate",
        "common_contingencies_rate": "common contingencies rate",
        "mei_rate": "MEI rate",
        "training_rate": "vocational training rate",
        "fogasa_rate": "FOGASA rate",
        "workplace_pension_rate": "workplace pension minimum",
        "pension_cap": "pension contribution ceiling",
        "health_cap": "health contribution ceiling",
        "max_insurable_income": "maximum insurable income",
        "nic_rate": "employer NIC rate",
        "nic_threshold": "NIC threshold",
        "employer_total_rate": "total employer contributions",
    },
    "de": {
        "minimum_wage": "Mindestlohn",
        "pension_rate": "Rentenbeitrag",
        "unemployment_rate": "Beitrag zur Arbeitslosenversicherung",
        "health_rate": "Krankenversicherungsbeitrag",
        "care_rate": "Pflegeversicherungsbeitrag",
        "insolvency_rate": "Insolvenzgeldumlage",
        "disability_rate": "Erwerbsunfähigkeitsbeitrag",
        "labour_fund_rate": "Beitrag zum Arbeitsfonds",
        "fgsp_rate": "Beitrag zum Garantiefonds",
        "upf_rate": "Beitrag zum universellen Pensionsfonds",
        "sickness_rate": "Beitrag für Krankheit und Mutterschaft",
        "common_contingencies_rate": "Beitrag für allgemeine Risiken",
        "mei_rate": "MEI-Beitrag",
        "training_rate": "Berufsbildungsbeitrag",
        "fogasa_rate": "FOGASA-Beitrag",
        "workplace_pension_rate": "Mindestbeitrag zur Betriebsrente",
        "pension_cap": "Beitragsbemessungsgrenze Rente",
        "health_cap": "Beitragsbemessungsgrenze Krankenversicherung",
        "max_insurable_income": "maximales versichertes Einkommen",
        "nic_rate": "NIC-Satz des Arbeitgebers",
        "nic_threshold": "NIC-Schwelle",
        "employer_total_rate": "Arbeitgeberbeiträge gesamt",
    },
    "es": {
        "minimum_wage": "salario mínimo",
        "pension_rate": "cotización por pensión",
        "unemployment_rate": "cotización por desempleo",
        "health_rate": "cotización sanitaria",
        "care_rate": "cotización por dependencia",
        "insolvency_rate": "cuota de insolvencia",
        "disability_rate": "cotización por incapacidad",
        "labour_fund_rate": "cotización al Fondo de Trabajo",
        "fgsp_rate": "cotización al fondo de garantía",
        "upf_rate": "cotización al fondo universal de pensiones",
        "sickness_rate": "cotización por enfermedad y maternidad",
        "common_contingencies_rate": "contingencias comunes",
        "mei_rate": "cotización MEI",
        "training_rate": "formación profesional",
        "fogasa_rate": "FOGASA",
        "workplace_pension_rate": "pensión de empresa mínima",
        "pension_cap": "tope de cotización por pensión",
        "health_cap": "tope de cotización sanitaria",
        "max_insurable_income": "base máxima de cotización",
        "nic_rate": "tipo de NIC del empleador",
        "nic_threshold": "umbral de NIC",
        "employer_total_rate": "cotizaciones totales de la empresa",
    },
    "pl": {
        "minimum_wage": "płaca minimalna",
        "pension_rate": "składka emerytalna",
        "unemployment_rate": "składka na bezrobocie",
        "health_rate": "składka zdrowotna",
        "care_rate": "składka pielęgnacyjna",
        "insolvency_rate": "składka na fundusz upadłościowy",
        "disability_rate": "składka rentowa",
        "labour_fund_rate": "składka na Fundusz Pracy",
        "fgsp_rate": "składka na FGŚP",
        "upf_rate": "składka do powszechnego funduszu emerytalnego",
        "sickness_rate": "składka chorobowa i macierzyńska",
        "common_contingencies_rate": "składka na ryzyka ogólne",
        "mei_rate": "składka MEI",
        "training_rate": "składka na kształcenie zawodowe",
        "fogasa_rate": "składka FOGASA",
        "workplace_pension_rate": "minimalna składka emerytalna pracodawcy",
        "pension_cap": "limit składek emerytalnych",
        "health_cap": "limit składki zdrowotnej",
        "max_insurable_income": "maksymalna podstawa składek",
        "nic_rate": "stawka NIC pracodawcy",
        "nic_threshold": "próg NIC",
        "employer_total_rate": "łączne składki pracodawcy",
    },
    "bg": {
        "minimum_wage": "минимална заплата",
        "pension_rate": "пенсионна вноска",
        "unemployment_rate": "вноска за безработица",
        "health_rate": "здравна вноска",
        "care_rate": "вноска за дългосрочни грижи",
        "insolvency_rate": "вноска при несъстоятелност",
        "disability_rate": "вноска за инвалидност",
        "labour_fund_rate": "вноска във Фонда на труда",
        "fgsp_rate": "вноска във фонда за гарантирани вземания",
        "upf_rate": "вноска в универсален пенсионен фонд",
        "sickness_rate": "вноска за общо заболяване и майчинство",
        "common_contingencies_rate": "вноска за общи рискове",
        "mei_rate": "вноска MEI",
        "training_rate": "вноска за професионално обучение",
        "fogasa_rate": "вноска FOGASA",
        "workplace_pension_rate": "минимална служебна пенсионна вноска",
        "pension_cap": "таван на пенсионните вноски",
        "health_cap": "таван на здравните вноски",
        "max_insurable_income": "максимален осигурителен доход",
        "nic_rate": "ставка на NIC за работодателя",
        "nic_threshold": "праг на NIC",
        "employer_total_rate": "общо вноски на работодателя",
    },
}

PERIODS: Final[dict[Lang, dict[str, str]]] = {
    "en": {"hour": "/h", "month": "/mo", "year": "/yr"},
    "de": {"hour": "/Std.", "month": "/Mon.", "year": "/Jahr"},
    "es": {"hour": "/h", "month": "/mes", "year": "/año"},
    "pl": {"hour": "/godz.", "month": "/mies.", "year": "/rok"},
    "bg": {"hour": "/ч", "month": "/мес.", "year": "/год."},
}

# Contribution names by the `id` in the country files. English falls back to the file's own
# `name`; a test makes sure every bundled id has a name in every other language.
CONTRIBUTIONS: Final[dict[Lang, dict[str, str]]] = {
    "en": {},
    "de": {
        "pension": "Rentenversicherung", "unemployment": "Arbeitslosenversicherung",
        "health": "Krankenversicherung", "care": "Pflegeversicherung", "insolvency": "Insolvenzgeldumlage",
        "u1": "Umlage U1 (Krankheit)", "u2": "Umlage U2 (Mutterschaft)", "accident": "Unfallversicherung",
        "nic": "National Insurance", "workplace_pension": "Betriebsrente (Minimum)",
        "common_contingencies": "Allgemeine Risiken", "mei": "MEI", "training": "Berufsbildung",
        "fogasa": "FOGASA", "solidarity_1": "Solidarbeitrag bis +10 %", "solidarity_2": "Solidarbeitrag +10–50 %",
        "solidarity_3": "Solidarbeitrag über +50 %", "disability": "Erwerbsunfähigkeit",
        "labour_fund": "Arbeitsfonds + FS", "fgsp": "FGŚP", "upf": "Universeller Pensionsfonds",
        "sickness": "Krankheit und Mutterschaft",
    },
    "es": {
        "pension": "Pensión", "unemployment": "Desempleo", "health": "Seguro médico", "care": "Dependencia",
        "insolvency": "Fondo de insolvencia", "u1": "Cuota U1 (bajas)", "u2": "Cuota U2 (maternidad)",
        "accident": "Accidentes de trabajo", "nic": "National Insurance", "workplace_pension": "Pensión de empresa (mínimo)",
        "common_contingencies": "Contingencias comunes", "mei": "MEI", "training": "Formación profesional",
        "fogasa": "FOGASA", "solidarity_1": "Solidaridad, hasta +10 %", "solidarity_2": "Solidaridad, +10–50 %",
        "solidarity_3": "Solidaridad, más de +50 %", "disability": "Incapacidad",
        "labour_fund": "Fondo de Trabajo + FS", "fgsp": "FGŚP", "upf": "Fondo universal de pensiones",
        "sickness": "Enfermedad y maternidad",
    },
    "pl": {
        "pension": "Emerytalna", "unemployment": "Bezrobocie", "health": "Zdrowotna", "care": "Pielęgnacyjna",
        "insolvency": "Fundusz upadłościowy", "u1": "Składka U1 (choroba)", "u2": "Składka U2 (macierzyństwo)",
        "accident": "Wypadkowa", "nic": "National Insurance", "workplace_pension": "Emerytura pracownicza (minimum)",
        "common_contingencies": "Ryzyka ogólne", "mei": "MEI", "training": "Kształcenie zawodowe",
        "fogasa": "FOGASA", "solidarity_1": "Solidarnościowa, do +10%", "solidarity_2": "Solidarnościowa, +10–50%",
        "solidarity_3": "Solidarnościowa, ponad +50%", "disability": "Rentowa",
        "labour_fund": "Fundusz Pracy + FS", "fgsp": "FGŚP", "upf": "Powszechny fundusz emerytalny",
        "sickness": "Chorobowa i macierzyńska",
    },
    "bg": {
        "pension": "Пенсия", "unemployment": "Безработица", "health": "Здравно осигуряване",
        "care": "Дългосрочни грижи", "insolvency": "Фонд при несъстоятелност", "u1": "Вноска U1 (болнични)",
        "u2": "Вноска U2 (майчинство)", "accident": "Трудова злополука", "nic": "National Insurance",
        "workplace_pension": "Служебна пенсия (минимум)", "common_contingencies": "Общи рискове", "mei": "MEI",
        "training": "Професионално обучение", "fogasa": "FOGASA", "solidarity_1": "Солидарна, до +10%",
        "solidarity_2": "Солидарна, +10–50%", "solidarity_3": "Солидарна, над +50%",
        "disability": "Инвалидност", "labour_fund": "Фонд на труда + FS", "fgsp": "FGŚP",
        "upf": "Универсален пенсионен фонд", "sickness": "Общо заболяване и майчинство",
    },
}  # fmt: skip

COUNTRY_NAMES: Final[dict[Lang, dict[str, str]]] = {
    "en": {},
    "de": {"DE": "Deutschland", "GB": "Vereinigtes Königreich", "ES": "Spanien", "PL": "Polen", "BG": "Bulgarien"},
    "es": {"DE": "Alemania", "GB": "Reino Unido", "ES": "España", "PL": "Polonia", "BG": "Bulgaria"},
    "pl": {"DE": "Niemcy", "GB": "Wielka Brytania", "ES": "Hiszpania", "PL": "Polska", "BG": "Bułgaria"},
    "bg": {"DE": "Германия", "GB": "Великобритания", "ES": "Испания", "PL": "Полша", "BG": "България"},
}


def t(lang: Lang, key: str, **params: object) -> str:
    template = MESSAGES[lang].get(key) or MESSAGES[DEFAULT][key]
    return template.format(**params) if params else template
