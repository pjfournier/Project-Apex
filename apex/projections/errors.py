"""Typed projection failures."""


class ProjectionError(Exception):
    """Base class for projection failures."""


class ProjectionSequenceError(ProjectionError):
    """Events were supplied out of dense Journal sequence order."""


class ProjectionInputError(ProjectionError):
    """A relevant Journal event has an invalid projection payload."""


class ProjectionStateCorruptionError(ProjectionError):
    """A decoded projection checkpoint violates its state contract."""


class UnknownProjectionError(ProjectionError):
    """A requested projection name is not registered."""
