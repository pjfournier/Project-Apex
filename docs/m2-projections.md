# M2 Projections

M2 implements the two projections required before policy work:

- `pending_approvals`, derived from `approval.*`
- `challenge_counters`, derived from `policy.challenged`

The Journal remains authoritative. Projection checkpoints are Class-D artifacts:
derived, disposable, and fully reconstructable from sequence zero.

## Architecture

Every projection is a pure fold:

```text
new_state = fold(previous_state, journal_event)
```

State dataclasses are frozen and contain only tuples and scalar values. A fold
receives one immutable `Event` and returns a new state. Events older than or equal
to `last_applied_seq` are idempotent re-deliveries. A forward sequence gap is an
error because accepting it would silently produce incomplete state.

`ProjectionRunner` provides:

- `rebuild()` — starts empty, replays the full Journal, then atomically publishes
  one checkpoint.
- `catch_up()` — verifies the current checkpoint and folds only newer events.
- `state()` — returns decoded, validated checkpoint state.

`ProjectionService` statically registers the M2 projections and exposes
`rebuild(name)`, `rebuild_all()`, `catch_up(name)`, and typed query methods.

## Persistence and recovery

The Journal stores projection checkpoints as opaque canonical JSON in
`projection_snapshots`. SQL remains exclusively in `apex/journal/store.py`;
projection modules never write storage directly.

Each checkpoint contains:

- projection name
- `last_applied_seq`
- canonical JSON state
- SHA-256 of that exact canonical representation

Publishing uses one SQLite transaction. If folding is interrupted, the prior
checkpoint remains intact. Restart recovery calls `catch_up()` or performs a full
rebuild. Snapshot hash or codec failures are explicit corruption errors.

Online rebuilds read a stable SQLite snapshot and publish when complete. Events
committed after that read began are allowed to leave the rebuilt projection
temporarily behind the Journal, as SPEC-001 §6.1 permits. A subsequent `catch_up()`
closes the gap.

## Event payload contracts

The specifications name these events but do not enumerate every payload field.
M2 uses the minimum deterministic contracts required by SPEC-001 and SPEC-002.
Additional fields remain allowed for later milestones.

### `approval.requested`

```json
{
  "request_id": "ULID",
  "bundle_id": "ULID",
  "policy_version": 1,
  "tool": "fs.write_file",
  "args_hash": "64 lowercase SHA-256 hex characters",
  "expires_at": "UTC ISO-8601 ending in Z"
}
```

`approval.granted`, `approval.denied`, `approval.expired`, and
`approval.invalidated` require the correlated `request_id`.

### `policy.challenged`

```json
{
  "decision_id": "ULID",
  "reasoning": "Why the denial is being challenged",
  "bundle_id": "ULID",
  "policy_version": 1,
  "rule_id": "r-fs-write"
}
```

Counts key on `(bundle_id, policy_version, rule_id)`. This prevents equal version
numbers from unrelated bundles sharing a counter.

## Public example

```python
from pathlib import Path

from apex.journal import JournalStore
from apex.projections import ProjectionService

journal = JournalStore(Path("apex.db"), injected_clock)
projections = ProjectionService(journal)

projections.rebuild_all()
pending = projections.pending_approvals()
count = projections.challenge_counters().count(bundle_id, version, rule_id)
```

The caller owns the Journal and closes it when finished.

## Extension contract

A future projection implements the `Projection[StateT]` protocol:

1. Choose a stable lowercase persistence name.
2. Define a frozen state carrying `last_applied_seq`.
3. Implement `initial`, pure `fold`, deterministic `encode`, and strict `decode`.
4. Advance sequence for every Journal event, including irrelevant events.
5. Add the projection explicitly to `ProjectionService`; there is no dynamic
   plugin registry or mutable global.
6. Add a reviewed golden replay fixture and corruption/recovery tests.

Ledger, Corpus, Self-Model, and working-set projections remain outside M2.

## Operational warning for future policy work

SPEC-001 permits lagging readers, but a lagging challenge counter must never be
used to authorize an additional challenge. M4 must call `catch_up` in the
serialized decision path and pass the resulting snapshot into the pure PDP.
Telemetry readers may intentionally tolerate lag.

## Verification

- `make test-m2` runs focused unit, integration, and golden replay coverage.
- `make test-replay` runs checked-in replay fixtures.
- `make test-volume` generates one million synthetic Journal envelopes in a
  temporary database and asserts both M2 projections rebuild within the configured
  incident-recovery threshold.

The volume harness creates no repository artifact and removes its temporary
database automatically.

Baseline measured on 2026-07-28 using Windows, Python 3.14.6, and the project-local
virtual environment: both projections rebuilt 1,000,000 synthetic Journal events
in **44.865 seconds**, below the 120-second incident-recovery threshold.
