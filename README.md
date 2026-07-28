# Project Apex

Project Apex is a persistent executive intelligence built around an immutable
Journal, deterministic policy enforcement, and replayable derived state.

Implemented milestones:

- **M0:** Python foundation, CI, typed ports, and architecture gates.
- **M1:** Append-only SQLite Journal, immutable event envelopes, canonical hashing,
  causal traversal, corruption detection, and crash recovery.
- **M2:** Deterministic pending-approval and challenge-counter projections with
  canonical durable checkpoints, replay, catch-up, and online rebuild support.

See [M2 Projections](docs/m2-projections.md) for the projection API, event payload
contracts, operational model, examples, and extension rules.
