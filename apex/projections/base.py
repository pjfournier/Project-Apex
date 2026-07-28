"""Generic deterministic projection replay and checkpointing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from apex.journal import Event, JournalStore, JsonObject

from .errors import ProjectionSequenceError, ProjectionStateCorruptionError


class ProjectionState(Protocol):
    """State shared by every projection."""

    @property
    def last_applied_seq(self) -> int:
        """Last Journal sequence incorporated into state."""
        ...


class Projection[StateT: ProjectionState](Protocol):
    """Pure projection fold and deterministic state codec."""

    @property
    def name(self) -> str:
        """Stable persistence name."""
        ...

    def initial(self) -> StateT:
        """Return empty state."""
        ...

    def fold(self, state: StateT, event: Event) -> StateT:
        """Return state after one Journal event."""
        ...

    def encode(self, state: StateT) -> JsonObject:
        """Encode state into immutable JSON."""
        ...

    def decode(self, state: JsonObject) -> StateT:
        """Decode and validate immutable JSON state."""
        ...


@dataclass(frozen=True)
class RebuildReport:
    """Projection replay result."""

    projection_name: str
    processed_events: int
    last_applied_seq: int
    state_hash: str
    rebuilt_from_empty: bool


class ProjectionRunner[StateT: ProjectionState]:
    """Replay one pure projection against a Journal."""

    def __init__(self, journal: JournalStore, projection: Projection[StateT]) -> None:
        self._journal = journal
        self._projection = projection

    def rebuild(self) -> RebuildReport:
        """Rebuild from empty state and atomically publish the checkpoint."""
        state = self._projection.initial()
        processed = 0
        for event in self._journal.read_range(0):
            state = self._projection.fold(state, event)
            processed += 1
        snapshot = self._journal.replace_projection_snapshot(
            self._projection.name,
            state.last_applied_seq,
            self._projection.encode(state),
        )
        return RebuildReport(
            self._projection.name,
            processed,
            state.last_applied_seq,
            snapshot.state_hash,
            True,
        )

    def catch_up(self) -> RebuildReport:
        """Resume from the durable checkpoint and fold unseen Journal events."""
        snapshot = self._journal.load_projection_snapshot(self._projection.name)
        if snapshot is None:
            return self.rebuild()
        state = self._projection.decode(snapshot.state)
        if state.last_applied_seq != snapshot.last_applied_seq:
            raise ProjectionStateCorruptionError(
                f"{self._projection.name} state sequence does not match checkpoint"
            )
        processed = 0
        for event in self._journal.read_range(state.last_applied_seq + 1):
            state = self._projection.fold(state, event)
            processed += 1
        if processed == 0:
            return RebuildReport(
                self._projection.name,
                0,
                state.last_applied_seq,
                snapshot.state_hash,
                False,
            )
        updated = self._journal.replace_projection_snapshot(
            self._projection.name,
            state.last_applied_seq,
            self._projection.encode(state),
        )
        return RebuildReport(
            self._projection.name,
            processed,
            state.last_applied_seq,
            updated.state_hash,
            False,
        )

    def state(self) -> StateT:
        """Return the verified checkpoint state, or empty state when absent."""
        snapshot = self._journal.load_projection_snapshot(self._projection.name)
        if snapshot is None:
            return self._projection.initial()
        state = self._projection.decode(snapshot.state)
        if state.last_applied_seq != snapshot.last_applied_seq:
            raise ProjectionStateCorruptionError(
                f"{self._projection.name} state sequence does not match checkpoint"
            )
        return state


def should_apply(last_applied_seq: int, event: Event) -> bool:
    """Enforce dense replay while making duplicate delivery idempotent."""
    if event.seq <= last_applied_seq:
        return False
    expected = last_applied_seq + 1
    if event.seq != expected:
        raise ProjectionSequenceError(
            f"expected Journal seq {expected}, received {event.seq}"
        )
    return True
