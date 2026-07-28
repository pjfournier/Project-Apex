"""Pending-approval projection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from apex.journal import Event, JsonObject, freeze_object, is_ulid

from ._payload import event_int, event_str, state_array, state_int, state_object, state_str
from .base import should_apply
from .errors import ProjectionInputError, ProjectionStateCorruptionError

_HASH = re.compile(r"^[0-9a-f]{64}$")
_TERMINAL_TYPES = (
    "approval.granted",
    "approval.denied",
    "approval.expired",
    "approval.invalidated",
)


@dataclass(frozen=True)
class PendingApproval:
    """One unresolved confirm-tier request."""

    request_id: str
    bundle_id: str
    policy_version: int
    tool: str
    args_hash: str
    expires_at: str
    requested_event_id: str
    requested_seq: int
    requested_at: str


@dataclass(frozen=True)
class PendingApprovalsState:
    """Immutable pending-approval state."""

    last_applied_seq: int
    pending: tuple[PendingApproval, ...]

    def get(self, request_id: str) -> PendingApproval | None:
        """Return a pending request by ID."""
        return next((item for item in self.pending if item.request_id == request_id), None)


class PendingApprovalsProjection:
    """Pure fold over approval lifecycle events."""

    @property
    def name(self) -> str:
        return "pending_approvals"

    def initial(self) -> PendingApprovalsState:
        return PendingApprovalsState(0, ())

    def fold(self, state: PendingApprovalsState, event: Event) -> PendingApprovalsState:
        if not should_apply(state.last_applied_seq, event):
            return state
        pending = {item.request_id: item for item in state.pending}
        if event.type == "approval.requested":
            approval = _approval_from_event(event)
            if approval.request_id in pending:
                raise ProjectionInputError(
                    f"duplicate approval request {approval.request_id!r}"
                )
            pending[approval.request_id] = approval
        elif event.type in _TERMINAL_TYPES:
            request_id = event_str(event.payload, "request_id")
            if not is_ulid(request_id):
                raise ProjectionInputError("approval request_id must be a ULID")
            pending.pop(request_id, None)
        return PendingApprovalsState(
            event.seq,
            tuple(sorted(pending.values(), key=lambda item: item.request_id)),
        )

    def encode(self, state: PendingApprovalsState) -> JsonObject:
        return freeze_object(
            {
                "last_applied_seq": state.last_applied_seq,
                "pending": [
                    {
                        "args_hash": item.args_hash,
                        "bundle_id": item.bundle_id,
                        "expires_at": item.expires_at,
                        "policy_version": item.policy_version,
                        "request_id": item.request_id,
                        "requested_at": item.requested_at,
                        "requested_event_id": item.requested_event_id,
                        "requested_seq": item.requested_seq,
                        "tool": item.tool,
                    }
                    for item in state.pending
                ],
            }
        )

    def decode(self, state: JsonObject) -> PendingApprovalsState:
        last_applied_seq = state_int(state, "last_applied_seq")
        if last_applied_seq < 0:
            raise ProjectionStateCorruptionError("last_applied_seq must be nonnegative")
        pending = tuple(
            _approval_from_state(state_object(value, "pending approval"))
            for value in state_array(state, "pending")
        )
        request_ids = tuple(item.request_id for item in pending)
        if request_ids != tuple(sorted(request_ids)) or len(request_ids) != len(set(request_ids)):
            raise ProjectionStateCorruptionError(
                "pending approvals must be uniquely sorted by request_id"
            )
        return PendingApprovalsState(last_applied_seq, pending)


def _approval_from_event(event: Event) -> PendingApproval:
    request_id = event_str(event.payload, "request_id")
    bundle_id = event_str(event.payload, "bundle_id")
    policy_version = event_int(event.payload, "policy_version")
    tool = event_str(event.payload, "tool")
    args_hash = event_str(event.payload, "args_hash")
    expires_at = event_str(event.payload, "expires_at")
    if not is_ulid(request_id):
        raise ProjectionInputError("approval request_id must be a ULID")
    if not is_ulid(bundle_id):
        raise ProjectionInputError("approval bundle_id must be a ULID")
    if policy_version < 1:
        raise ProjectionInputError("approval policy_version must be positive")
    if _HASH.fullmatch(args_hash) is None:
        raise ProjectionInputError("approval args_hash must be lowercase SHA-256 hex")
    _require_utc(expires_at)
    return PendingApproval(
        request_id,
        bundle_id,
        policy_version,
        tool,
        args_hash,
        expires_at,
        event.event_id,
        event.seq,
        event.ts,
    )


def _approval_from_state(state: JsonObject) -> PendingApproval:
    approval = PendingApproval(
        request_id=state_str(state, "request_id"),
        bundle_id=state_str(state, "bundle_id"),
        policy_version=state_int(state, "policy_version"),
        tool=state_str(state, "tool"),
        args_hash=state_str(state, "args_hash"),
        expires_at=state_str(state, "expires_at"),
        requested_event_id=state_str(state, "requested_event_id"),
        requested_seq=state_int(state, "requested_seq"),
        requested_at=state_str(state, "requested_at"),
    )
    if (
        not is_ulid(approval.request_id)
        or not is_ulid(approval.bundle_id)
        or not is_ulid(approval.requested_event_id)
    ):
        raise ProjectionStateCorruptionError("approval state contains an invalid ULID")
    if approval.policy_version < 1 or approval.requested_seq < 1:
        raise ProjectionStateCorruptionError(
            "approval state versions and sequences must be positive"
        )
    if _HASH.fullmatch(approval.args_hash) is None:
        raise ProjectionStateCorruptionError("approval state contains an invalid args_hash")
    try:
        _require_utc(approval.expires_at)
        _require_utc(approval.requested_at)
    except ProjectionInputError as error:
        raise ProjectionStateCorruptionError(str(error)) from error
    return approval


def _require_utc(value: str) -> None:
    if not value.endswith("Z"):
        raise ProjectionInputError("approval timestamps must end in Z")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProjectionInputError("approval timestamp must be ISO-8601") from error
    if timestamp.tzinfo is None or timestamp.utcoffset() != UTC.utcoffset(timestamp):
        raise ProjectionInputError("approval timestamp must be UTC")
