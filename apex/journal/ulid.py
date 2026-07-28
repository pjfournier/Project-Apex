"""ULID encoding in the Journal's single identity-generation location."""

from __future__ import annotations

from datetime import datetime

from .errors import InvalidEnvelopeError

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_MAX_TIMESTAMP = (1 << 48) - 1
_MAX_RANDOMNESS = (1 << 80) - 1


def new_monotonic_ulid(timestamp: datetime, seq: int, previous: str | None) -> str:
    """Build a monotonic ULID from injected time and the durable sequence."""
    timestamp_ms = int(timestamp.timestamp() * 1000)
    if previous is not None:
        timestamp_ms = max(timestamp_ms, ulid_timestamp_ms(previous))
    if not 0 <= timestamp_ms <= _MAX_TIMESTAMP:
        raise InvalidEnvelopeError("timestamp is outside the ULID range")
    if not 0 <= seq <= _MAX_RANDOMNESS:
        raise InvalidEnvelopeError("sequence is outside the ULID randomness range")
    return _encode(timestamp_ms, 10) + _encode(seq, 16)


def is_ulid(value: str) -> bool:
    """Return whether a string is a canonical 26-character ULID."""
    return (
        len(value) == 26
        and value[0] in "01234567"
        and all(character in _ALPHABET for character in value)
    )


def ulid_timestamp_ms(value: str) -> int:
    """Decode the timestamp component of a validated ULID."""
    if not is_ulid(value):
        raise InvalidEnvelopeError(f"invalid ULID {value!r}")
    result = 0
    for character in value[:10]:
        result = (result << 5) | _ALPHABET.index(character)
    return result


def _encode(value: int, width: int) -> str:
    characters = ["0"] * width
    for index in range(width - 1, -1, -1):
        characters[index] = _ALPHABET[value & 31]
        value >>= 5
    return "".join(characters)
