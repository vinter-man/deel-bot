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
            "Tell me who you want to hire — country, people and annual gross salary — and I'll show "
            "what the EOR costs against your own company in each country, and when a company would "
            "start to pay off.\n\n"
            "Try: <code>Germany 2 × 80k</code>\nor a team: <code>Germany 2 × 80k, Spain 1 × 50k</code>\n\n"
            "{countries}\n/help — how to ask"
        ),
        "help": (
            "<b>How to ask</b>\n"
            "Country, people × annual gross salary — one country or several:\n"
            "<code>Germany 2 × 80k</code>\n"
            "<code>Germany 2 × 80k, UK 1 × £60k, Spain 1 × 50k</code>\n"
            "<code>Germany 2, Spain 1 — 70k</code> (one salary for everyone, in EUR)\n"
            "A salary is in the country's own currency unless you write another; for a monthly one add "
            "<code>/mo</code>; a horizon goes at the end: <code>… 24 months</code>.\n\n"
            "<b>Commands</b>\n"
            "/team — the same, as a command\n"
            "/sources <code>country</code> — where every figure comes from\n"
            "/lang — change language\n\n"
            "{countries}\n\n"
            "<i>Unofficial, estimates only, not legal or tax advice.</i>"
        ),
        "countries": "Countries: {list}",
        "team.below_min_wage": "⚠️ Below the {year} minimum wage ({minimum} a year).",
        "team.even": "💡 For {team} over {months} both cost about the same.",
        "team.header": "🌍 <b>Team in {countries} countries</b> · {team} · {months}",
        "team.header_one": "{flag} <b>{country}</b> · {team} · {months}",
        "team.country": "{flag} <b>{country}</b> · {team} × {salary}",
        "team.eor_line": "EOR (Deel): {amount}",
        "team.entity_line": "Own entity: {amount}",
        "team.note": "<i>EOR fees against own-entity costs; salary + contributions ({amount}) are the same either way. Totals in EUR at ECB rates of {date}. Every figure: /sources.</i>",
        "team.total": "<b>Total</b>: EOR (Deel) {eor} · {entities} own entities {entity}",
        "team.total_one": "<b>Total</b>: EOR (Deel) {eor} · own entity {entity}",
        "team.eor_saves": "💡 Over {months} EOR saves ~{diff} — and no company to open, run and close in {entities} countries.",
        "team.eor_saves_one": "💡 Over {months} EOR saves ~{diff} — and no company to open, run and close.",
        "team.entities_win": "💡 Over {months} own entities would be ~{diff} cheaper — Deel Payroll can run their payroll.",
        "team.entities_win_one": "💡 Over {months} an own entity would be ~{diff} cheaper — Deel Payroll can run its payroll.",
        "team.mix": "💡 Cheapest mix: EOR in {eor}, own entity on Deel Payroll in {entity} — {total}.",
        "team.breakeven": "An own entity pays off from: {list} people (over {months}).",
        "team.guides": "📝 Deel's guides for {flags} still show some figures that have since changed — details in /sources.",
        "chart.title": "Team in {countries} countries · {team} · {months}",
        "chart.title_one": "{country} · {team} · {months}",
        "chart.subtitle": "EOR fees vs own-entity costs over the horizon, EUR",
        "chart.eor": "EOR (Deel)",
        "chart.entity": "Own entity",
        "chart.cheaper": "cheaper",
        "chart.total": "Total: EOR {eor} · {entities} own entities {entity}",
        "chart.total_one": "Total: EOR {eor} · own entity {entity}",
        "chart.eor_saves": "EOR saves ~{diff}",
        "chart.even": "About the same either way",
        "chart.entities_save": "Own entities save ~{diff}",
        "chart.entities_save_one": "An own entity saves ~{diff}",
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
        "warn.fx_old": "⚠️ Exchange rates are from {date}.",
        "btn.months": "{n} mo",
        "err.empty": "Send a country, people and an annual salary, e.g. <code>Germany 2 × 80k</code>.",
        "err.no_country": "Which country? {countries}",
        "err.no_salary": "I need an annual gross salary too, e.g. <code>{example}</code>.",
        "err.unknown_word": "I don't know “{word}”.",
        "err.unknown_word_suggest": "I don't know “{word}”. Did you mean <b>{suggestion}</b>?",
        "err.unknown_currency": "No ECB rate for {currency}. Use EUR, USD, GBP, PLN or another ECB currency.",
        "err.salary_too_low": "That salary looks too small for a year (minimum {minimum}). Monthly? Add <code>/mo</code>.",
        "err.salary_too_high": "That salary is above {maximum} — probably a typo.",
        "err.people_range": "Team size must be between 1 and {maximum}.",
        "err.months_range": "The horizon must be between 1 and {maximum} months.",
        "err.same_country": "Each country once, please — add up its head count.",
        "err.unexpected": "I didn't understand “{word}”.",
        "err.twice": "“{word}” says the same thing twice — keep one.",
        "err.team_salary": "Give {country} a salary too, e.g. <code>Germany 2 × 80k, Spain 1 × 50k</code>.",
        "err.stale_button": "That button belongs to an old message. Send the query again.",
        "err.internal": "Something went wrong on my side. Please try again in a minute.",
        "usage.sources": "Usage: <code>/sources Spain</code>",
        "usage.team": "Usage: <code>/team Germany 2 × 80k, UK 1 × £60k, Spain 1 × 50k</code> (people × salary per country, one per line or comma)",
        "stats": "<b>Since start</b> ({since})\n{lines}",
    },
    "de": {
        "lang.prompt": _PROMPT,
        "lang.set": "Sprache: Deutsch. Ändern kannst du sie jederzeit mit /lang.",
        "start": (
            "👋 <b>Hire-or-Entity Advisor</b> <i>(inoffiziell)</i>\n\n"
            "Sag mir, wen du einstellen willst – Land, Personen und Bruttojahresgehalt –, und ich zeige, "
            "was EOR gegenüber einer eigenen Gesellschaft in jedem Land kostet und ab wann sich eine "
            "Gesellschaft rechnet.\n\n"
            "Probier: <code>Deutschland 2 × 80k</code>\noder ein Team: <code>Deutschland 2 × 80k, Spanien 1 × 50k</code>\n\n"
            "{countries}\n/help – so fragst du"
        ),
        "help": (
            "<b>So fragst du</b>\n"
            "Land, Personen × Bruttojahresgehalt – ein Land oder mehrere:\n"
            "<code>Deutschland 2 × 80k</code>\n"
            "<code>Deutschland 2 × 80k, UK 1 × £60k, Spanien 1 × 50k</code>\n"
            "<code>Deutschland 2, Spanien 1 — 70k</code> (ein Gehalt für alle, in EUR)\n"
            "Ein Gehalt ist in der Währung des Landes, außer du schreibst eine andere; für ein Monatsgehalt "
            "<code>/mo</code> anhängen; ein Zeitraum kommt ans Ende: <code>… 24 Monate</code>.\n\n"
            "<b>Befehle</b>\n"
            "/team – dasselbe als Befehl\n"
            "/sources <code>Land</code> – woher jede Zahl stammt\n"
            "/lang – Sprache ändern\n\n"
            "{countries}\n\n"
            "<i>Inoffiziell, nur Schätzungen, keine Rechts- oder Steuerberatung.</i>"
        ),
        "countries": "Länder: {list}",
        "team.below_min_wage": "⚠️ Unter dem Mindestlohn {year} ({minimum} im Jahr).",
        "team.even": "💡 Für {team} über {months} kosten beide etwa gleich viel.",
        "team.header": "🌍 <b>Team in {countries} Ländern</b> · {team} · {months}",
        "team.header_one": "{flag} <b>{country}</b> · {team} · {months}",
        "team.country": "{flag} <b>{country}</b> · {team} × {salary}",
        "team.eor_line": "EOR (Deel): {amount}",
        "team.entity_line": "Eigene Gesellschaft: {amount}",
        "team.note": "<i>EOR-Gebühren gegen Kosten eigener Gesellschaften; Gehalt + Beiträge ({amount}) sind in beiden Fällen gleich. Summen in EUR zu EZB-Kursen vom {date}. Alle Zahlen: /sources.</i>",
        "team.total": "<b>Gesamt</b>: EOR (Deel) {eor} · {entities} eigene Gesellschaften {entity}",
        "team.total_one": "<b>Gesamt</b>: EOR (Deel) {eor} · eigene Gesellschaft {entity}",
        "team.eor_saves": "💡 Über {months} spart EOR ~{diff} – und keine Gesellschaft zu gründen, zu führen und zu schließen in {entities} Ländern.",
        "team.eor_saves_one": "💡 Über {months} spart EOR ~{diff} – und keine Gesellschaft zu gründen, zu führen und zu schließen.",
        "team.entities_win": "💡 Über {months} wären eigene Gesellschaften ~{diff} günstiger – Deel Payroll kann ihre Abrechnung übernehmen.",
        "team.entities_win_one": "💡 Über {months} wäre eine eigene Gesellschaft ~{diff} günstiger – Deel Payroll kann ihre Abrechnung übernehmen.",
        "team.mix": "💡 Günstigste Kombination: EOR in {eor}, eigene Gesellschaft mit Deel Payroll in {entity} – {total}.",
        "team.breakeven": "Eine eigene Gesellschaft rechnet sich ab: {list} Personen (über {months}).",
        "team.guides": "📝 Die Deel-Leitfäden für {flags} zeigen noch einige inzwischen geänderte Zahlen – Details unter /sources.",
        "chart.title": "Team in {countries} Ländern · {team} · {months}",
        "chart.title_one": "{country} · {team} · {months}",
        "chart.subtitle": "EOR-Gebühren vs. Kosten eigener Gesellschaften im Zeitraum, EUR",
        "chart.eor": "EOR (Deel)",
        "chart.entity": "Eigene Ges.",
        "chart.cheaper": "günstiger",
        "chart.total": "Gesamt: EOR {eor} · {entities} eigene Gesellschaften {entity}",
        "chart.total_one": "Gesamt: EOR {eor} · eigene Gesellschaft {entity}",
        "chart.eor_saves": "EOR spart ~{diff}",
        "chart.even": "Beide etwa gleich teuer",
        "chart.entities_save": "Eigene Gesellschaften sparen ~{diff}",
        "chart.entities_save_one": "Eigene Gesellschaft spart ~{diff}",
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
        "warn.fx_old": "⚠️ Wechselkurse vom {date}.",
        "btn.months": "{n} Mon.",
        "err.empty": "Schick Land, Personen und Jahresgehalt, z. B. <code>Deutschland 2 × 80k</code>.",
        "err.no_country": "Welches Land? {countries}",
        "err.no_salary": "Ich brauche auch ein Bruttojahresgehalt, z. B. <code>{example}</code>.",
        "err.unknown_word": "„{word}“ kenne ich nicht.",
        "err.unknown_word_suggest": "„{word}“ kenne ich nicht. Meintest du <b>{suggestion}</b>?",
        "err.unknown_currency": "Für {currency} gibt es keinen EZB-Kurs. Nimm EUR, USD, GBP, PLN oder eine andere EZB-Währung.",
        "err.salary_too_low": "Für ein Jahresgehalt zu niedrig (mindestens {minimum}). Monatlich? <code>/mo</code> anhängen.",
        "err.salary_too_high": "Das Gehalt liegt über {maximum} – wohl ein Tippfehler.",
        "err.people_range": "Die Teamgröße muss zwischen 1 und {maximum} liegen.",
        "err.months_range": "Der Zeitraum muss zwischen 1 und {maximum} Monaten liegen.",
        "err.same_country": "Jedes Land bitte nur einmal – zähl die Personen zusammen.",
        "err.unexpected": "„{word}“ habe ich nicht verstanden.",
        "err.twice": "„{word}“ sagt etwas zum zweiten Mal – lass eins weg.",
        "err.team_salary": "Gib auch {country} ein Gehalt, z. B. <code>Germany 2 × 80k, Spain 1 × 50k</code>.",
        "err.stale_button": "Diese Schaltfläche gehört zu einer alten Nachricht. Schick die Anfrage noch einmal.",
        "err.internal": "Bei mir ist etwas schiefgelaufen. Versuch es in einer Minute noch einmal.",
        "usage.sources": "Beispiel: <code>/sources Spain</code>",
        "usage.team": "Beispiel: <code>/team Germany 2 × 80k, UK 1 × £60k, Spain 1 × 50k</code> (Personen × Gehalt je Land, pro Zeile oder mit Komma)",
        "stats": "<b>Seit dem Start</b> ({since})\n{lines}",
    },
    "es": {
        "lang.prompt": _PROMPT,
        "lang.set": "Idioma: español. Cámbialo cuando quieras con /lang.",
        "start": (
            "👋 <b>Hire-or-Entity Advisor</b> <i>(no oficial)</i>\n\n"
            "Dime a quién quieres contratar —país, personas y salario bruto anual— y te muestro cuánto "
            "cuesta el EOR frente a una sociedad propia en cada país y desde cuándo compensaría la "
            "sociedad.\n\n"
            "Prueba: <code>Alemania 2 × 80k</code>\no un equipo: <code>Alemania 2 × 80k, España 1 × 50k</code>\n\n"
            "{countries}\n/help — cómo preguntar"
        ),
        "help": (
            "<b>Cómo preguntar</b>\n"
            "País, personas × salario bruto anual — uno o varios países:\n"
            "<code>Alemania 2 × 80k</code>\n"
            "<code>Alemania 2 × 80k, UK 1 × £60k, España 1 × 50k</code>\n"
            "<code>Alemania 2, España 1 — 70k</code> (un salario para todos, en EUR)\n"
            "El salario va en la moneda del país salvo que escribas otra; para uno mensual añade "
            "<code>/mo</code>; el horizonte va al final: <code>… 24 meses</code>.\n\n"
            "<b>Comandos</b>\n"
            "/team — lo mismo, como comando\n"
            "/sources <code>país</code> — de dónde sale cada cifra\n"
            "/lang — cambiar idioma\n\n"
            "{countries}\n\n"
            "<i>No oficial, solo estimaciones, no es asesoramiento legal ni fiscal.</i>"
        ),
        "countries": "Países: {list}",
        "team.below_min_wage": "⚠️ Por debajo del salario mínimo de {year} ({minimum} al año).",
        "team.even": "💡 Para {team} durante {months}, ambas opciones cuestan más o menos lo mismo.",
        "team.header": "🌍 <b>Equipo en {countries} países</b> · {team} · {months}",
        "team.header_one": "{flag} <b>{country}</b> · {team} · {months}",
        "team.country": "{flag} <b>{country}</b> · {team} × {salary}",
        "team.eor_line": "EOR (Deel): {amount}",
        "team.entity_line": "Sociedad propia: {amount}",
        "team.note": "<i>Cuotas EOR frente a costes de sociedades propias; salario + cotizaciones ({amount}) son iguales en ambos casos. Totales en EUR a tipos del BCE del {date}. Todas las cifras: /sources.</i>",
        "team.total": "<b>Total</b>: EOR (Deel) {eor} · {entities} sociedades propias {entity}",
        "team.total_one": "<b>Total</b>: EOR (Deel) {eor} · sociedad propia {entity}",
        "team.eor_saves": "💡 En {months}, el EOR ahorra ~{diff}, sin ninguna sociedad que abrir, gestionar y cerrar en {entities} países.",
        "team.eor_saves_one": "💡 En {months}, el EOR ahorra ~{diff}, sin ninguna sociedad que abrir, gestionar y cerrar.",
        "team.entities_win": "💡 En {months}, las sociedades propias saldrían ~{diff} más baratas; Deel Payroll puede gestionar sus nóminas.",
        "team.entities_win_one": "💡 En {months}, una sociedad propia saldría ~{diff} más barata; Deel Payroll puede gestionar sus nóminas.",
        "team.mix": "💡 La combinación más barata: EOR en {eor}, sociedad propia con Deel Payroll en {entity}: {total}.",
        "team.breakeven": "Una sociedad propia compensa a partir de: {list} personas (en {months}).",
        "team.guides": "📝 Las guías de Deel de {flags} aún muestran algunas cifras que han cambiado; detalles en /sources.",
        "chart.title": "Equipo en {countries} países · {team} · {months}",
        "chart.title_one": "{country} · {team} · {months}",
        "chart.subtitle": "Cuotas EOR frente a costes de sociedades propias en el periodo, EUR",
        "chart.eor": "EOR (Deel)",
        "chart.entity": "Sociedad propia",
        "chart.cheaper": "más barato",
        "chart.total": "Total: EOR {eor} · {entities} sociedades propias {entity}",
        "chart.total_one": "Total: EOR {eor} · sociedad propia {entity}",
        "chart.eor_saves": "El EOR ahorra ~{diff}",
        "chart.even": "Ambas opciones cuestan casi lo mismo",
        "chart.entities_save": "Las sociedades ahorran ~{diff}",
        "chart.entities_save_one": "La sociedad ahorra ~{diff}",
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
        "warn.fx_old": "⚠️ Los tipos de cambio son del {date}.",
        "btn.months": "{n} meses",
        "err.empty": "Envía país, personas y salario anual, p. ej. <code>Alemania 2 × 80k</code>.",
        "err.no_country": "¿Qué país? {countries}",
        "err.no_salary": "También necesito un salario bruto anual, p. ej. <code>{example}</code>.",
        "err.unknown_word": "No conozco «{word}».",
        "err.unknown_word_suggest": "No conozco «{word}». ¿Querías decir <b>{suggestion}</b>?",
        "err.unknown_currency": "No hay tipo del BCE para {currency}. Usa EUR, USD, GBP, PLN u otra moneda del BCE.",
        "err.salary_too_low": "Parece poco para un salario anual (mínimo {minimum}). ¿Es mensual? Añade <code>/mo</code>.",
        "err.salary_too_high": "El salario supera {maximum}; seguramente es una errata.",
        "err.people_range": "El tamaño del equipo debe estar entre 1 y {maximum}.",
        "err.months_range": "El horizonte debe estar entre 1 y {maximum} meses.",
        "err.same_country": "Cada país una sola vez, por favor: suma las personas.",
        "err.unexpected": "No he entendido «{word}».",
        "err.twice": "«{word}» repite algo que ya has dicho; deja solo uno.",
        "err.team_salary": "Indica también un salario para {country}, p. ej. <code>Germany 2 × 80k, Spain 1 × 50k</code>.",
        "err.stale_button": "Ese botón es de un mensaje antiguo. Vuelve a enviar la consulta.",
        "err.internal": "Algo ha fallado por mi parte. Inténtalo de nuevo en un minuto.",
        "usage.sources": "Ejemplo: <code>/sources Spain</code>",
        "usage.team": "Ejemplo: <code>/team Germany 2 × 80k, UK 1 × £60k, Spain 1 × 50k</code> (personas × salario por país, en líneas o con comas)",
        "stats": "<b>Desde el inicio</b> ({since})\n{lines}",
    },
    "pl": {
        "lang.prompt": _PROMPT,
        "lang.set": "Język: polski. Zmienisz go w każdej chwili przez /lang.",
        "start": (
            "👋 <b>Hire-or-Entity Advisor</b> <i>(nieoficjalny)</i>\n\n"
            "Napisz, kogo chcesz zatrudnić — kraj, liczbę osób i roczne wynagrodzenie brutto — a pokażę, "
            "ile kosztuje EOR w porównaniu z własną spółką w każdym kraju i od kiedy spółka zaczęłaby "
            "się opłacać.\n\n"
            "Spróbuj: <code>Niemcy 2 × 80k</code>\nalbo zespół: <code>Niemcy 2 × 80k, Polska 1 × 200k</code>\n\n"
            "{countries}\n/help — jak pytać"
        ),
        "help": (
            "<b>Jak pytać</b>\n"
            "Kraj, osoby × roczne wynagrodzenie brutto — jeden kraj lub kilka:\n"
            "<code>Niemcy 2 × 80k</code>\n"
            "<code>Niemcy 2 × 80k, UK 1 × £60k, Polska 1 × 200k</code>\n"
            "<code>Niemcy 2, Hiszpania 1 — 70k</code> (jedna pensja dla wszystkich, w EUR)\n"
            "Pensja jest w walucie kraju, chyba że podasz inną; dla miesięcznej dodaj <code>/mo</code>; "
            "okres na końcu: <code>… 24 miesiące</code>.\n\n"
            "<b>Polecenia</b>\n"
            "/team — to samo jako polecenie\n"
            "/sources <code>kraj</code> — skąd pochodzi każda liczba\n"
            "/lang — zmiana języka\n\n"
            "{countries}\n\n"
            "<i>Nieoficjalne, tylko szacunki, nie jest to porada prawna ani podatkowa.</i>"
        ),
        "countries": "Kraje: {list}",
        "team.below_min_wage": "⚠️ Poniżej płacy minimalnej na {year} ({minimum} rocznie).",
        "team.even": "💡 Dla {team} przez {months} oba warianty kosztują mniej więcej tyle samo.",
        "team.header": "🌍 <b>Zespół w {countries} krajach</b> · {team} · {months}",
        "team.header_one": "{flag} <b>{country}</b> · {team} · {months}",
        "team.country": "{flag} <b>{country}</b> · {team} × {salary}",
        "team.eor_line": "EOR (Deel): {amount}",
        "team.entity_line": "Własna spółka: {amount}",
        "team.note": "<i>Opłaty EOR wobec kosztów własnych spółek; wynagrodzenie + składki ({amount}) są takie same w obu wariantach. Sumy w EUR po kursach EBC z {date}. Wszystkie liczby: /sources.</i>",
        "team.total": "<b>Razem</b>: EOR (Deel) {eor} · własne spółki ({entities}) {entity}",
        "team.total_one": "<b>Razem</b>: EOR (Deel) {eor} · własna spółka {entity}",
        "team.eor_saves": "💡 Przez {months} EOR oszczędza ~{diff} — i nie trzeba zakładać, prowadzić ani likwidować spółek w {entities} krajach.",
        "team.eor_saves_one": "💡 Przez {months} EOR oszczędza ~{diff} — i nie trzeba zakładać, prowadzić ani likwidować spółki.",
        "team.entities_win": "💡 Przez {months} własne spółki byłyby tańsze o ~{diff} — Deel Payroll może prowadzić ich płace.",
        "team.entities_win_one": "💡 Przez {months} własna spółka byłaby tańsza o ~{diff} — Deel Payroll może prowadzić jej płace.",
        "team.mix": "💡 Najtańsze połączenie: EOR w {eor}, własna spółka z Deel Payroll w {entity} — {total}.",
        "team.breakeven": "Własna spółka opłaca się od: {list} os. (przez {months}).",
        "team.guides": "📝 Przewodniki Deel dla {flags} nadal podają niektóre nieaktualne liczby — szczegóły w /sources.",
        "chart.title": "Zespół w {countries} krajach · {team} · {months}",
        "chart.title_one": "{country} · {team} · {months}",
        "chart.subtitle": "Opłaty EOR wobec kosztów własnych spółek w okresie, EUR",
        "chart.eor": "EOR (Deel)",
        "chart.entity": "Własna spółka",
        "chart.cheaper": "taniej",
        "chart.total": "Razem: EOR {eor} · własne spółki ({entities}) {entity}",
        "chart.total_one": "Razem: EOR {eor} · własna spółka {entity}",
        "chart.eor_saves": "EOR oszczędza ~{diff}",
        "chart.even": "Oba warianty kosztują mniej więcej tyle samo",
        "chart.entities_save": "Własne spółki oszczędzają ~{diff}",
        "chart.entities_save_one": "Własna spółka oszczędza ~{diff}",
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
        "warn.fx_old": "⚠️ Kursy walut z {date}.",
        "btn.months": "{n} mies.",
        "err.empty": "Wyślij kraj, liczbę osób i roczne wynagrodzenie, np. <code>Niemcy 2 × 80k</code>.",
        "err.no_country": "Który kraj? {countries}",
        "err.no_salary": "Potrzebuję też rocznego wynagrodzenia brutto, np. <code>{example}</code>.",
        "err.unknown_word": "Nie znam „{word}”.",
        "err.unknown_word_suggest": "Nie znam „{word}”. Chodziło o <b>{suggestion}</b>?",
        "err.unknown_currency": "Brak kursu EBC dla {currency}. Użyj EUR, USD, GBP, PLN lub innej waluty EBC.",
        "err.salary_too_low": "To za mało na roczne wynagrodzenie (minimum {minimum}). Miesięczne? Dodaj <code>/mo</code>.",
        "err.salary_too_high": "Wynagrodzenie powyżej {maximum} — pewnie literówka.",
        "err.people_range": "Wielkość zespołu musi wynosić od 1 do {maximum}.",
        "err.months_range": "Okres musi wynosić od 1 do {maximum} miesięcy.",
        "err.same_country": "Każdy kraj tylko raz — zsumuj liczbę osób.",
        "err.unexpected": "Nie rozumiem „{word}”.",
        "err.twice": "„{word}” powtarza coś, co już podano — zostaw jedno.",
        "err.team_salary": "Podaj też pensję dla {country}, np. <code>Germany 2 × 80k, Spain 1 × 50k</code>.",
        "err.stale_button": "Ten przycisk pochodzi ze starej wiadomości. Wyślij zapytanie jeszcze raz.",
        "err.internal": "Coś poszło nie tak po mojej stronie. Spróbuj ponownie za minutę.",
        "usage.sources": "Przykład: <code>/sources Spain</code>",
        "usage.team": "Przykład: <code>/team Germany 2 × 80k, UK 1 × £60k, Spain 1 × 50k</code> (osoby × pensja dla kraju, w wierszach lub po przecinku)",
        "stats": "<b>Od startu</b> ({since})\n{lines}",
    },
    "bg": {
        "lang.prompt": _PROMPT,
        "lang.set": "Език: български. Можете да го смените по всяко време с /lang.",
        "start": (
            "👋 <b>Hire-or-Entity Advisor</b> <i>(неофициален)</i>\n\n"
            "Напишете кого искате да наемете — държава, брой хора и годишна брутна заплата — и ще покажа "
            "колко струва EOR спрямо собствено дружество във всяка държава и откога дружеството би "
            "започнало да се изплаща.\n\n"
            "Опитайте: <code>Германия 2 × 80k</code>\nили екип: <code>Германия 2 × 80k, България 1 × 30k</code>\n\n"
            "{countries}\n/help — как да питате"
        ),
        "help": (
            "<b>Как да питате</b>\n"
            "Държава, хора × годишна брутна заплата — една държава или няколко:\n"
            "<code>Германия 2 × 80k</code>\n"
            "<code>Германия 2 × 80k, UK 1 × £60k, Испания 1 × 50k</code>\n"
            "<code>Германия 2, Испания 1 — 70k</code> (една заплата за всички, в EUR)\n"
            "Заплатата е във валутата на държавата, освен ако не посочите друга; за месечна добавете "
            "<code>/mo</code>; периодът е накрая: <code>… 24 месеца</code>.\n\n"
            "<b>Команди</b>\n"
            "/team — същото, като команда\n"
            "/sources <code>държава</code> — откъде е всяка цифра\n"
            "/lang — смяна на езика\n\n"
            "{countries}\n\n"
            "<i>Неофициално, само приблизителни оценки, не е правен или данъчен съвет.</i>"
        ),
        "countries": "Държави: {list}",
        "team.below_min_wage": "⚠️ Под минималната заплата за {year} ({minimum} годишно).",
        "team.even": "💡 За {team} за {months} двата варианта струват почти еднакво.",
        "team.header": "🌍 <b>Екип в {countries} държави</b> · {team} · {months}",
        "team.header_one": "{flag} <b>{country}</b> · {team} · {months}",
        "team.country": "{flag} <b>{country}</b> · {team} × {salary}",
        "team.eor_line": "EOR (Deel): {amount}",
        "team.entity_line": "Собствено дружество: {amount}",
        "team.note": "<i>Такси EOR срещу разходи за собствени дружества; заплата + осигуровки ({amount}) са еднакви и в двата варианта. Суми в EUR по курсовете на ЕЦБ от {date}. Всички цифри: /sources.</i>",
        "team.total": "<b>Общо</b>: EOR (Deel) {eor} · собствени дружества ({entities}) {entity}",
        "team.total_one": "<b>Общо</b>: EOR (Deel) {eor} · собствено дружество {entity}",
        "team.eor_saves": "💡 За {months} EOR спестява ~{diff} — и няма дружества за учредяване, поддръжка и закриване в {entities} държави.",
        "team.eor_saves_one": "💡 За {months} EOR спестява ~{diff} — и няма дружество за учредяване, поддръжка и закриване.",
        "team.entities_win": "💡 За {months} собствените дружества биха били по-евтини с ~{diff} — Deel Payroll може да поеме ведомостите им.",
        "team.entities_win_one": "💡 За {months} собствено дружество би било по-евтино с ~{diff} — Deel Payroll може да поеме ведомостите му.",
        "team.mix": "💡 Най-евтината комбинация: EOR в {eor}, собствено дружество с Deel Payroll в {entity} — {total}.",
        "team.breakeven": "Собствено дружество се изплаща от: {list} служители (за {months}).",
        "team.guides": "📝 Ръководствата на Deel за {flags} все още показват някои вече променени цифри — подробности в /sources.",
        "chart.title": "Екип в {countries} държави · {team} · {months}",
        "chart.title_one": "{country} · {team} · {months}",
        "chart.subtitle": "Такси EOR срещу разходи за собствени дружества за периода, EUR",
        "chart.eor": "EOR (Deel)",
        "chart.entity": "Собств. дружество",
        "chart.cheaper": "по-евтино",
        "chart.total": "Общо: EOR {eor} · собствени дружества ({entities}) {entity}",
        "chart.total_one": "Общо: EOR {eor} · собствено дружество {entity}",
        "chart.eor_saves": "EOR спестява ~{diff}",
        "chart.even": "Двата варианта струват почти еднакво",
        "chart.entities_save": "Собствените дружества спестяват ~{diff}",
        "chart.entities_save_one": "Собственото дружество спестява ~{diff}",
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
        "warn.fx_old": "⚠️ Валутните курсове са от {date}.",
        "btn.months": "{n} мес.",
        "err.empty": "Изпратете държава, брой хора и годишна заплата, напр. <code>Германия 2 × 80k</code>.",
        "err.no_country": "Коя държава? {countries}",
        "err.no_salary": "Нужна е и годишна брутна заплата, напр. <code>{example}</code>.",
        "err.unknown_word": "Не познавам „{word}“.",
        "err.unknown_word_suggest": "Не познавам „{word}“. Може би <b>{suggestion}</b>?",
        "err.unknown_currency": "Няма курс на ЕЦБ за {currency}. Използвайте EUR, USD, GBP, PLN или друга валута на ЕЦБ.",
        "err.salary_too_low": "Твърде малко за годишна заплата (минимум {minimum}). Месечна ли е? Добавете <code>/mo</code>.",
        "err.salary_too_high": "Заплатата е над {maximum} — вероятно грешка.",
        "err.people_range": "Размерът на екипа трябва да е между 1 и {maximum}.",
        "err.months_range": "Периодът трябва да е между 1 и {maximum} месеца.",
        "err.same_country": "Всяка държава само веднъж — съберете броя на хората.",
        "err.unexpected": "Не разбрах „{word}“.",
        "err.twice": "„{word}“ повтаря вече казаното — оставете едно.",
        "err.team_salary": "Посочете заплата и за {country}, напр. <code>Germany 2 × 80k, Spain 1 × 50k</code>.",
        "err.stale_button": "Този бутон е от старо съобщение. Изпратете заявката отново.",
        "err.internal": "Нещо се обърка при мен. Опитайте пак след минута.",
        "usage.sources": "Пример: <code>/sources Spain</code>",
        "usage.team": "Пример: <code>/team Germany 2 × 80k, UK 1 × £60k, Spain 1 × 50k</code> (хора × заплата за държава, на ред или със запетая)",
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
