from datetime import UTC, datetime

from apex.ports import Clock, Rng, SignatureVerifier


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)


class FixedRng:
    def bytes(self, length: int) -> bytes:
        return b"x" * length


class RejectingVerifier:
    def verify(self, message: bytes, signature: bytes) -> bool:
        return False


def test_ports_are_structurally_implementable() -> None:
    clock: Clock = FixedClock()
    rng: Rng = FixedRng()
    verifier: SignatureVerifier = RejectingVerifier()

    assert clock.now().tzinfo is UTC
    assert rng.bytes(3) == b"xxx"
    assert verifier.verify(b"message", b"signature") is False
