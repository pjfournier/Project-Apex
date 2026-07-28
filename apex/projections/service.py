"""Registered M2 projection rebuild service."""

from __future__ import annotations

from apex.journal import JournalStore, JsonObject

from .approvals import (
    PendingApprovalsProjection,
    PendingApprovalsState,
)
from .base import ProjectionRunner, RebuildReport
from .counters import ChallengeCountersProjection, ChallengeCountersState
from .errors import UnknownProjectionError


class ProjectionService:
    """Public rebuild and query surface for registered M2 projections."""

    def __init__(self, journal: JournalStore) -> None:
        self._journal = journal

    @property
    def names(self) -> tuple[str, ...]:
        """Return projection names in deterministic rebuild order."""
        return ("pending_approvals", "challenge_counters")

    def rebuild(self, projection_name: str) -> RebuildReport:
        """Discard derived state logically and replay from sequence zero."""
        if projection_name == "pending_approvals":
            return ProjectionRunner(self._journal, PendingApprovalsProjection()).rebuild()
        if projection_name == "challenge_counters":
            return ProjectionRunner(self._journal, ChallengeCountersProjection()).rebuild()
        raise UnknownProjectionError(f"unknown projection {projection_name!r}")

    def rebuild_all(self) -> tuple[RebuildReport, ...]:
        """Rebuild every registered M2 projection."""
        return tuple(self.rebuild(name) for name in self.names)

    def catch_up(self, projection_name: str) -> RebuildReport:
        """Fold only events newer than a projection checkpoint."""
        if projection_name == "pending_approvals":
            return ProjectionRunner(self._journal, PendingApprovalsProjection()).catch_up()
        if projection_name == "challenge_counters":
            return ProjectionRunner(self._journal, ChallengeCountersProjection()).catch_up()
        raise UnknownProjectionError(f"unknown projection {projection_name!r}")

    def pending_approvals(self) -> PendingApprovalsState:
        """Return verified pending-approval state."""
        return ProjectionRunner(self._journal, PendingApprovalsProjection()).state()

    def challenge_counters(self) -> ChallengeCountersState:
        """Return verified challenge-counter state."""
        return ProjectionRunner(self._journal, ChallengeCountersProjection()).state()

    def encoded_state(self, projection_name: str) -> JsonObject:
        """Return canonicalizable state for a registered projection."""
        if projection_name == "pending_approvals":
            return PendingApprovalsProjection().encode(self.pending_approvals())
        if projection_name == "challenge_counters":
            return ChallengeCountersProjection().encode(self.challenge_counters())
        raise UnknownProjectionError(f"unknown projection {projection_name!r}")
