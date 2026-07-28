"""Immutable Journal event envelopes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from .errors import InvalidEnvelopeError
from .json_types import JsonObject, freeze_object
from .registry import registered_schema, validate_payload
from .ulid import is_ulid

_ACTOR = re.compile(r"^(?:user|apex|system|agent:[A-Za-z0-9_-]+)$")
_EVENT_TYPE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Event:
    """The one envelope shared by every Journal record."""

    event_id: str
    seq: int
    ts: str
    actor: str
    type: str
    schema_version: int
    session_id: str | None
    turn_id: str | None
    caused_by: str | None
    payload: JsonObject
    prev_hash: str
    hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", freeze_object(self.payload))
        _validate_envelope(self)
        schema = registered_schema(self.type, self.schema_version)
        validate_payload(schema, self.payload)


def _validate_envelope(event: Event) -> None:
    if not is_ulid(event.event_id):
        raise InvalidEnvelopeError("event_id must be a ULID")
    if event.seq < 1:
        raise InvalidEnvelopeError("seq must be positive")
    if not event.ts.endswith("Z"):
        raise InvalidEnvelopeError("ts must be a UTC ISO-8601 string ending in Z")
    try:
        timestamp = datetime.fromisoformat(event.ts.replace("Z", "+00:00"))
    except ValueError as error:
        raise InvalidEnvelopeError("ts must be valid ISO-8601") from error
    if timestamp.tzinfo is None or timestamp.utcoffset() != UTC.utcoffset(timestamp):
        raise InvalidEnvelopeError("ts must be UTC")
    if _ACTOR.fullmatch(event.actor) is None:
        raise InvalidEnvelopeError(f"invalid actor {event.actor!r}")
    if _EVENT_TYPE.fullmatch(event.type) is None:
        raise InvalidEnvelopeError(f"invalid event type {event.type!r}")
    if event.schema_version < 1:
        raise InvalidEnvelopeError("schema_version must be positive")
    for field_name, value in (
        ("session_id", event.session_id),
        ("turn_id", event.turn_id),
        ("caused_by", event.caused_by),
    ):
        if value is not None and not is_ulid(value):
            raise InvalidEnvelopeError(f"{field_name} must be a ULID or null")
    if _HASH.fullmatch(event.prev_hash) is None:
        raise InvalidEnvelopeError("prev_hash must be lowercase SHA-256 hex")
    if _HASH.fullmatch(event.hash) is None:
        raise InvalidEnvelopeError("hash must be lowercase SHA-256 hex")
