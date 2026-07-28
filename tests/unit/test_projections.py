from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.journal.chain import GENESIS_HASH, compute_event_hash
from apex.journal.events import Event
from apex.journal.json_types import freeze_object
from apex.journal.registry import registered_schema
from apex.journal.ulid import new_monotonic_ulid
from apex.projections import (
    ChallengeCountersProjection,
    PendingApprovalsProjection,
    ProjectionInputError,
    ProjectionSequenceError,
    ProjectionStateCorruptionError,
)

BUNDLE_ID = "01KDVDNA000000000000000020"
REQUEST_ID = "01KDVDNA000000000000000010"
DECISION_ID = "01KDVDNA000000000000000030"
ARGS_HASH = "a" * 64
TIMESTAMP = datetime(2026, 1, 1, tzinfo=UTC)


def _event(seq: int, event_type: str, payload: object) -> Event:
    event_id = new_monotonic_ulid(TIMESTAMP, seq, None)
    frozen_payload = freeze_object(payload)
    schema = registered_schema(event_type)
    event_hash = compute_event_hash(
        event_id=event_id,
        seq=seq,
        ts="2026-01-01T00:00:00.000000Z",
        actor="system",
        event_type=event_type,
        schema_version=schema.schema_version,
        session_id=None,
        turn_id=None,
        caused_by=None,
        payload=frozen_payload,
        prev_hash=GENESIS_HASH,
    )
    return Event(
        event_id=event_id,
        seq=seq,
        ts="2026-01-01T00:00:00.000000Z",
        actor="system",
        type=event_type,
        schema_version=schema.schema_version,
        session_id=None,
        turn_id=None,
        caused_by=None,
        payload=frozen_payload,
        prev_hash=GENESIS_HASH,
        hash=event_hash,
    )


def _approval_payload(request_id: str = REQUEST_ID, policy_version: int = 1) -> object:
    return {
        "args_hash": ARGS_HASH,
        "bundle_id": BUNDLE_ID,
        "expires_at": "2026-01-02T00:00:00Z",
        "policy_version": policy_version,
        "request_id": request_id,
        "tool": "fs.write_file",
    }


def _challenge_payload(rule_id: str = "r-write") -> object:
    return {
        "bundle_id": BUNDLE_ID,
        "decision_id": DECISION_ID,
        "policy_version": 7,
        "reasoning": "The request is necessary.",
        "rule_id": rule_id,
    }


@pytest.mark.parametrize(
    "terminal_type",
    [
        "approval.granted",
        "approval.denied",
        "approval.expired",
        "approval.invalidated",
    ],
)
def test_pending_approval_terminal_events_remove_request(terminal_type: str) -> None:
    projection = PendingApprovalsProjection()
    requested = _event(1, "approval.requested", _approval_payload())
    terminal = _event(2, terminal_type, {"request_id": REQUEST_ID})

    pending = projection.fold(projection.initial(), requested)
    resolved = projection.fold(pending, terminal)

    assert pending.get(REQUEST_ID) is not None
    assert resolved.pending == ()
    assert resolved.last_applied_seq == 2


def test_pending_approval_irrelevant_event_only_advances_sequence() -> None:
    projection = PendingApprovalsProjection()

    state = projection.fold(projection.initial(), _event(1, "admin.action", {}))

    assert state.pending == ()
    assert state.last_applied_seq == 1


def test_duplicate_event_delivery_is_idempotent() -> None:
    projection = PendingApprovalsProjection()
    requested = _event(1, "approval.requested", _approval_payload())
    once = projection.fold(projection.initial(), requested)

    twice = projection.fold(once, requested)

    assert twice is once


def test_duplicate_request_id_in_distinct_events_fails() -> None:
    projection = PendingApprovalsProjection()
    state = projection.fold(
        projection.initial(),
        _event(1, "approval.requested", _approval_payload()),
    )

    with pytest.raises(ProjectionInputError, match="duplicate approval"):
        projection.fold(state, _event(2, "approval.requested", _approval_payload()))


def test_projection_rejects_sequence_gap() -> None:
    projection = ChallengeCountersProjection()

    with pytest.raises(ProjectionSequenceError, match="expected Journal seq 1"):
        projection.fold(projection.initial(), _event(2, "admin.action", {}))


def test_approval_rejects_nonpositive_policy_version() -> None:
    projection = PendingApprovalsProjection()

    with pytest.raises(ProjectionInputError, match="must be positive"):
        projection.fold(
            projection.initial(),
            _event(1, "approval.requested", _approval_payload(policy_version=0)),
        )


def test_challenge_counters_isolate_bundle_version_and_rule() -> None:
    projection = ChallengeCountersProjection()
    state = projection.initial()
    state = projection.fold(state, _event(1, "policy.challenged", _challenge_payload()))
    state = projection.fold(state, _event(2, "policy.challenged", _challenge_payload()))
    state = projection.fold(
        state,
        _event(3, "policy.challenged", _challenge_payload(rule_id="r-other")),
    )

    assert state.count(BUNDLE_ID, 7, "r-write") == 2
    assert state.count(BUNDLE_ID, 7, "r-other") == 1
    assert state.count(BUNDLE_ID, 8, "r-write") == 0


def test_projection_codecs_round_trip_byte_stable_state() -> None:
    approvals = PendingApprovalsProjection()
    approval_state = approvals.fold(
        approvals.initial(),
        _event(1, "approval.requested", _approval_payload()),
    )
    counters = ChallengeCountersProjection()
    counter_state = counters.fold(
        counters.initial(),
        _event(1, "policy.challenged", _challenge_payload()),
    )

    assert approvals.decode(approvals.encode(approval_state)) == approval_state
    assert counters.decode(counters.encode(counter_state)) == counter_state


def test_projection_codec_rejects_unsorted_duplicate_state() -> None:
    projection = PendingApprovalsProjection()
    state = projection.fold(
        projection.initial(),
        _event(1, "approval.requested", _approval_payload()),
    )
    encoded = projection.encode(state)
    pending = encoded["pending"]
    assert isinstance(pending, tuple)
    corrupted = freeze_object(
        {
            "last_applied_seq": 1,
            "pending": [pending[0], pending[0]],
        }
    )

    with pytest.raises(ProjectionStateCorruptionError, match="uniquely sorted"):
        projection.decode(corrupted)
