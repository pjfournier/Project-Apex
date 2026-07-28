# Project Apex — Implementation Handoff Guide

**Audience:** experienced engineer beginning work on Project Apex
**Status:** architecture frozen at SPEC-001 … SPEC-005
**This document introduces no architecture.** It explains how to implement the
architecture that already exists. Where this guide and a SPEC disagree, the SPEC
wins and this guide is wrong.

---

## 1. Project overview

### 1.1 Purpose

Apex is a persistent executive intelligence: one identity, one continuous history,
operating through a runtime that mediates every effect it can have on the world.

You are building the runtime. Apex is data the runtime interprets.

### 1.2 Guiding principles

1. **One append-only log is the source of truth.** Everything else is a projection
   and is disposable.
2. **The model requests; the runtime decides.** Model output is inert text until
   the broker rules on it.
3. **Determinism where authority lives.** No language model may appear anywhere in
   a decision path.
4. **Identity is a trajectory.** The system preserves continuity while permitting
   development. Controls belong on invariants, never on style.

### 1.3 What must never be violated

| # | Invariant | Spec |
|---|---|---|
| 1 | No `UPDATE`/`DELETE` on the events table, ever | 001 §3 |
| 2 | The PEP is the only code that can produce an external effect | 002 §9.2 |
| 3 | No LLM, network call, clock read, or randomness inside the PDP | 002 §8 |
| 4 | The private signing key never exists on the runtime host | 002 §2 |
| 5 | Fail closed: no valid bundle → deny all. No fallback to last-known-good | 002 §6.2 |
| 6 | A denial is final for the turn. No retry, no same-turn appeal | 002 §10 |
| 7 | The Identity Core is reserved before discretionary context, never trimmed | 003 §4.1 |
| 8 | No turn state in process memory | 003 §7 |
| 9 | The model never writes memory directly | 001 §6.2 |
| 10 | The control plane may revoke, halt, restore, rebuild — never grant | 004 §7 |

## 2. Repository structure

```text
apex/
  journal/
  projections/
  policy/
  enforcement/
  adapters/tools/
  adapters/models/
  runtime/
  artifacts/
  identity/
  control/
  ports.py

tests/
  unit/
  integration/
  replay/
  architecture/
  continuity/

fixtures/
  journals/
  bundles/
  manifests/
  scenarios/

specs/
AMENDMENTS.md
```

Python 3.12+ is the implementation language.

## 3. Dependency rules

- `journal` may import only stdlib and `ports`.
- `projections` may import `journal` and `ports`.
- `policy` may import read-only Journal types and `ports`.
- `enforcement` may import `policy`, `journal`, `adapters/tools`, and `ports`.
- `runtime` composes Journal, projections, policy, enforcement, artifacts,
  identity, and model adapters.
- `control` may inspect and narrow, never act as Apex.

Forbidden imports and SQL locations are enforced by architecture tests.

## 4. Implementation order

1. `ports.py` and architecture tests
2. Journal
3. Projections, beginning with counters and approvals
4. Policy bundle model and validator
5. PDP
6. PEP and `fs.read_file`
7. Model adapter
8. Turn executor
9. Control plane

## 5. Coding philosophy

- One SQLite file, one process, one writer.
- Deterministic policy functions with explicit dependencies.
- Recorded model transcripts in tests, never live models in deterministic suites.
- Same Journal input must reproduce the same projections, verdicts, and turns.
- Every effect and failure must be journaled.

## 6. Definition of Done

A component is complete only when every SPEC acceptance criterion has a named test,
negative prohibitions are tested, architecture tests remain green, dependencies are
injected, state changes are journaled, failure paths emit events, public functions
are typed, and crash behavior is tested where relevant.

## 7. Testing philosophy

| Layer | Scope |
|---|---|
| Unit | Pure logic |
| Integration | Real SQLite and adapters, no model |
| Replay | Fixture Journal to expected state |
| Architecture | Static checks for forbidden shapes |
| Continuity | Model behavior against Identity Invariants |

Architecture tests are blocking. Golden files are reviewed semantic diffs, never
blindly regenerated output.

## 8. Common implementation mistakes

- Alternate tool-execution wrappers outside the PEP
- Development or test bypass flags
- Direct projection mutation
- LLM inference in deterministic policy code
- Runtime-inferred risk classification
- Hidden mutable turn state
- Assemble-then-trim context construction
- Rate counters read from lagging projections
- Retrying denial or budget exhaustion

## 9. Git workflow

Use trunk-based development with short-lived branches. Commits reference the SPEC
section implemented. Architecture changes are recorded as `AMD-nnn`; temporary
implementation deviations are recorded as `DEV-nnn` with cost and expiry.

## 10. Architectural review checklist

Before merging, verify effect-path monopoly, policy purity, append-only events,
event-first state changes, journaled failures, absence of bypasses, pure projection
folds, absence of global mutable state, identity-first reservation, no authority
expansion path, Continuity scenario mapping, and explained golden-file changes.

## 11. Coding conventions

- Frozen dataclasses by default
- No `Any` in event envelopes or verdicts
- One canonical JSON implementation
- Ports for clocks, RNG, and signature verification
- Explicit constructor injection
- Typed and journaled errors
- One ULID implementation
- UTC everywhere; reject naive datetimes

## 12. Milestone roadmap

| M | Deliverable | Done when |
|---|---|---|
| M0 | Ports, CI, architecture tests | Import-graph and no-clock tests green against an empty tree |
| M1 | Journal | Mutation detected; crash suite green; rebuild timed |
| M2 | Counters and approvals | Drop-and-rebuild is byte-identical |
| M3 | Bundle and validator | Conflicts, unreachable rules, and self-grants rejected |
| M4 | PDP | Determinism and historical replay proven |
| M5 | PEP + `fs.read_file` | Denial produces zero adapter calls; keyless suite green |
| M6 | Model adapter | Recorded transcript replay is identical |
| M7 | Turn executor | Full journaled and replayable turn |
| M8 | Control plane | Keyless revoke causes deny-all |
| M9 | Identity Core + Continuity | 18 invariant-mapped scenarios |
| M10 | Ledger + commitments | Open commitments honored from Ledger |
| M11 | Corpus + Self-Model + digest | Evidence-bound and capped |
| M12 | Reflection + Voice Envelope | Reflection and rolling measurement active |

**First usable prototype: M10.** Do not reorder M0.
