import string

import pytest

from deel_advisor import i18n
from deel_advisor.catalog import Catalog
from deel_advisor.i18n import LANGS, MESSAGES, people, people_gen, pick_lang, plural, t


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


@pytest.mark.parametrize("table", [i18n.FIGURES, i18n.PERIODS], ids=["figures", "periods"])
def test_label_tables_are_complete(table: dict[str, dict[str, str]]) -> None:
    for lang in LANGS:
        assert table[lang].keys() == table["en"].keys(), lang


def test_every_bundled_name_is_translated(real_catalog: Catalog) -> None:
    # English falls back to the names in the data files; Ukrainian and Russian must not.
    for country in real_catalog.countries:
        for lang in ("uk", "ru"):
            assert country.code in i18n.COUNTRY_NAMES[lang], (lang, country.code)
            for c in country.contributions:
                assert c.id in i18n.CONTRIBUTIONS[lang], (lang, country.code, c.id)


@pytest.mark.parametrize(
    ("code", "lang"),
    [("uk", "uk"), ("uk-UA", "uk"), ("ru", "ru"), ("be", "ru"), ("en-GB", "en"), ("de", "en"), (None, "en")],
)
def test_pick_lang(code: str | None, lang: str) -> None:
    assert pick_lang(code) == lang


@pytest.mark.parametrize(
    ("n", "ru"),
    [(1, "1 человек"), (2, "2 человека"), (4, "4 человека"), (5, "5 человек"), (11, "11 человек"),
     (12, "12 человек"), (21, "21 человек"), (22, "22 человека"), (111, "111 человек")],
)  # fmt: skip
def test_russian_plural(n: int, ru: str) -> None:
    assert people("ru", n) == ru


def test_genitive_after_for() -> None:
    assert people_gen("ru", 1) == "1 человека"
    assert people_gen("ru", 3) == "3 человек"
    assert people_gen("uk", 1) == "1 особи"
    assert people_gen("uk", 9) == "9 осіб"
    assert people_gen("en", 1) == "1 person"
    assert people_gen("en", 9) == "9 people"


def test_ukrainian_months() -> None:
    assert plural("uk", 1, ("місяць", "місяці", "місяців")) == "місяць"
    assert i18n.months("uk", 3) == "3 місяці"
    assert i18n.months("uk", 12) == "12 місяців"


def test_t_formats() -> None:
    assert "Germany" in t("en", "pick.country", country="Germany")
    assert t("en", "btn.sources") == "📚 Sources"
