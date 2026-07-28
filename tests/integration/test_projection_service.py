from __future__ import annotations

import queue
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.journal import Event, JournalStore, ProjectionSnapshotCorruptionError
from apex.projections import (
    PendingApprovalsProjection,
    PendingApprovalsState,
    ProjectionRunner,
    ProjectionService,
    UnknownProjectionError,
)

BUNDLE_ID = "01KDVDNA000000000000000020"
REQUEST_ONE = "01KDVDNA000000000000000010"
REQUEST_TWO = "01KDVDNA000000000000000011"
ARGS_HASH = "a" * 64


class SteppingClock:
    def __init__(self) -> None:
        self._next = datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        value = self._next
        self._next += timedelta(microseconds=1)
        return value


def _request_payload(request_id: str) -> object:
    return {
        "args_hash": ARGS_HASH,
        "bundle_id": BUNDLE_ID,
        "expires_at": "2026-01-02T00:00:00Z",
        "policy_version": 1,
        "request_id": request_id,
        "tool": "fs.write_file",
    }


def _challenge_payload(rule_id: str = "r-write") -> object:
    return {
        "bundle_id": BUNDLE_ID,
        "decision_id": "01KDVDNA000000000000000030",
        "policy_version": 1,
        "reasoning": "Needed for the requested operation.",
        "rule_id": rule_id,
    }


def test_acceptance_6_rebuilds_are_byte_identical(tmp_path: Path) -> None:
    path = tmp_path / "journal.db"
    with JournalStore(path, SteppingClock()) as journal:
        journal.append("system", "approval.requested", _request_payload(REQUEST_ONE))
        journal.append("apex", "policy.challenged", _challenge_payload())
        service = ProjectionService(journal)

        first_reports = service.rebuild_all()
        first_snapshots = tuple(journal.load_projection_snapshot(name) for name in service.names)
        second_reports = service.rebuild_all()
        second_snapshots = tuple(journal.load_projection_snapshot(name) for name in service.names)

    assert first_reports == second_reports
    assert first_snapshots == second_snapshots
    assert all(snapshot is not None for snapshot in first_snapshots)


def test_projection_checkpoint_survives_process_restart(tmp_path: Path) -> None:
    path = tmp_path / "journal.db"
    with JournalStore(path, SteppingClock()) as journal:
        journal.append("system", "approval.requested", _request_payload(REQUEST_ONE))
        ProjectionService(journal).rebuild_all()

    with JournalStore(path, SteppingClock()) as reopened:
        service = ProjectionService(reopened)

        assert service.pending_approvals().get(REQUEST_ONE) is not None
        assert service.challenge_counters().last_applied_seq == 1


def test_catch_up_processes_only_new_events_and_is_idempotent(tmp_path: Path) -> None:
    with JournalStore(tmp_path / "journal.db", SteppingClock()) as journal:
        service = ProjectionService(journal)
        journal.append("system", "approval.requested", _request_payload(REQUEST_ONE))
        service.rebuild("pending_approvals")
        journal.append("system", "approval.requested", _request_payload(REQUEST_TWO))

        caught_up = service.catch_up("pending_approvals")
        repeated = service.catch_up("pending_approvals")
        state = service.pending_approvals()

    assert caught_up.processed_events == 1
    assert caught_up.rebuilt_from_empty is False
    assert repeated.processed_events == 0
    assert repeated.state_hash == caught_up.state_hash
    assert tuple(item.request_id for item in state.pending) == (REQUEST_ONE, REQUEST_TWO)


def test_interrupted_catch_up_preserves_previous_checkpoint(tmp_path: Path) -> None:
    class InterruptedProjection(PendingApprovalsProjection):
        def fold(self, state: PendingApprovalsState, event: Event) -> PendingApprovalsState:
            if event.seq == 2:
                raise RuntimeError("simulated interruption")
            return super().fold(state, event)

    path = tmp_path / "journal.db"
    with JournalStore(path, SteppingClock()) as journal:
        journal.append("system", "approval.requested", _request_payload(REQUEST_ONE))
        service = ProjectionService(journal)
        service.rebuild("pending_approvals")
        before = journal.load_projection_snapshot("pending_approvals")
        journal.append("system", "approval.requested", _request_payload(REQUEST_TWO))

        with pytest.raises(RuntimeError, match="simulated interruption"):
            ProjectionRunner(journal, InterruptedProjection()).catch_up()

        after_failure = journal.load_projection_snapshot("pending_approvals")
        recovered = service.catch_up("pending_approvals")

    assert before == after_failure
    assert recovered.last_applied_seq == 2
    assert recovered.processed_events == 1


def test_corrupted_projection_checkpoint_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "journal.db"
    with JournalStore(path, SteppingClock()) as journal:
        journal.append("apex", "policy.challenged", _challenge_payload())
        ProjectionService(journal).rebuild("challenge_counters")

    with sqlite3.connect(path) as administrator:
        administrator.execute(
            """
            UPDATE projection_snapshots
            SET state = replace(state, '"count":1', '"count":2')
            WHERE name = 'challenge_counters'
            """
        )

    with (
        JournalStore(path, SteppingClock()) as journal,
        pytest.raises(ProjectionSnapshotCorruptionError, match="hash validation"),
    ):
        ProjectionService(journal).challenge_counters()


def test_online_rebuild_can_lag_and_then_catch_up(tmp_path: Path) -> None:
    class BlockingProjection(PendingApprovalsProjection):
        def __init__(self, reading: threading.Event, resume: threading.Event) -> None:
            self._reading = reading
            self._resume = resume

        def fold(self, state: PendingApprovalsState, event: Event) -> PendingApprovalsState:
            if event.seq == 1:
                self._reading.set()
                assert self._resume.wait(timeout=5)
            return super().fold(state, event)

    path = tmp_path / "journal.db"
    reading = threading.Event()
    resume = threading.Event()
    results: queue.SimpleQueue[object] = queue.SimpleQueue()

    with JournalStore(path, SteppingClock()) as writer:
        writer.append("system", "approval.requested", _request_payload(REQUEST_ONE))

        def rebuild_in_reader() -> None:
            try:
                with JournalStore(path, SteppingClock()) as reader:
                    result = ProjectionRunner(
                        reader,
                        BlockingProjection(reading, resume),
                    ).rebuild()
                    results.put(result)
            except BaseException as error:
                results.put(error)

        worker = threading.Thread(target=rebuild_in_reader)
        worker.start()
        assert reading.wait(timeout=5)
        writer.append("system", "approval.requested", _request_payload(REQUEST_TWO))
        resume.set()
        worker.join(timeout=5)
        assert not worker.is_alive()

        result = results.get()
        if isinstance(result, BaseException):
            raise result
        service = ProjectionService(writer)
        lagging = service.pending_approvals()
        caught_up = service.catch_up("pending_approvals")
        current = service.pending_approvals()

    assert lagging.last_applied_seq == 1
    assert caught_up.processed_events == 1
    assert current.last_applied_seq == 2
    assert tuple(item.request_id for item in current.pending) == (REQUEST_ONE, REQUEST_TWO)


def test_unknown_projection_name_fails_explicitly(tmp_path: Path) -> None:
    with JournalStore(tmp_path / "journal.db", SteppingClock()) as journal:
        service = ProjectionService(journal)

        with pytest.raises(UnknownProjectionError, match="unknown projection"):
            service.rebuild("ledger")
