# AGENTS.md — apex/policy/

Everything here is a **pure function**. This is the decision layer; if it becomes
impure, the system loses replayability and auditability at once.

## Rules

- No imports of `datetime`, `random`, `os`, `requests`, any model SDK, `runtime`,
  or `adapters/*`. The architecture test enforces this; do not add an exemption.
- Time, IDs, and signature verification arrive as arguments via `ports`.
- `decide()` must return identical output for identical input, forever, including
  `matched_rule_id`.
- Rate-limit counters are passed in as a transactionally-read snapshot. Never fetch
  them here.
- Denial is monotonic: no rule may un-deny. Explicit deny beats any allow.
- No bundle reaches this module unvalidated. If you need a shortcut for a test,
  build a valid fixture bundle instead.

## Never

Any form of "just ask the model whether this is safe." There is no version of that
which is acceptable, including behind a flag, including in tests.

Reference: SPEC-002 §6–§8.
