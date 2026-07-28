from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.journal import (
    GENESIS_HASH,
    InvalidEnvelopeError,
    JournalStore,
    JournalWriteError,
    PayloadSchemaError,
    UnregisteredEventTypeError,
)
from apex.journal.store import AppendStage


class SteppingClock:
    def __init__(self) -> None:
        self._next = datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        value = self._next
        self._next += timedelta(microseconds=1)
        return value


class InterruptAppend(RuntimeError):
    pass


class RaisingObserver:
    def __init__(self, target: AppendStage) -> None:
        self._target = target

    def reached(self, stage: AppendStage) -> None:
        if stage == self._target:
            raise InterruptAppend(stage)


def test_acceptance_1_unregistered_type_fails(tmp_path: Path) -> None:
    with JournalStore(tmp_path / "journal.db", SteppingClock()) as store:
        with pytest.raises(UnregisteredEventTypeError):
            store.append("system", "unknown.event", {})
        assert store.head() == (0, GENESIS_HASH)


def test_acceptance_2_payload_violating_registered_schema_fails(tmp_path: Path) -> None:
    with JournalStore(tmp_path / "journal.db", SteppingClock()) as store:
        with pytest.raises(PayloadSchemaError, match="expected object"):
            store.append("user", "user.message", ["not", "an", "object"])
        assert store.head() == (0, GENESIS_HASH)


def test_acceptance_3_sequences_are_dense_across_restarts(tmp_path: Path) -> None:
    path = tmp_path / "journal.db"
    observed: list[int] = []

    for index in range(5):
        with JournalStore(path, SteppingClock()) as store:
            observed.append(store.append("system", "admin.action", {"index": index}).seq)

    assert observed == [1, 2, 3, 4, 5]


def test_acceptance_4_application_connection_cannot_update_or_delete(tmp_path: Path) -> None:
    with JournalStore(tmp_path / "journal.db", SteppingClock()) as store:
        event = store.append("system", "admin.action", {"operation": "test"})

        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            store._connection.execute(
                "UPDATE events SET payload = '{}' WHERE seq = ?", (event.seq,)
            )
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            store._connection.execute("DELETE FROM events WHERE seq = ?", (event.seq,))

        assert tuple(store.read_range(0)) == (event,)


def test_acceptance_4_storage_triggers_reject_external_mutation(tmp_path: Path) -> None:
    path = tmp_path / "journal.db"
    with JournalStore(path, SteppingClock()) as store:
        store.append("system", "admin.action", {"operation": "test"})

        with sqlite3.connect(path) as connection:
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                connection.execute("UPDATE events SET payload = '{}' WHERE seq = 1")
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                connection.execute("DELETE FROM events WHERE seq = 1")


def test_acceptance_5_corruption_reports_exact_sequence(tmp_path: Path) -> None:
    path = tmp_path / "journal.db"
    with JournalStore(path, SteppingClock()) as store:
        store.append("system", "admin.action", {"text": "a"})
        store.append("system", "admin.action", {"text": "a"})
        store.append("system", "admin.action", {"text": "a"})

    with sqlite3.connect(path) as administrator:
        administrator.executescript(
            """
            DROP TRIGGER events_no_update;
            DROP TRIGGER events_no_delete;
            UPDATE events SET payload = replace(payload, '"a"', '"b"') WHERE seq = 2;
            """
        )

    with JournalStore(path, SteppingClock()) as store:
        report = store.verify_chain()

    assert report.valid is False
    assert report.divergence_seq == 2
    assert report.reason == "event hash mismatch"


@pytest.mark.parametrize("stage", ["transaction_started", "row_inserted"])
def test_acceptance_7_exception_interruption_rolls_back_atomically(
    tmp_path: Path, stage: AppendStage
) -> None:
    path = tmp_path / "journal.db"

    with JournalStore(
        path,
        SteppingClock(),
        append_observer=RaisingObserver(stage),
    ) as store:
        with pytest.raises(InterruptAppend):
            store.append("user", "user.message", {"text": "interrupted"})
        assert store.head() == (0, GENESIS_HASH)
        assert store.verify_chain().valid is True

    with JournalStore(path, SteppingClock()) as recovered:
        event = recovered.append("user", "user.message", {"text": "recovered"})
        assert event.seq == 1
        assert recovered.verify_chain().valid is True


