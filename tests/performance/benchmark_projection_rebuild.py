"""Reproducible one-million-event M2 projection rebuild benchmark."""

from __future__ import annotations

import argparse
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter

from apex.journal import JournalStore
from apex.projections import ProjectionService


class ReplayOnlyClock:
    def now(self) -> datetime:
        raise AssertionError("projection replay must not read the wall clock")


@dataclass(frozen=True)
class BenchmarkResult:
    events: int
    elapsed_seconds: float
    max_seconds: float


def run_benchmark(events: int, max_seconds: float) -> BenchmarkResult:
    if events < 1:
        raise ValueError("events must be positive")
    if max_seconds <= 0:
        raise ValueError("max_seconds must be positive")
    with tempfile.TemporaryDirectory(
        prefix=".apex-m2-volume-",
        dir=Path.cwd(),
    ) as directory:
        path = Path(directory) / "journal.db"
        _seed_synthetic_journal(path, events)
        started = perf_counter()
        with JournalStore(path, ReplayOnlyClock()) as journal:
            reports = ProjectionService(journal).rebuild_all()
        elapsed = perf_counter() - started
    if any(report.processed_events != events for report in reports):
        raise AssertionError("a projection did not process the complete synthetic Journal")
    if elapsed > max_seconds:
        raise AssertionError(
            f"{events:,}-event rebuild took {elapsed:.3f}s; threshold is {max_seconds:.3f}s"
        )
    return BenchmarkResult(events, elapsed, max_seconds)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=1_000_000)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    arguments = parser.parse_args()
    result = run_benchmark(arguments.events, arguments.max_seconds)
    print(
        f"events={result.events} elapsed_seconds={result.elapsed_seconds:.3f} "
        f"max_seconds={result.max_seconds:.3f}"
    )
    return 0


def _seed_synthetic_journal(path: Path, events: int) -> None:
    with JournalStore(path, ReplayOnlyClock()):
        pass
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA synchronous = OFF")
        connection.execute(
            """
            WITH RECURSIVE counter(seq) AS (
                VALUES (1)
                UNION ALL
                SELECT seq + 1 FROM counter WHERE seq < ?
            )
            INSERT INTO events (
                event_id, seq, ts, actor, type, schema_version,
                session_id, turn_id, caused_by, payload, prev_hash, hash
            )
            SELECT
                '0000000000' || printf('%016X', seq),
                seq,
                '2026-01-01T00:00:00.000000Z',
                'system',
                'admin.action',
                1,
                NULL,
                NULL,
                NULL,
                '{}',
                printf('%064d', 0),
                printf('%064d', 0)
            FROM counter
            """,
            (events,),
        )
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
