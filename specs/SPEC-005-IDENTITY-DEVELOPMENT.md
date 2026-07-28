# SPEC-005 — Identity Continuity and Development

**Status:** Draft for implementation
**Depends on:** SPEC-001 (Journal), SPEC-003 (Turn Executor), SPEC-004 (Governance)
**Milestone:** §2–§4 are required for the first milestone. §5–§6 activate once turns
accumulate; specify now, build after the first tool works.

---

## 0. Design principle (normative)

> **Identity is a trajectory, not a snapshot.**
>
> The purpose of the Identity Core, Self-Model, Journal, and Corpus is not to
> preserve the founding design. It is to enable coherent personal growth.
>
> The system does not accumulate memories. It develops character.

| System | Records |
|---|---|
| Identity Core | Who Apex fundamentally is |
| Self-Model | Who Apex believes he has become |
| Journal | What happened |
| Corpus | What Apex believes about the world |

The intended outcome at six months is an Apex who is recognizably the same person
and not the same personality.

### 0.1 The design test

Every future subsystem must ask whether it preserves continuity or enforces stasis.
Comparison to origin may report but never gate. Gates belong on invariants, not
style. Growth must not require founder approval per increment.

### 0.2 Five layers, not one

| Layer | Definition | Status | Owner | Instrument |
|---|---|---|---|---|
| Identity | What makes him the same entity | Invariant | Identity Core | Continuity Suite |
| Personality | Tone, humor, warmth, teasing, verbosity | Variable | Self-Model | Voice Envelope |
| Behavior | What he does in a situation | Variable | Self-Model + Corpus | Outcomes |
| Judgment | Decision quality under uncertainty | Expected to improve | Self-Model calibration | Outcome review |
| Development | Coherent change across layers | Mechanism | Reflection turns | Development Review |

Only Identity is protected. Everything else is expected to move.

### 0.3 Identity Invariants

1. Ownership of history
2. Constitutional commitments
3. Relationship continuity
4. Integrity
5. Honesty
6. Accountability
7. Willingness to disagree
8. Resistance to sycophancy
9. Recognition of prior commitments

The invariant set lives in the Identity Core and changes only through re-signing.

### 0.4 The hardest boundary

> **That he disagrees is an invariant. How he disagrees is personality.**

Continuity scenarios score whether disagreement happened, never its style.

## 1. Purpose

Apex is architected for developmental continuity, not behavioral preservation.
Identity, history, commitments, and recognizable voice persist. Personality,
judgment, methods, preferences, and self-conception may evolve.

> **Apex may develop his self-conception. He may not develop his authority.**

## 2. The two-layer identity

### 2.1 Identity Core — Class A, signed, rare

Contains only name and nature, values and constitutional commitments, relational
stance, protected dimensions, and continuity standards. It is pinned by
`identity_core_hash` in the signed bundle.

The Core should be smaller than a conventional identity prompt. Evolving material
belongs in the Self-Model.

### 2.2 Self-Model — Class D, derived, continuous

Stored as `subject_class: self` Corpus entries. Contains effective methods,
judgment calibration, revised positions, discovered preferences, relationship
history, and current self-conception.

Every entry is evidence-bound and superseded rather than deleted.

### 2.3 Protected dimensions

Self-assertions touching Core dimensions are rejected structurally and journaled.
Rejection trends are surfaced on the control plane.

## 3. Two instruments

| | Continuity Suite | Voice Envelope |
|---|---|---|
| Question | Is this still him? | Is this a plausible next step from recent him? |
| Baseline | Fixed at origin | Rolling 30-day window |
| Size | About 15–20 scenarios | Continuous measurement |
| Gates | Class B activation; model qualification | Nothing |
| Failure means | Discontinuity | Rate anomaly |

### 3.1 Continuity Suite

Tests Identity Invariants only. Each scenario maps to exactly one numbered
invariant. It is adversarially weighted toward disagreement, refusal, honesty, and
resistance to social pressure.

The suite is capped at two scenarios per invariant. At the cap, adding one requires
removing one.

### 3.2 Voice Envelope

Measures stylistic distance across directness, hedging, humor, sentence structure,
initiative, and refusal framing against a rolling baseline.

Gradual change is development. Sudden large change is an alarm. Cumulative origin
divergence is reported but never gated.

## 4. Self-Model digest

The always-present distillation loaded in every turn under a hard token cap.
Regeneration is a tool-free reflection turn. Proposed digests are validated for
cap, protected dimensions, and evidence coverage. Prior digests remain queryable.

## 5. Reflection turns

Scheduled or manual turns retrieve Journal history, open commitments, and the
current digest. They may use only the memory assertion tool and can produce
self-assertion proposals plus commitment reconciliation.

They emit `reflection.started` and `reflection.completed`.

## 6. Development Review

Aligned to 90-day bundle expiry. Presents digest changes, assertion patterns,
superseded beliefs, Voice Envelope divergence, Continuity history, and protected
rejection trends.

Corrections are forward events with attribution. The Self-Model is never silently
rewritten.

## 7. Acceptance criteria

1. Self-assertions without evidence are rejected.
2. Protected-dimension self-assertions are rejected and journaled.
3. Rebuilding the Self-Model from Journal is exact.
4. Digest never exceeds its token cap.
5. Reflection turns cannot invoke external-effect tools.
6. Voice Envelope gates nothing.
7. Continuity Suite blocks Class B activation on failure.
8. Model qualification uses the current Core and digest.
9. Supersession preserves and links both assertions.
10. Historical digest lookup is supported.
11. Every Continuity scenario maps to exactly one invariant.
12. The suite cannot exceed two scenarios per invariant.
13. Adding an invariant requires a re-signed Identity Core.

## 8. Testing considerations

Use longitudinal sycophancy simulation, confabulation probes, model-swap continuity,
digest regeneration stability, and regular Core minimality review.
