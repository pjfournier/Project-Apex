"""Policy-challenge counter projection."""

from __future__ import annotations

from dataclasses import dataclass

from apex.journal import Event, JsonObject, freeze_object, is_ulid

from ._payload import event_int, event_str, state_array, state_int, state_object, state_str
from .base import should_apply
from .errors import ProjectionInputError, ProjectionStateCorruptionError


@dataclass(frozen=True, order=True)
class ChallengeKey:
    """Stable challenge rate-limit key."""

    bundle_id: str
    policy_version: int
    rule_id: str


@dataclass(frozen=True)
class ChallengeCount:
    """Challenge count for one rule under one bundle version."""

    key: ChallengeKey
    count: int


@dataclass(frozen=True)
class ChallengeCountersState:
    """Immutable challenge-counter state."""

    last_applied_seq: int
    counters: tuple[ChallengeCount, ...]

    def count(self, bundle_id: str, policy_version: int, rule_id: str) -> int:
        """Return a challenge count, defaulting to zero."""
        key = ChallengeKey(bundle_id, policy_version, rule_id)
        return next((item.count for item in self.counters if item.key == key), 0)


class ChallengeCountersProjection:
    """Pure fold over policy challenge events."""

    @property
    def name(self) -> str:
        return "challenge_counters"

    def initial(self) -> ChallengeCountersState:
        return ChallengeCountersState(0, ())

    def fold(self, state: ChallengeCountersState, event: Event) -> ChallengeCountersState:
        if not should_apply(state.last_applied_seq, event):
            return state
        counters = {item.key: item.count for item in state.counters}
        if event.type == "policy.challenged":
            key = ChallengeKey(
                bundle_id=event_str(event.payload, "bundle_id"),
                policy_version=event_int(event.payload, "policy_version"),
                rule_id=event_str(event.payload, "rule_id"),
            )
            if not is_ulid(key.bundle_id):
                raise ProjectionInputError("challenge bundle_id must be a ULID")
            if key.policy_version < 1:
                raise ProjectionInputError("challenge policy_version must be positive")
            counters[key] = counters.get(key, 0) + 1
        return ChallengeCountersState(
            event.seq,
            tuple(
                ChallengeCount(key, count)
                for key, count in sorted(counters.items(), key=lambda item: item[0])
            ),
        )

    def encode(self, state: ChallengeCountersState) -> JsonObject:
        return freeze_object(
            {
                "counters": [
                    {
                        "bundle_id": item.key.bundle_id,
                        "count": item.count,
                        "policy_version": item.key.policy_version,
                        "rule_id": item.key.rule_id,
                    }
                    for item in state.counters
                ],
                "last_applied_seq": state.last_applied_seq,
            }
        )

    def decode(self, state: JsonObject) -> ChallengeCountersState:
        last_applied_seq = state_int(state, "last_applied_seq")
        if last_applied_seq < 0:
            raise ProjectionStateCorruptionError("last_applied_seq must be nonnegative")
        counters = tuple(
            _counter_from_state(state_object(value, "challenge counter"))
            for value in state_array(state, "counters")
        )
        keys = tuple(item.key for item in counters)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ProjectionStateCorruptionError(
                "challenge counters must be uniquely sorted by key"
            )
        return ChallengeCountersState(last_applied_seq, counters)


def _counter_from_state(state: JsonObject) -> ChallengeCount:
    key = ChallengeKey(
        bundle_id=state_str(state, "bundle_id"),
        policy_version=state_int(state, "policy_version"),
        rule_id=state_str(state, "rule_id"),
    )
    count = state_int(state, "count")
    if not is_ulid(key.bundle_id):
        raise ProjectionStateCorruptionError("challenge state bundle_id must be a ULID")
    if key.policy_version < 1 or count < 1:
        raise ProjectionStateCorruptionError("challenge state version and count must be positive")
    return ChallengeCount(key, count)
