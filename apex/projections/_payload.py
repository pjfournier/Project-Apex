"""Strict JSON readers shared by projection folds."""

from __future__ import annotations

from collections.abc import Mapping

from apex.journal import JsonObject, JsonValue

from .errors import ProjectionInputError, ProjectionStateCorruptionError


def event_str(payload: JsonObject, field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ProjectionInputError(f"event payload field {field!r} must be nonempty text")
    return value


def event_int(payload: JsonObject, field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProjectionInputError(f"event payload field {field!r} must be an integer")
    return value


def state_str(payload: JsonObject, field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ProjectionStateCorruptionError(
            f"projection state field {field!r} must be nonempty text"
        )
    return value


def state_int(payload: JsonObject, field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProjectionStateCorruptionError(f"projection state field {field!r} must be an integer")
    return value


def state_array(payload: JsonObject, field: str) -> tuple[JsonValue, ...]:
    value = payload.get(field)
    if not isinstance(value, tuple):
        raise ProjectionStateCorruptionError(f"projection state field {field!r} must be an array")
    return value


def state_object(value: JsonValue, context: str) -> JsonObject:
    if not isinstance(value, Mapping):
        raise ProjectionStateCorruptionError(f"{context} must be an object")
    return value
