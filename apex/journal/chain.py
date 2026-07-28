"""Canonical JSON and tamper-evident Journal hashing."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass

from .events import Event
from .json_types import JsonObject, JsonValue

GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class ChainReport:
    """Result of verifying a contiguous Journal range."""

    valid: bool
    checked_from_seq: int
    checked_to_seq: int
    divergence_seq: int | None
    reason: str | None


def canonical_json(value: JsonObject) -> bytes:
    """Serialize JSON once, canonically, for persistence and hashing."""
    plain = _plain_json(value)
    return json.dumps(
        plain,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def compute_event_hash(
    *,
    event_id: str,
    seq: int,
    ts: str,
    actor: str,
    event_type: str,
    schema_version: int,
    session_id: str | None,
    turn_id: str | None,
    caused_by: str | None,
    payload: JsonObject,
    prev_hash: str,
) -> str:
    """Hash every envelope field except the hash itself."""
    fields: dict[str, JsonValue] = {
        "event_id": event_id,
        "seq": seq,
        "ts": ts,
        "actor": actor,
        "type": event_type,
        "schema_version": schema_version,
        "session_id": session_id,
        "turn_id": turn_id,
        "caused_by": caused_by,
        "payload": payload,
        "prev_hash": prev_hash,
    }
    return hashlib.sha256(canonical_json(fields)).hexdigest()


def recompute_event_hash(event: Event) -> str:
    """Recompute an existing event's hash."""
    return compute_event_hash(
        event_id=event.event_id,
        seq=event.seq,
        ts=event.ts,
        actor=event.actor,
        event_type=event.type,
        schema_version=event.schema_version,
        session_id=event.session_id,
        turn_id=event.turn_id,
        caused_by=event.caused_by,
        payload=event.payload,
        prev_hash=event.prev_hash,
    )


def payload_json(payload: JsonObject) -> str:
    """Persist payloads with the same canonical serializer used for hashes."""
    return canonical_json(payload).decode("utf-8")


def _plain_json(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _plain_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain_json(item) for item in value]
    return value
