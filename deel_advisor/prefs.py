"""The one thing the bot remembers about anybody: which language they picked.

Not the Telegram id itself — an HMAC of it under a key that never leaves the data directory,
so the table cannot be joined back to accounts without that key. Nothing else is stored: no
names, no usernames, no queries.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path

from deel_advisor.i18n import LANGS, Lang

_SCHEMA = "CREATE TABLE IF NOT EXISTS lang (who TEXT PRIMARY KEY, lang TEXT NOT NULL)"


def _load_key(path: Path) -> bytes:
    try:
        return bytes.fromhex(path.read_text().strip())
    except FileNotFoundError:
        key = secrets.token_bytes(32)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(mode=0o600)
        path.write_text(key.hex())
        return key


class LanguageStore:
    def __init__(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        self._key = _load_key(data_dir / "prefs.key")
        self._db = data_dir / "prefs.db"
        with self._connect() as db:
            db.execute(_SCHEMA)
        # Read-through cache: the language is looked up on every update.
        self._cache: dict[str, Lang] = {}

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db, timeout=5)

    def _who(self, user_id: int) -> str:
        return hmac.new(self._key, str(user_id).encode(), hashlib.sha256).hexdigest()

    def _get(self, who: str) -> Lang | None:
        with self._connect() as db:
            row = db.execute("SELECT lang FROM lang WHERE who = ?", (who,)).fetchone()
        value = row[0] if row else None
        return next((lang for lang in LANGS if lang == value), None)

    def _set(self, who: str, lang: Lang) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO lang (who, lang) VALUES (?, ?) ON CONFLICT(who) DO UPDATE SET lang = excluded.lang",
                (who, lang),
            )

    async def get(self, user_id: int) -> Lang | None:
        who = self._who(user_id)
        if who in self._cache:
            return self._cache[who]
        lang = await asyncio.to_thread(self._get, who)
        if lang is not None:
            self._cache[who] = lang
        return lang

    async def set(self, user_id: int, lang: Lang) -> None:
        who = self._who(user_id)
        await asyncio.to_thread(self._set, who, lang)
        self._cache[who] = lang
