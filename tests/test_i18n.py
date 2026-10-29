import re
import string

import pytest

from deel_advisor import i18n
from deel_advisor.catalog import Catalog
from deel_advisor.i18n import LANGS, MESSAGES, category, months, months_after, people, people_for, pick_lang, t


def _fields(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


@pytest.mark.parametrize("lang", LANGS)
def test_every_key_in_every_language(lang: str) -> None:
    assert MESSAGES[lang].keys() == MESSAGES["en"].keys()  # type: ignore[index]


@pytest.mark.parametrize("key", sorted(MESSAGES["en"]))
def test_placeholders_match(key: str) -> None:
    expected = _fields(MESSAGES["en"][key])
    for lang in LANGS:
        assert _fields(MESSAGES[lang][key]) == expected, (lang, key)


@pytest.mark.parametrize("lang", LANGS)
def test_html_in_copy_is_balanced(lang: str) -> None:
    # Telegram rejects the whole message on one unclosed tag, so every template must balance.
    for key, template in MESSAGES[lang].items():  # type: ignore[index]
        for tag in ("b", "i", "code", "a"):
            opened = len(re.findall(rf"<{tag}[ >]", template))
            assert opened == template.count(f"</{tag}>"), (lang, key, tag)


@pytest.mark.parametrize("lang", [lang for lang in LANGS if lang != "en"])
def test_translations_are_not_english_copies(lang: str) -> None:
    same = {k for k, v in MESSAGES[lang].items() if v == MESSAGES["en"][k]}  # type: ignore[index]
    # Strings that are the same in every language (a brand, a symbol, a shared prompt) or
    # happen to be spelled the same in German ("in EUR: …").
    allowed = {"lang.prompt", "plan.eor", "sources.guide_ok", "compare.row_local"}
    assert same <= allowed, same - allowed


@pytest.mark.parametrize("table", [i18n.FIGURES, i18n.PERIODS], ids=["figures", "periods"])
def test_label_tables_are_complete(table: dict[str, dict[str, str]]) -> None:
    for lang in LANGS:
        assert table[lang].keys() == table["en"].keys(), lang


def test_every_bundled_name_is_translated(real_catalog: Catalog) -> None:
    # English falls back to the names in the data files; the other languages must not.
    for country in real_catalog.countries:
        for lang in LANGS[1:]:
            assert country.code in i18n.COUNTRY_NAMES[lang], (lang, country.code)
            for c in country.contributions:
                assert c.id in i18n.CONTRIBUTIONS[lang], (lang, country.code, c.id)


def test_no_unsupported_language_left_anywhere() -> None:
    assert set(LANGS) == {"en", "de", "es", "pl", "bg"}
    for table in (MESSAGES, i18n.FIGURES, i18n.PERIODS, i18n.CONTRIBUTIONS, i18n.COUNTRY_NAMES, i18n.LANG_NAMES):
        assert set(table) == set(LANGS)


@pytest.mark.parametrize(
    ("code", "lang"),
    [("de", "de"), ("de-AT", "de"), ("es-419", "es"), ("pl", "pl"), ("bg", "bg"), ("EN-gb", "en"),
     ("fr", "en"), ("it", "en"), ("pt-BR", "en"), ("", "en"), (None, "en"), ("d", "en"), ("deu", "en")],
)  # fmt: skip
def test_pick_lang(code: str | None, lang: str) -> None:
    assert pick_lang(code) == lang


@pytest.mark.parametrize(
    ("n", "expected"),
    [(0, "many"), (1, "one"), (2, "few"), (4, "few"), (5, "many"), (11, "many"), (12, "many"), (14, "many"),
     (21, "many"), (22, "few"), (24, "few"), (25, "many"), (102, "few"), (112, "many"), (1000, "many")],
)  # fmt: skip
def test_polish_plural_categories(n: int, expected: str) -> None:
    assert category("pl", n) == expected


@pytest.mark.parametrize("lang", ["en", "de", "es", "bg"])
def test_two_form_languages_never_say_few(lang: str) -> None:
    assert {category(lang, n) for n in range(200)} == {"one", "many"}  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("lang", "n", "nominative", "after_for"),
    [
        ("en", 1, "1 person", "1 person"), ("en", 3, "3 people", "3 people"),
        ("de", 1, "1 Person", "1 Person"), ("de", 5, "5 Personen", "5 Personen"),
        ("es", 1, "1 persona", "1 persona"), ("es", 2, "2 personas", "2 personas"),
        ("pl", 1, "1 osoba", "1 osoby"), ("pl", 3, "3 osoby", "3 osób"), ("pl", 5, "5 osób", "5 osób"),
        ("pl", 22, "22 osoby", "22 osób"), ("bg", 1, "1 служител", "1 служител"),
        ("bg", 7, "7 служители", "7 служители"),
    ],
)  # fmt: skip
def test_people_forms(lang: str, n: int, nominative: str, after_for: str) -> None:
    assert people(lang, n) == nominative  # type: ignore[arg-type]
    assert people_for(lang, n) == after_for  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("lang", "n", "duration", "after"),
    [
        ("de", 1, "1 Monat", "1 Monat"), ("de", 2, "2 Monate", "2 Monaten"),
        ("pl", 1, "1 miesiąc", "1 miesiącu"), ("pl", 2, "2 miesiące", "2 miesiącach"),
        ("pl", 12, "12 miesięcy", "12 miesiącach"), ("pl", 24, "24 miesiące", "24 miesiącach"),
        ("es", 1, "1 mes", "1 mes"), ("es", 6, "6 meses", "6 meses"),
        ("bg", 1, "1 месец", "1 месец"), ("bg", 36, "36 месеца", "36 месеца"),
        ("en", 1, "1 month", "1 month"), ("en", 13, "13 months", "13 months"),
    ],
)  # fmt: skip
def test_month_forms(lang: str, n: int, duration: str, after: str) -> None:
    assert months(lang, n) == duration  # type: ignore[arg-type]
    assert months_after(lang, n) == after  # type: ignore[arg-type]


def test_t_formats_and_falls_back() -> None:
    assert t("de", "pick.country", country="Polen") == "Polen vergleichen mit:"
    assert t("en", "btn.sources") == "📚 Sources"


def test_t_missing_parameter_is_a_bug_not_a_silent_blank() -> None:
    with pytest.raises(KeyError):
        t("en", "pick.country", wrong="x")
