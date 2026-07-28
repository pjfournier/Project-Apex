"""Typed boundaries for nondeterministic or host-provided capabilities."""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Supply an aware UTC timestamp."""

    def now(self) -> datetime:
        """Return the current time as an aware UTC datetime."""
        ...


class Rng(Protocol):
    """Supply cryptographically suitable random bytes."""

    def bytes(self, length: int) -> bytes:
        """Return exactly ``length`` random bytes."""
        ...


class SignatureVerifier(Protocol):
    """Verify signatures without exposing signing capability."""

    def verify(self, message: bytes, signature: bytes) -> bool:
        """Return whether ``signature`` is valid for ``message``."""
        ...
