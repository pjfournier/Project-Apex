from datetime import UTC, datetime

import pytest

from apex.journal.chain import GENESIS_HASH, canonical_json, compute_event_hash
from apex.journal.errors import InvalidEnvelopeError, PayloadSchemaError
from apex.journal.json_types import freeze_object
from apex.journal.registry import EVENT_SCHEMAS, EventSchema, validate_payload
from apex.journal.ulid import is_ulid, new_monotonic_ulid


def test_canonical_json_sorts_keys_and_removes_whitespace() -> None:
    first = freeze_object({"z": 1, "a": {"b": True, "a": None}})
    second = freeze_object({"a": {"a": None, "b": True}, "z": 1})

    assert canonical_json(first) == b'{"a":{"a":null,"b":true},"z":1}'
    assert canonical_json(first) == canonical_json(second)


def test_canonical_json_rejects_nonfinite_numbers() -> None:
    with pytest.raises(InvalidEnvelopeError):
        freeze_object({"invalid": float("nan")})


def test_event_hash_is_deterministic_and_covers_payload() -> None:
    def hash_payload(text: str) -> str:
        return compute_event_hash(
            event_id="01KDVDNA000000000000000001",
            seq=1,
            ts="2026-01-01T00:00:00.000000Z",
            actor="user",
            event_type="user.message",
            schema_version=1,
            session_id=None,
            turn_id=None,
            caused_by=None,
            payload=freeze_object({"text": text}),
            prev_hash=GENESIS_HASH,
        )

    first = hash_payload("a")
    repeated = hash_payload("a")
    changed = hash_payload("b")

    assert first == repeated
    assert first != changed
    assert len(first) == 64


def test_ulids_are_monotonic_when_clock_moves_backward() -> None:
    later = datetime(2026, 1, 1, tzinfo=UTC)
    earlier = datetime(2025, 1, 1, tzinfo=UTC)

    first = new_monotonic_ulid(later, 1, None)
    second = new_monotonic_ulid(earlier, 2, first)

    assert is_ulid(first)
    assert is_ulid(second)
    assert first < second


def test_registry_is_static_and_contains_spec_minimum() -> None:
    registered = {schema.event_type for schema in EVENT_SCHEMAS}

    assert "session.started" in registered
    assert "user.message" in registered
    assert "tool.result" in registered
    assert "artifact.activated" in registered
    assert "development.reviewed" in registered
    assert "admin.action" in registered
    assert len(registered) == 41


def test_json_schema_validator_rejects_required_property_violation() -> None:
    schema = EventSchema(
        "example.event",
        1,
        '{"additionalProperties":false,"properties":{"text":{"type":"string"}},'
        '"required":["text"],"type":"object"}',
    )

    with pytest.raises(PayloadSchemaError, match="missing required property"):
        validate_payload(schema, freeze_object({}))
