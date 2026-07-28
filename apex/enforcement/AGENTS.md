# AGENTS.md — apex/enforcement/

This module is the **only** code in the repository permitted to import
`adapters/tools`. That monopoly is the sole reason effects in this system are
bounded.

## Rules

- `pep.py` holds every adapter reference. Do not re-export them. Do not add a
  convenience wrapper elsewhere that calls through — a legal import in a second
  location still creates a second call site.
- Execute only on a verdict of `allow` or `notify`, produced by the PDP in this
  same request. Never construct a verdict here.
- Hash arguments at decision time; refuse execution if they differ at execution
  time.
- `confirm` never executes without a matching signed `approval.granted`, and never
  after the bundle version has changed.
- Idempotency keys are required where the manifest says so. Replaying a key returns
  the recorded result; it does not re-execute.
- Emit `tool.result` or `tool.failed` for every attempt. A silent return is a bug
  of the same severity as data loss.

## Never

- A `force`, `bypass`, or test-only execution path.
- Computing a tool's risk tier. It is declared in the manifest and pinned by hash;
  read it, never derive it.

Reference: SPEC-002 §9.
