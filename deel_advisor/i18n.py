"""The bot's copy in English, Ukrainian and Russian.

Plain dictionaries rather than gettext: three languages and ~90 strings do not need a build
step, and a test makes sure every key exists in every language with the same placeholders.
"""

from __future__ import annotations

from typing import Final, Literal

Lang = Literal["en", "uk", "ru"]
LANGS: Final[tuple[Lang, ...]] = ("en", "uk", "ru")
DEFAULT: Final[Lang] = "en"
LANG_NAMES: Final[dict[Lang, str]] = {"en": "🇬🇧 English", "uk": "🇺🇦 Українська", "ru": "Русский"}


def pick_lang(code: str | None) -> Lang:
    """A Telegram `language_code` to one of ours; `uk` and `ru` as themselves, else English."""
    if code:
        base = code.split("-")[0].lower()
        if base == "uk":
            return "uk"
        if base in ("ru", "be", "kk"):
            return "ru"
    return DEFAULT


def plural(lang: Lang, n: int, forms: tuple[str, str, str]) -> str:
    """forms = (one, few, many); English uses only one/many."""
    if lang == "en":
        return forms[0] if n == 1 else forms[2]
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return forms[1]
    return forms[2]


_PEOPLE: dict[Lang, tuple[str, str, str]] = {
    "en": ("person", "people", "people"),
    "uk": ("особа", "особи", "осіб"),
    "ru": ("человек", "человека", "человек"),
}
# After "for"/"from" Russian and Ukrainian need the genitive: "для 3 человек", "від 9 осіб".
_PEOPLE_GEN: dict[Lang, tuple[str, str, str]] = {
    "en": ("person", "people", "people"),
    "uk": ("особи", "осіб", "осіб"),
    "ru": ("человека", "человек", "человек"),
}
_MONTHS: dict[Lang, tuple[str, str, str]] = {
    "en": ("month", "months", "months"),
    "uk": ("місяць", "місяці", "місяців"),
    "ru": ("месяц", "месяца", "месяцев"),
}


def people(lang: Lang, n: int) -> str:
    return f"{n} {plural(lang, n, _PEOPLE[lang])}"


def people_gen(lang: Lang, n: int) -> str:
    return f"{n} {plural(lang, n, _PEOPLE_GEN[lang])}"


def months(lang: Lang, n: int) -> str:
    return f"{n} {plural(lang, n, _MONTHS[lang])}"


