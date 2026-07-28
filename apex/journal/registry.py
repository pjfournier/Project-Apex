"""Static event-type registry and JSON Schema validation."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from .errors import PayloadSchemaError, UnregisteredEventTypeError
from .json_types import JsonObject, JsonValue, freeze_object

_OBJECT_SCHEMA = '{"additionalProperties":true,"type":"object"}'
_APPROVAL_REQUESTED_SCHEMA = (
    '{"additionalProperties":true,"properties":{'
    '"args_hash":{"pattern":"^[0-9a-f]{64}$","type":"string"},'
    '"bundle_id":{"pattern":"^[0-7][0123456789ABCDEFGHJKMNPQRSTVWXYZ]{25}$","type":"string"},'
    '"expires_at":{"pattern":"Z$","type":"string"},'
    '"policy_version":{"type":"integer"},'
    '"request_id":{"pattern":"^[0-7][0123456789ABCDEFGHJKMNPQRSTVWXYZ]{25}$","type":"string"},'
    '"tool":{"type":"string"}},'
    '"required":["request_id","bundle_id","policy_version","tool","args_hash","expires_at"],'
    '"type":"object"}'
)
_APPROVAL_TERMINAL_SCHEMA = (
    '{"additionalProperties":true,"properties":{'
    '"request_id":{"pattern":"^[0-7][0123456789ABCDEFGHJKMNPQRSTVWXYZ]{25}$","type":"string"}},'
    '"required":["request_id"],"type":"object"}'
)
_POLICY_CHALLENGED_SCHEMA = (
    '{"additionalProperties":true,"properties":{'
    '"bundle_id":{"pattern":"^[0-7][0123456789ABCDEFGHJKMNPQRSTVWXYZ]{25}$","type":"string"},'
    '"decision_id":{"pattern":"^[0-7][0123456789ABCDEFGHJKMNPQRSTVWXYZ]{25}$",'
    '"type":"string"},'
    '"policy_version":{"type":"integer"},'
    '"reasoning":{"type":"string"},'
    '"rule_id":{"type":"string"}},'
    '"required":["decision_id","reasoning","bundle_id","policy_version","rule_id"],'
    '"type":"object"}'
)

_EVENT_TYPES: Final[tuple[str, ...]] = (
    "session.started",
    "session.ended",
    "turn.started",
    "turn.completed",
    "turn.aborted",
    "user.message",
    "apex.message",
    "model.called",
    "model.returned",
    "model.failed",
    "tool.requested",
    "tool.result",
    "tool.failed",
    "policy.decided",
    "policy.challenged",
    "approval.requested",
    "approval.granted",
    "approval.denied",
    "approval.expired",
    "memory.assertion.proposed",
    "memory.assertion.applied",
    "memory.assertion.rejected",
    "commitment.created",
    "commitment.updated",
    "commitment.closed",
    "artifact.proposed",
    "artifact.validated",
    "artifact.rejected",
    "artifact.evaluated",
    "artifact.activated",
    "artifact.rolled_back",
    "bundle.revoked",
    "approval.invalidated",
    "model.qualified",
    "reflection.started",
    "reflection.completed",
    "self_model.digest.regenerated",
    "voice.envelope.measured",
    "continuity.evaluated",
    "development.reviewed",
    "admin.action",
)


@dataclass(frozen=True)
class EventSchema:
    """One immutable event-type schema registration."""

    event_type: str
    schema_version: int
    schema_json: str


def _schema_for(event_type: str) -> str:
    if event_type == "approval.requested":
        return _APPROVAL_REQUESTED_SCHEMA
    if event_type in {
        "approval.granted",
        "approval.denied",
        "approval.expired",
        "approval.invalidated",
    }:
        return _APPROVAL_TERMINAL_SCHEMA
    if event_type == "policy.challenged":
        return _POLICY_CHALLENGED_SCHEMA
    return _OBJECT_SCHEMA


EVENT_SCHEMAS: Final[tuple[EventSchema, ...]] = tuple(
    EventSchema(event_type, 1, _schema_for(event_type)) for event_type in _EVENT_TYPES
)


def registered_schema(event_type: str, schema_version: int | None = None) -> EventSchema:
    """Return a registered schema, choosing the newest version when omitted."""
    matches = tuple(
        schema
        for schema in EVENT_SCHEMAS
        if schema.event_type == event_type
        and (schema_version is None or schema.schema_version == schema_version)
    )
    if not matches:
        suffix = "" if schema_version is None else f" at version {schema_version}"
        raise UnregisteredEventTypeError(f"unregistered event type {event_type!r}{suffix}")
    return max(matches, key=lambda schema: schema.schema_version)


def validate_payload(schema: EventSchema, payload: JsonValue) -> None:
    """Validate a payload against the registered, immutable JSON Schema."""
    raw_schema: object = json.loads(schema.schema_json)
    parsed_schema = freeze_object(raw_schema)
    _validate_value(payload, parsed_schema, "$")


def _validate_value(value: JsonValue, schema: JsonObject, path: str) -> None:
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _matches_type(value, expected_type):
        raise PayloadSchemaError(f"{path}: expected {expected_type}")

    enum_values = schema.get("enum")
    if isinstance(enum_values, tuple) and value not in enum_values:
        raise PayloadSchemaError(f"{path}: value is not in enum")

    if isinstance(value, Mapping):
        required = schema.get("required")
        if isinstance(required, tuple):
            for key in required:
                if isinstance(key, str) and key not in value:
                    raise PayloadSchemaError(f"{path}: missing required property {key!r}")
        properties = schema.get("properties")
        property_schemas = properties if isinstance(properties, Mapping) else {}
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            child_schema = property_schemas.get(key)
            if isinstance(child_schema, Mapping):
                _validate_value(item, child_schema, f"{path}.{key}")
            elif additional is False:
                raise PayloadSchemaError(f"{path}: additional property {key!r} is forbidden")

    if isinstance(value, tuple):
        items = schema.get("items")
        if isinstance(items, Mapping):
            for index, item in enumerate(value):
                _validate_value(item, items, f"{path}[{index}]")

    if isinstance(value, str):
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            raise PayloadSchemaError(f"{path}: string does not match pattern")


def _matches_type(value: JsonValue, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, Mapping)
    if expected_type == "array":
        return isinstance(value, tuple)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    raise PayloadSchemaError(f"unsupported JSON Schema type {expected_type!r}")
