"""Immutable JSON value types and boundary conversion."""

from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import cast

from .errors import InvalidEnvelopeError

type JsonScalar = bool | int | float | str | None
type JsonValue = JsonScalar | tuple[JsonValue, ...] | Mapping[str, JsonValue]
type JsonObject = Mapping[str, JsonValue]


def freeze_json(value: object) -> JsonValue:
    """Validate and copy a JSON value into an immutable representation."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise InvalidEnvelopeError("JSON numbers must be finite")
        return value
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(item) for item in value)
    if isinstance(value, Mapping):
        source = cast(Mapping[object, object], value)
        frozen: dict[str, JsonValue] = {}
        for key, item in source.items():
            if not isinstance(key, str):
                raise InvalidEnvelopeError("JSON object keys must be strings")
            frozen[key] = freeze_json(item)
        return MappingProxyType(frozen)
    raise InvalidEnvelopeError(f"unsupported JSON value: {type(value).__name__}")


def freeze_object(value: object) -> JsonObject:
    """Validate and copy a JSON object into an immutable representation."""
    frozen = freeze_json(value)
    if not isinstance(frozen, Mapping):
        raise InvalidEnvelopeError("event payload must be a JSON object")
    return frozen