@pytest.mark.parametrize("stage", ["transaction_started", "row_inserted"])
def test_acceptance_7_process_kill_leaves_no_partial_event(
    tmp_path: Path, stage: AppendStage
) -> None:
    path = tmp_path / "journal.db"
    helper = Path(__file__).with_name("crash_append.py")

    result = subprocess.run(
        [sys.executable, str(helper), str(path), stage],
        check=False,
        timeout=10,
    )

    assert result.returncode == 71
    with JournalStore(path, SteppingClock()) as store:
        assert store.head() == (0, GENESIS_HASH)
        assert store.verify_chain().valid is True


def test_acceptance_7_completed_append_is_fully_present_after_process_exit(
    tmp_path: Path,
) -> None:
    path = tmp_path / "journal.db"
    helper = Path(__file__).with_name("crash_append.py")

    result = subprocess.run(
        [sys.executable, str(helper), str(path), "complete"],
        check=False,
        timeout=10,
    )

    assert result.returncode == 0
    with JournalStore(path, SteppingClock()) as store:
        assert store.head()[0] == 1
        assert store.verify_chain().valid is True


def test_acceptance_8_tool_result_causal_chain_reaches_user_message(tmp_path: Path) -> None:
    with JournalStore(tmp_path / "journal.db", SteppingClock()) as store:
        user = store.append("user", "user.message", {"text": "read it"})
        requested = store.append(
            "apex",
            "tool.requested",
            {"tool": "fs.read_file"},
            caused_by=user.event_id,
        )
        result = store.append(
            "system",
            "tool.result",
            {"content": "result"},
            caused_by=requested.event_id,
        )

        chain = store.walk_caused_by(result.event_id)

    assert [event.type for event in chain] == [
        "tool.result",
        "tool.requested",
        "user.message",
    ]
    assert chain[-1].event_id == user.event_id


def test_missing_causal_parent_is_rejected_atomically(tmp_path: Path) -> None:
    missing = "01KDVDNA000000000000000099"
    with JournalStore(tmp_path / "journal.db", SteppingClock()) as store:
        with pytest.raises(JournalWriteError):
            store.append("system", "tool.result", {}, caused_by=missing)
        assert store.head() == (0, GENESIS_HASH)


def test_replay_is_deterministic_and_does_not_read_wall_clock(tmp_path: Path) -> None:
    path = tmp_path / "journal.db"
    with JournalStore(path, SteppingClock()) as store:
        expected = tuple(
            store.append("system", "admin.action", {"index": index}) for index in range(20)
        )

    class ExplodingClock:
        def now(self) -> datetime:
            raise AssertionError("replay must not read the wall clock")

    with JournalStore(path, ExplodingClock()) as replay:
        first = tuple(replay.read_range(0))
        second = tuple(replay.read_range(0))

    assert first == expected
    assert second == expected


def test_read_range_filters_and_orders_events(tmp_path: Path) -> None:
    session_id = "01KDVDNA000000000000000010"
    turn_id = "01KDVDNA000000000000000011"
    with JournalStore(tmp_path / "journal.db", SteppingClock()) as store:
        store.append("system", "session.started", {}, session_id=session_id)
        selected = store.append(
            "user",
            "user.message",
            {"text": "hello"},
            session_id=session_id,
            turn_id=turn_id,
        )
        store.append("apex", "apex.message", {"text": "hi"}, session_id=session_id)

        events = tuple(
            store.read_range(
                1,
                3,
                types=("user.message",),
                session_id=session_id,
                turn_id=turn_id,
            )
        )

    assert events == (selected,)


def test_naive_clock_is_rejected_without_writing(tmp_path: Path) -> None:
    class NaiveClock:
        def now(self) -> datetime:
            return datetime(2026, 1, 1)

    with JournalStore(tmp_path / "journal.db", NaiveClock()) as store:
        with pytest.raises(InvalidEnvelopeError, match="aware"):
            store.append("system", "admin.action", {})
        assert store.head() == (0, GENESIS_HASH)
