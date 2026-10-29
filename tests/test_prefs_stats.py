from pathlib import Path

import pytest

from deel_advisor.prefs import LanguageStore
from deel_advisor.stats import Stats


async def test_language_round_trip_and_persistence(tmp_path: Path) -> None:
    store = LanguageStore(tmp_path)
    assert await store.get(42) is None
    await store.set(42, "uk")
    await store.set(42, "ru")
    assert await store.get(42) == "ru"
    # A new process reads the same key file and the same table.
    assert await LanguageStore(tmp_path).get(42) == "ru"


async def test_telegram_id_is_not_stored(tmp_path: Path) -> None:
    store = LanguageStore(tmp_path)
    await store.set(123456789, "en")
    raw = (tmp_path / "prefs.db").read_bytes()
    assert b"123456789" not in raw
    assert (tmp_path / "prefs.key").stat().st_mode & 0o077 == 0


async def test_different_key_means_unlinkable(tmp_path: Path) -> None:
    await LanguageStore(tmp_path / "a").set(7, "uk")
    assert await LanguageStore(tmp_path / "b").get(7) is None


async def test_unknown_stored_value_is_ignored(tmp_path: Path) -> None:
    import sqlite3

    store = LanguageStore(tmp_path)
    await store.set(1, "en")
    with sqlite3.connect(tmp_path / "prefs.db") as db:
        db.execute("UPDATE lang SET lang = 'xx'")
    assert await LanguageStore(tmp_path).get(1) is None


def test_stats_counts_without_identities() -> None:
    stats = Stats()
    stats.hit("cost")
    stats.hit("cost")
    stats.hit("plan")
    assert stats.lines() == ["cost: 2", "plan: 1"]


async def test_malformed_key_is_replaced(tmp_path: Path) -> None:
    (tmp_path / "prefs.key").write_text("")  # what a crash mid-write used to leave
    store = LanguageStore(tmp_path)
    await store.set(1, "uk")
    assert len(bytes.fromhex((tmp_path / "prefs.key").read_text())) == 32
    (tmp_path / "prefs.key").write_text("zz")
    assert await LanguageStore(tmp_path).get(1) is None  # new key: old rows are unreachable


def test_empty_owner_id_means_unset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from deel_advisor.config import Settings

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("BOT_TOKEN=1:x\nOWNER_ID=\nSERVER_PASSWORD=unrelated\n")
    settings = Settings()
    assert settings.owner_id is None
    assert settings.bot_token.get_secret_value() == "1:x"