MESSAGES: Final[dict[Lang, dict[str, str]]] = {
    "en": {
        "lang.prompt": "🌐 Choose your language · Оберіть мову · Выберите язык",
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
        "cost.below_min_wage": (
            "⚠️ Below the {year} minimum wage ({minimum} a year). I expect an <b>annual</b> salary; "
            "for a monthly one write <code>{example}</code>."
        ),
        "plan.header": "{flag} <b>{country}</b> · {team} × {salary} a year · {months}",
        "plan.eor": "<b>EOR ({provider})</b>: {total}",
        "plan.eor_detail": "fee {fee} per person a month",
        "plan.entity": "<b>Own entity</b>: {total}",
        "plan.entity_detail": "setup {setup} + {fixed} a month + {per_employee} per person a month",
        "plan.same": "Salary + contributions, identical either way: {amount}",
        "plan.eor_cheaper": "💡 For {team} over {months} EOR is cheaper by ~{diff}.",
        "plan.entity_cheaper": "💡 For {team} over {months} your own entity is cheaper by ~{diff}.",
        "plan.even": "💡 For {team} over {months} both cost about the same.",
        "plan.pays_off_people": "An entity pays off from {team} (over {months}).",
        "plan.pays_off_months": "With {team} it pays off after {months}.",
        "plan.never_months": "With {team} it never pays off: the fixed costs eat the saving.",
        "plan.never_people": "At these prices an entity never pays off.",
        "plan.note": (
            "<i>Direct costs only, each with a source (/sources). Not priced: the weeks an entity takes "
            "to set up, your team's time and the compliance risk an EOR carries for you.</i>"
        ),
        "compare.header": "<b>{a} vs {b}</b> · {salary} gross a year",
        "compare.row": "{flag} <b>{country}</b>: {total} a year · +{rate}",
        "compare.row_local": "in {currency}: {total}",
        "compare.row_eor": "EOR {fee} a month · entity from {team} (12 mo)",
        "compare.row_never": "EOR {fee} a month · entity never pays off",
        "compare.cheaper": "💡 {country} is cheaper to employ in by ~{diff} a year ({rate} less).",
        "compare.fx": "<i>Converted at ECB rates of {date}.</i>",
        "sources.header": "{flag} <b>{country}: sources</b>",
        "sources.rates": "<b>Rates {year}</b>, in force since {since} · checked {checked}",
        "sources.entity": "<b>Own entity</b> (estimates)",
        "sources.capital": "Share capital {amount}: stays the company's, not a cost",
        "sources.eor": '<b>EOR price</b>: {provider} from {fee} a month · <a href="{url}">pricing</a>, checked {checked}',
        "sources.guide": '<b>Deel guide</b> · <a href="{url}">page</a>, checked {checked}',
        "sources.guide_ok": "✅ {label}: {value}",
        "sources.guide_bad": "⚠️ {label}: Deel {deel}, official {official}",
        "sources.fx": "FX: ECB reference rates of {date}.",
        "warn.year": "⚠️ These are {year} rates; {current} figures may differ.",
        "warn.unchecked": "⚠️ Official figures last checked {date}.",
        "warn.mismatch": (
            '⚠️ Deel\'s guide says {label}: {deel}; officially from {since}: {official} (<a href="{url}">source</a>).'
        ),
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
        "err.stale_button": "That button belongs to an old message. Send the query again.",
        "usage.cost": "Usage: <code>/cost Bulgaria 60000 EUR</code>",
        "usage.plan": "Usage: <code>/plan Germany 80000 5 12</code> (country, salary, people, months)",
        "usage.compare": "Usage: <code>/compare Germany Poland 60000</code>",
        "usage.sources": "Usage: <code>/sources Spain</code>",
        "usage.free": "Try <code>Germany 80k</code> or /help.",
        "stats": "<b>Since start</b> ({since})\n{lines}",
    },
    "uk": {
        "lang.prompt": "🌐 Choose your language · Оберіть мову · Выберите язык",
        "lang.set": "Мова: українська. Змінити будь-коли: /lang.",
        "start": (
            "👋 <b>Hire-or-Entity Advisor</b> <i>(неофіційний)</i>\n\n"
            "Напишіть країну, річну зарплату брутто й розмір команди — покажу повну вартість "
            "для роботодавця, EOR проти власної юрособи і коли юрособа почне окуповуватися.\n\n"
            "Спробуйте: <code>Germany 80k 5 people</code>\n\n"
            "{countries}\n/help — усі команди"
        ),
        "help": (
            "<b>Команди</b>\n"
            "/cost <code>країна зарплата [валюта]</code> — вартість роботодавця з розбивкою\n"
            "/plan <code>країна зарплата люди [місяці]</code> — EOR проти юрособи, точка беззбитковості\n"
            "/compare <code>країна1 країна2 зарплата</code> — дві країни поруч\n"
            "/sources <code>країна</code> — звідки кожна цифра\n"
            "/lang — змінити мову\n\n"
            "Або просто напишіть: <code>Болгарія 60000 EUR</code>, <code>Іспанія 50k 3 особи 24 місяці</code>, "
            "<code>Німеччина vs Польща 70k</code>.\n"
            "Зарплата — <b>річна брутто</b>; для місячної додайте <code>/mo</code>.\n\n"
            "{countries}\n\n"
            "<i>Неофіційно, лише оцінки, не юридична й не податкова консультація.</i>"
        ),
        "countries": "Країни: {list}",
        "cost.header": "{flag} <b>{country}</b> · {salary} брутто на рік",
        "cost.monthly_input": "{monthly} на місяць × 12",
        "cost.converted": "≈ {amount} за курсом ЄЦБ на {date}",
        "cost.total": "Вартість для роботодавця: <b>{annual}</b> на рік · {monthly} на місяць",
        "cost.burden": "Понад зарплату: +{amount} на рік ({rate})",
        "cost.capped": "стеля",
        "cost.footer": (
            "<i>Ставки {year} року, діють з {since}. Рядки розрахункового листа округлені до "
            "цента, показано в цілих одиницях.</i>"
        ),
        "cost.estimate_note": "<i>~ типова ставка, залежить від роботодавця.</i>",
        "cost.below_min_wage": (
            "⚠️ Це нижче мінімальної зарплати {year} року ({minimum} на рік). Я чекаю <b>річну</b> "
            "зарплату; для місячної напишіть <code>{example}</code>."
        ),
        "plan.header": "{flag} <b>{country}</b> · {team} × {salary} на рік · {months}",
        "plan.eor": "<b>EOR ({provider})</b>: {total}",
        "plan.eor_detail": "комісія {fee} за особу на місяць",
        "plan.entity": "<b>Власна юрособа</b>: {total}",
        "plan.entity_detail": "відкриття {setup} + {fixed} на місяць + {per_employee} за особу на місяць",
        "plan.same": "Зарплата + внески, однаково в обох варіантах: {amount}",
        "plan.eor_cheaper": "💡 Для {team} на {months} EOR дешевший на ~{diff}.",
        "plan.entity_cheaper": "💡 Для {team} на {months} власна юрособа дешевша на ~{diff}.",
        "plan.even": "💡 Для {team} на {months} обидва варіанти коштують приблизно однаково.",
        "plan.pays_off_people": "Юрособа окуповується від {team} (на {months}).",
        "plan.pays_off_months": "Для {team} вона окупиться через {months}.",
        "plan.never_months": "Для {team} вона не окупиться: фіксовані витрати з'їдають економію.",
        "plan.never_people": "За таких цін юрособа не окуповується.",
        "plan.note": (
            "<i>Лише прямі витрати, кожна з джерелом (/sources). Не враховано: тижні на відкриття юрособи, "
            "час вашої команди і комплаєнс-ризик, який EOR бере на себе.</i>"
        ),
        "compare.header": "<b>{a} vs {b}</b> · {salary} брутто на рік",
        "compare.row": "{flag} <b>{country}</b>: {total} на рік · +{rate}",
        "compare.row_local": "у {currency}: {total}",
        "compare.row_eor": "EOR {fee} на місяць · юрособа від {team} (12 міс.)",
        "compare.row_never": "EOR {fee} на місяць · юрособа не окуповується",
        "compare.cheaper": "💡 У країні {country} наймати дешевше на ~{diff} на рік (на {rate} менше).",
        "compare.fx": "<i>Перераховано за курсами ЄЦБ на {date}.</i>",
        "sources.header": "{flag} <b>{country}: джерела</b>",
        "sources.rates": "<b>Ставки {year}</b>, діють з {since} · перевірено {checked}",
        "sources.entity": "<b>Власна юрособа</b> (оцінки)",
        "sources.capital": "Статутний капітал {amount}: лишається у компанії, це не витрата",
        "sources.eor": '<b>Ціна EOR</b>: {provider} від {fee} на місяць · <a href="{url}">прайс</a>, перевірено {checked}',
        "sources.guide": '<b>Гайд Deel</b> · <a href="{url}">сторінка</a>, перевірено {checked}',
        "sources.guide_ok": "✅ {label}: {value}",
        "sources.guide_bad": "⚠️ {label}: у Deel {deel}, офіційно {official}",
        "sources.fx": "Курси: довідкові курси ЄЦБ на {date}.",
        "warn.year": "⚠️ Це ставки {year} року; у {current} цифри можуть відрізнятися.",
        "warn.unchecked": "⚠️ Офіційні цифри востаннє перевірено {date}.",
        "warn.mismatch": (
            '⚠️ У гайді Deel {label}: {deel}; офіційно з {since}: {official} (<a href="{url}">джерело</a>).'
        ),
        "warn.fx_old": "⚠️ Курси валют станом на {date}.",
        "btn.compare": "🔁 Порівняти з іншою країною",
        "btn.plan": "👥 Порахувати на N осіб",
        "btn.sources": "📚 Джерела",
        "btn.months": "{n} міс.",
        "pick.country": "З якою країною порівняти {country}?",
        "pick.people": "Скільки людей?",
        "err.empty": "Надішліть країну й річну зарплату, наприклад <code>Germany 80k</code>.",
        "err.no_country": "Яка країна? {countries}",
        "err.no_salary": "Потрібна ще річна зарплата брутто, наприклад <code>{example}</code>.",
        "err.unknown_word": "Не знаю, що таке «{word}».",
        "err.unknown_word_suggest": "Не знаю, що таке «{word}». Можливо, <b>{suggestion}</b>?",
        "err.unknown_currency": "Для {currency} немає курсу ЄЦБ. Використайте EUR, USD, GBP, PLN чи іншу валюту ЄЦБ.",
        "err.salary_too_low": "Замало для річної зарплати (мінімум {minimum}). Місячна? Додайте <code>/mo</code>.",
        "err.salary_too_high": "Зарплата понад {maximum} — схоже на помилку.",
        "err.people_range": "Розмір команди — від 1 до {maximum}.",
        "err.months_range": "Горизонт — від 1 до {maximum} місяців.",
        "err.need_two_countries": "Назвіть дві країни: <code>/compare Germany Poland 60000</code>.",
        "err.too_many_countries": "Тут одна країна; щоб порівняти дві, є /compare.",
        "err.same_country": "Це та сама країна — оберіть дві різні.",
        "err.unexpected": "Не зрозумів «{word}».",
        "err.stale_button": "Ця кнопка зі старого повідомлення. Надішліть запит ще раз.",
        "usage.cost": "Приклад: <code>/cost Bulgaria 60000 EUR</code>",
        "usage.plan": "Приклад: <code>/plan Germany 80000 5 12</code> (країна, зарплата, люди, місяці)",
        "usage.compare": "Приклад: <code>/compare Germany Poland 60000</code>",
        "usage.sources": "Приклад: <code>/sources Spain</code>",
        "usage.free": "Спробуйте <code>Germany 80k</code> або /help.",
        "stats": "<b>Від запуску</b> ({since})\n{lines}",
    },
    "ru": {
        "lang.prompt": "🌐 Choose your language · Оберіть мову · Выберите язык",
        "lang.set": "Язык: русский. Сменить в любой момент: /lang.",
        "start": (
            "👋 <b>Hire-or-Entity Advisor</b> <i>(неофициальный)</i>\n\n"
            "Напишите страну, годовую зарплату брутто и размер команды — покажу полную стоимость "
            "для работодателя, EOR против своего юрлица и когда юрлицо начнёт окупаться.\n\n"
            "Попробуйте: <code>Germany 80k 5 people</code>\n\n"
            "{countries}\n/help — все команды"
        ),
        "help": (
            "<b>Команды</b>\n"
            "/cost <code>страна зарплата [валюта]</code> — стоимость работодателя с разбивкой\n"
            "/plan <code>страна зарплата люди [месяцы]</code> — EOR против юрлица, точка безубыточности\n"
            "/compare <code>страна1 страна2 зарплата</code> — две страны рядом\n"
            "/sources <code>страна</code> — откуда каждая цифра\n"
            "/lang — сменить язык\n\n"
            "Или просто напишите: <code>Болгария 60000 EUR</code>, <code>Испания 50k 3 человека 24 месяца</code>, "
            "<code>Германия vs Польша 70k</code>.\n"
            "Зарплата — <b>годовая брутто</b>; для месячной добавьте <code>/mo</code>.\n\n"
            "{countries}\n\n"
            "<i>Неофициально, только оценки, не юридическая и не налоговая консультация.</i>"
        ),
        "countries": "Страны: {list}",
        "cost.header": "{flag} <b>{country}</b> · {salary} брутто в год",
        "cost.monthly_input": "{monthly} в месяц × 12",
        "cost.converted": "≈ {amount} по курсу ЕЦБ на {date}",
        "cost.total": "Стоимость для работодателя: <b>{annual}</b> в год · {monthly} в месяц",
        "cost.burden": "Сверх зарплаты: +{amount} в год ({rate})",
        "cost.capped": "потолок",
        "cost.footer": (
            "<i>Ставки {year} года, действуют с {since}. Строки расчётного листа округлены до "
            "цента, показано в целых единицах.</i>"
        ),
        "cost.estimate_note": "<i>~ типичная ставка, зависит от работодателя.</i>",
        "cost.below_min_wage": (
            "⚠️ Это ниже минимальной зарплаты {year} года ({minimum} в год). Я жду <b>годовую</b> "
            "зарплату; для месячной напишите <code>{example}</code>."
        ),
        "plan.header": "{flag} <b>{country}</b> · {team} × {salary} в год · {months}",
        "plan.eor": "<b>EOR ({provider})</b>: {total}",
        "plan.eor_detail": "комиссия {fee} за человека в месяц",
        "plan.entity": "<b>Своё юрлицо</b>: {total}",
        "plan.entity_detail": "открытие {setup} + {fixed} в месяц + {per_employee} за человека в месяц",
        "plan.same": "Зарплата + взносы, одинаково в обоих вариантах: {amount}",
        "plan.eor_cheaper": "💡 Для {team} на {months} EOR дешевле на ~{diff}.",
        "plan.entity_cheaper": "💡 Для {team} на {months} своё юрлицо дешевле на ~{diff}.",
        "plan.even": "💡 Для {team} на {months} оба варианта стоят примерно одинаково.",
        "plan.pays_off_people": "Юрлицо окупается с {team} (на {months}).",
        "plan.pays_off_months": "Для {team} оно окупится через {months}.",
        "plan.never_months": "Для {team} оно не окупится: фиксированные расходы съедают экономию.",
        "plan.never_people": "При таких ценах юрлицо не окупается.",
        "plan.note": (
            "<i>Только прямые расходы, каждая с источником (/sources). Не учтены: недели на открытие юрлица, "
            "время вашей команды и комплаенс-риск, который EOR берёт на себя.</i>"
        ),
        "compare.header": "<b>{a} vs {b}</b> · {salary} брутто в год",
        "compare.row": "{flag} <b>{country}</b>: {total} в год · +{rate}",
        "compare.row_local": "в {currency}: {total}",
        "compare.row_eor": "EOR {fee} в месяц · юрлицо с {team} (12 мес.)",
        "compare.row_never": "EOR {fee} в месяц · юрлицо не окупается",
        "compare.cheaper": "💡 В стране {country} нанимать дешевле на ~{diff} в год (на {rate} меньше).",
        "compare.fx": "<i>Пересчитано по курсам ЕЦБ на {date}.</i>",
        "sources.header": "{flag} <b>{country}: источники</b>",
        "sources.rates": "<b>Ставки {year}</b>, действуют с {since} · проверено {checked}",
        "sources.entity": "<b>Своё юрлицо</b> (оценки)",
        "sources.capital": "Уставный капитал {amount}: остаётся у компании, это не расход",
        "sources.eor": '<b>Цена EOR</b>: {provider} от {fee} в месяц · <a href="{url}">прайс</a>, проверено {checked}',
        "sources.guide": '<b>Гайд Deel</b> · <a href="{url}">страница</a>, проверено {checked}',
        "sources.guide_ok": "✅ {label}: {value}",
        "sources.guide_bad": "⚠️ {label}: у Deel {deel}, официально {official}",
        "sources.fx": "Курсы: справочные курсы ЕЦБ на {date}.",
        "warn.year": "⚠️ Это ставки {year} года; в {current} цифры могут отличаться.",
        "warn.unchecked": "⚠️ Официальные цифры последний раз проверены {date}.",
        "warn.mismatch": (
            '⚠️ В гайде Deel {label}: {deel}; официально с {since}: {official} (<a href="{url}">источник</a>).'
        ),
        "warn.fx_old": "⚠️ Курсы валют на {date}.",
        "btn.compare": "🔁 Сравнить с другой страной",
        "btn.plan": "👥 Посчитать на N человек",
        "btn.sources": "📚 Источники",
        "btn.months": "{n} мес.",
        "pick.country": "С какой страной сравнить {country}?",
        "pick.people": "Сколько человек?",
        "err.empty": "Пришлите страну и годовую зарплату, например <code>Germany 80k</code>.",
        "err.no_country": "Какая страна? {countries}",
        "err.no_salary": "Нужна ещё годовая зарплата брутто, например <code>{example}</code>.",
        "err.unknown_word": "Не знаю, что такое «{word}».",
        "err.unknown_word_suggest": "Не знаю, что такое «{word}». Может быть, <b>{suggestion}</b>?",
        "err.unknown_currency": "Для {currency} нет курса ЕЦБ. Используйте EUR, USD, GBP, PLN или другую валюту ЕЦБ.",
        "err.salary_too_low": "Маловато для годовой зарплаты (минимум {minimum}). Месячная? Добавьте <code>/mo</code>.",
        "err.salary_too_high": "Зарплата больше {maximum} — похоже на опечатку.",
        "err.people_range": "Размер команды — от 1 до {maximum}.",
        "err.months_range": "Горизонт — от 1 до {maximum} месяцев.",
        "err.need_two_countries": "Назовите две страны: <code>/compare Germany Poland 60000</code>.",
        "err.too_many_countries": "Здесь одна страна; чтобы сравнить две, есть /compare.",
        "err.same_country": "Это одна и та же страна — выберите две разные.",
        "err.unexpected": "Не понял «{word}».",
        "err.stale_button": "Эта кнопка из старого сообщения. Пришлите запрос ещё раз.",
        "usage.cost": "Пример: <code>/cost Bulgaria 60000 EUR</code>",
        "usage.plan": "Пример: <code>/plan Germany 80000 5 12</code> (страна, зарплата, люди, месяцы)",
        "usage.compare": "Пример: <code>/compare Germany Poland 60000</code>",
        "usage.sources": "Пример: <code>/sources Spain</code>",
        "usage.free": "Попробуйте <code>Germany 80k</code> или /help.",
        "stats": "<b>С запуска</b> ({since})\n{lines}",
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
    "uk": {
        "minimum_wage": "мінімальна зарплата",
        "pension_rate": "пенсійний внесок",
        "unemployment_rate": "внесок на безробіття",
        "health_rate": "внесок на медстрахування",
        "care_rate": "внесок на догляд",
        "insolvency_rate": "збір на випадок банкрутства",
        "disability_rate": "внесок з інвалідності",
        "labour_fund_rate": "внесок до Фонду праці",
        "fgsp_rate": "внесок до фонду гарантованих виплат",
        "upf_rate": "внесок до універсального пенсійного фонду",
        "sickness_rate": "внесок з хвороби та материнства",
        "common_contingencies_rate": "внесок на загальні ризики",
        "mei_rate": "внесок MEI",
        "training_rate": "внесок на профнавчання",
        "fogasa_rate": "внесок FOGASA",
        "workplace_pension_rate": "мінімальний пенсійний внесок",
        "pension_cap": "стеля пенсійних внесків",
        "health_cap": "стеля внесків на медстрахування",
        "max_insurable_income": "максимальний страховий дохід",
        "nic_rate": "ставка NIC роботодавця",
        "nic_threshold": "поріг NIC",
        "employer_total_rate": "загальні внески роботодавця",
    },
    "ru": {
        "minimum_wage": "минимальная зарплата",
        "pension_rate": "пенсионный взнос",
        "unemployment_rate": "взнос на безработицу",
        "health_rate": "взнос на медстрахование",
        "care_rate": "взнос на уход",
        "insolvency_rate": "сбор на случай банкротства",
        "disability_rate": "взнос по инвалидности",
        "labour_fund_rate": "взнос в Фонд труда",
        "fgsp_rate": "взнос в фонд гарантированных выплат",
        "upf_rate": "взнос в универсальный пенсионный фонд",
        "sickness_rate": "взнос по болезни и материнству",
        "common_contingencies_rate": "взнос на общие риски",
        "mei_rate": "взнос MEI",
        "training_rate": "взнос на профобучение",
        "fogasa_rate": "взнос FOGASA",
        "workplace_pension_rate": "минимальный пенсионный взнос",
        "pension_cap": "потолок пенсионных взносов",
        "health_cap": "потолок взносов на медстрахование",
        "max_insurable_income": "максимальный страховой доход",
        "nic_rate": "ставка NIC работодателя",
        "nic_threshold": "порог NIC",
        "employer_total_rate": "общие взносы работодателя",
    },
}

PERIODS: Final[dict[Lang, dict[str, str]]] = {
    "en": {"hour": "/h", "month": "/mo", "year": "/yr"},
    "uk": {"hour": "/год", "month": "/міс", "year": "/рік"},
    "ru": {"hour": "/ч", "month": "/мес", "year": "/год"},
}

# Contribution names by the `id` in the country files. English falls back to the file's own
# `name`; a test makes sure every bundled id has a Ukrainian and a Russian name.
CONTRIBUTIONS: Final[dict[Lang, dict[str, str]]] = {
    "en": {},
    "uk": {
        "pension": "Пенсійне", "unemployment": "Безробіття", "health": "Медстрахування", "care": "Догляд (Pflege)",
        "insolvency": "Збір на банкрутство", "u1": "Збір U1 (лікарняні)", "u2": "Збір U2 (материнство)",
        "accident": "Нещасні випадки", "nic": "National Insurance", "workplace_pension": "Пенсія (мінімум)",
        "common_contingencies": "Загальні ризики", "mei": "MEI", "training": "Профнавчання", "fogasa": "FOGASA",
        "solidarity_1": "Солідарний, до +10%", "solidarity_2": "Солідарний, +10–50%",
        "solidarity_3": "Солідарний, понад +50%", "disability": "Інвалідність", "labour_fund": "Фонд праці + FS",
        "fgsp": "FGŚP", "upf": "Універсальний пенсійний фонд", "sickness": "Хвороба й материнство",
    },
    "ru": {
        "pension": "Пенсионное", "unemployment": "Безработица", "health": "Медстрахование", "care": "Уход (Pflege)",
        "insolvency": "Сбор на банкротство", "u1": "Сбор U1 (больничные)", "u2": "Сбор U2 (материнство)",
        "accident": "Несчастные случаи", "nic": "National Insurance", "workplace_pension": "Пенсия (минимум)",
        "common_contingencies": "Общие риски", "mei": "MEI", "training": "Профобучение", "fogasa": "FOGASA",
        "solidarity_1": "Солидарный, до +10%", "solidarity_2": "Солидарный, +10–50%",
        "solidarity_3": "Солидарный, свыше +50%", "disability": "Инвалидность", "labour_fund": "Фонд труда + FS",
        "fgsp": "FGŚP", "upf": "Универсальный пенсионный фонд", "sickness": "Болезнь и материнство",
    },
}  # fmt: skip

COUNTRY_NAMES: Final[dict[Lang, dict[str, str]]] = {
    "en": {},
    "uk": {"DE": "Німеччина", "GB": "Велика Британія", "ES": "Іспанія", "PL": "Польща", "BG": "Болгарія"},
    "ru": {"DE": "Германия", "GB": "Великобритания", "ES": "Испания", "PL": "Польша", "BG": "Болгария"},
}


def t(lang: Lang, key: str, **params: object) -> str:
    template = MESSAGES[lang].get(key) or MESSAGES[DEFAULT][key]
    return template.format(**params) if params else template
