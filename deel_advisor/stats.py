"""Command counters: how much each command is used, and nothing about who used it."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime


class Stats:
    def __init__(self) -> None:
        self.since = datetime.now(UTC)
        self.counts: Counter[str] = Counter()

    def hit(self, name: str) -> None:
        self.counts[name] += 1

    def lines(self) -> list[str]:
        return [f"{name}: {count}" for name, count in sorted(self.counts.items())]
