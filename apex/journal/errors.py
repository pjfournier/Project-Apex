"""Typed Journal failures."""


class JournalError(Exception):
    """Base class for Journal failures."""


class InvalidEnvelopeError(JournalError):
    """An event envelope violates its structural contract."""


class UnregisteredEventTypeError(JournalError):
    """An event type or schema version is not registered."""


class PayloadSchemaError(JournalError):
    """An event payload does not satisfy its registered JSON Schema."""


class JournalWriteError(JournalError):
    """A durable Journal append failed."""


class EventNotFoundError(JournalError):
    """A requested event does not exist."""


class StoredEventCorruptionError(JournalError):
    """A stored row cannot be decoded as a valid event."""
