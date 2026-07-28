from collections.abc import MutableMapping
from typing import cast

import pytest

from apex.journal.chain import GENESIS_HASH, compute_event_hash
from apex.journal.events import Event
from apex.journal.json_types import JsonValue, freeze_object


def _event() -> Event:
    payload = freeze_object({"nested": {"value": 1}})
    event_hash = compute_event_hash(
        event_id="01KDVDNA000000000000000001",
        seq=1,
        ts="2026-01-01T00:00:00.000000Z",
        actor="user",
        event_type="user.message",
        schema_version=1,
        session_id=None,
        turn_id=None,
        caused_by=None,
        payload=payload,
        prev_hash=GENESIS_HASH,
    )
    return Event(
        event_id="01KDVDNA000000000000000001",
        seq=1,
        ts="2026-01-01T00:00:00.000000Z",
        actor="user",
        type="user.message",
        schema_version=1,
        session_id=None,
        turn_id=None,
        caused_by=None,
        payload=payload,
        prev_hash=GENESIS_HASH,
        hash=event_hash,
    )


def test_event_envelope_is_frozen() -> None:
    event = _event()

    with pytest.raises(AttributeError):
        event.actor = "apex"  # type: ignore[misc]


def test_event_payload_is_deeply_immutable() -> None:
    event = _event()
    nested = cast(MutableMapping[str, JsonValue], event.payload["nested"])

    with pytest.raises(TypeError):
        nested["value"] = 2
