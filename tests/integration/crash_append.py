"""Subprocess helper that terminates at a requested append stage."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from apex.journal.store import AppendStage, JournalStore


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)


class ProcessTerminator:
    def __init__(self, target: str) -> None:
        self._target = target

    def reached(self, stage: AppendStage) -> None:
        if stage == self._target:
            os._exit(71)


def main() -> int:
    path = Path(sys.argv[1])
    target = sys.argv[2]
    observer = None if target == "complete" else ProcessTerminator(target)
    with JournalStore(path, FixedClock(), append_observer=observer) as store:
        store.append("user", "user.message", {"text": "crash test"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
