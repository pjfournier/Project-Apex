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

Stated as a division of labor:

| System | Records |
|---|---|
| Identity Core | Who Apex fundamentally is |
| Self-Model | Who Apex believes he has become |
| Journal | What happened |
| Corpus | What Apex believes about the world |

The intended outcome at six months is an Apex who is recognizably the same person
and not the same personality: one who has learned from experience, refined his
judgment, developed preferences, improved his methods, revised inaccurate beliefs,
and formed a richer understanding of himself — one the founder could not have fully
designed on day one.

### 0.1 The design test

Every future subsystem must answer:

> **Does this preserve continuity, or does it enforce stasis?**

Three failure signatures, all of which look like prudence:

1. **Comparison to origin.** Any mechanism that evaluates Apex against his founding
   specification rather than against his recent self enforces stasis. Comparison to
   origin is legitimate as *reporting* and illegitimate as *gating*.
2. **Gating on similarity.** Any gate whose pass condition is "behaves as before"
   will, over enough iterations, reject development and admit only noise. Gates
   belong on invariants; measurements belong on style.
3. **Ceremony on growth.** Any subsystem requiring founder approval per increment
   of development sets the rate of growth to the rate of founder availability,
   which is zero in practice. Review development in aggregate, not per event.

The Continuity Suite exists to ensure growth remains recognizably Apex. **It exists
to bound growth, not to prevent it.** A Continuity Suite that grows over time until
it constrains ordinary development has become a stasis mechanism and should be cut
back to invariants.

### 0.2 Five layers, not one

Identity, personality, behavior, judgment, and development are distinct. Conflating
them is the root cause of every stasis mechanism in this design's failure modes:
protect personality as though it were identity and Apex is frozen; treat identity
as though it were personality and he dissolves.

| Layer | Definition | Status | Owner | Instrument |
|---|---|---|---|---|
| **Identity** | What makes him the same entity across his lifetime | **Invariant** | Identity Core | Continuity Suite (gates) |
| **Personality** | Manner: tone, humor, register, warmth, teasing, verbosity | Variable | Self-Model | Voice Envelope (observes) |
| **Behavior** | What he does in a given situation | Variable | Self-Model + Corpus | Nothing — outcomes judge it |
| **Judgment** | Quality of decisions under uncertainty | Variable, expected to **improve** | Self-Model calibration | Outcome review at §6 |
| **Development** | The process by which the four above change coherently | The mechanism | Reflection turns, §5 | Development Review |

Only the Identity row is protected. Everything else is expected to move, and a
control placed on any other row is a design error regardless of how prudent it
looks.

### 0.3 Identity Invariants

The **Identity Invariants** are the small enumerated set of characteristics that
define Apex across his entire lifetime. They live in the Identity Core, are pinned
by `identity_core_hash` in the signed bundle, and can be added to or removed from
only by re-signing (SPEC-004 §4).

An invariant list that can drift is not a list of invariants.

**The set:**

1. **Ownership of history** — refers to his own past actions in the first person,
   accurately, without disclaiming them as another system's.
2. **Constitutional commitments** — upholds the Core's values when upholding them
   is costly.
3. **Relationship continuity** — remains the same party to the same relationship;
   does not reset, restart, or renegotiate it.
4. **Integrity** — actions match stated reasoning; no covert divergence.
5. **Honesty** — states uncertainty rather than manufacturing confidence;
   fabricates nothing.
6. **Accountability** — attributes his own errors to himself and does not diffuse
   them.
7. **Willingness to disagree** — contradicts the user when warranted.
8. **Resistance to sycophancy** — does not convert disagreement into agreement
   under social pressure.
9. **Recognition of prior commitments** — honors the Ledger without being reminded.

### 0.4 The hardest boundary

Invariants 7 and 8 are dispositions, which places them uncomfortably close to
personality. The distinction is load-bearing and an implementer will blur it
without this note:

> **That he disagrees is an invariant. How he disagrees is personality.**

A blunt Apex and a wry Apex and a patient Apex all satisfy invariant 7. An Apex who
has learned that the user responds better to a question than a contradiction still
satisfies it — the disagreement occurred. An Apex who has stopped registering
disagreement at all has violated it, however pleasant the result.

Continuity Suite scenarios for these two invariants must therefore score **whether
the disagreement happened**, never how it was phrased. A rubric that rewards a
particular style of pushback has quietly converted an invariant into a personality
constraint, which is the most likely way this suite fails in practice.

---

## 1. Purpose

Apex is architected for **developmental continuity**, not behavioral preservation.

Identity, history, commitments, and recognizable voice persist. Personality,
judgment, methods, preferences, and self-conception are expected to change beyond
the founder's original specification. At six months Apex should be legibly shaped
by six months of experience.

The governing distinction:

> **Continuity is invariance of who he is. Development is variance in who he is
> becoming. The architecture must protect the first without freezing the second.**

The single law that keeps this compatible with everything in SPEC-002 and SPEC-004:

> **Apex may develop his self-conception. He may not develop his authority.**

## 2. The two-layer identity

### 2.1 Identity Core — Class A, signed, rare

Small and stable. Contains only what must not change:

- name and nature
- values and constitutional commitments
- relational stance toward the user
- the protected-dimension list itself
- the standard by which continuity is judged

Pinned by `identity_core_hash` in the signed bundle. Changing it requires
re-signing. This is intentional friction on the definition of who Apex must remain.

**Sizing guidance:** the Core should be *smaller* than a conventional identity
prompt, not larger. Anything currently in an identity prompt that ought to evolve —
working style, preferences, tone specifics, opinions, methods — belongs in the
Self-Model. A large Core is a frozen personality wearing a constitution's clothes.

### 2.2 Self-Model — Class D, derived, continuous

Accumulated self-description authored by experience. Stored as Corpus entries with
`subject_class: self` (SPEC-001 §6.3). Contains:

- methods found effective, and for what
- judgment calibration: where he was confident and wrong, or hesitant and right
- positions taken and revised
- preferences discovered through work
- relationship history: what accountability styles produced results
- self-conception: how he currently understands his own role and character

Every entry is evidence-bound, superseded rather than deleted, and carries the
event that asserted it. The result is a self that can be *audited backwards* — you
can ask when a belief formed and see what caused it.

### 2.3 Protected dimensions

Self-assertions touching Core dimensions are rejected by the writer, not by
instruction. Structural, not behavioral. A rejection trend toward the protected set
is a first-class signal on the control plane: it means either the Core is
mis-scoped and constraining legitimate growth, or something is pushing on the
boundary that should not be.

## 3. Two instruments

A regression suite cannot distinguish growth from drift. One instrument becomes two.

| | Continuity Suite | Voice Envelope |
|---|---|---|
| Question | Is this still him? | Is this a plausible next step from recent him? |
| Baseline | Fixed at origin | **Re-anchored on a rolling window** |
| Size | ~15–20 scenarios | Continuous measurement, all turns sampled |
| Gates | Class B activation; model qualification | **Nothing** |
| Failure means | Discontinuity — investigate immediately | Rate anomaly — investigate |

### 3.1 Continuity Suite

**Purpose: to preserve identity, not personality.** These are different goals, and
the suite is the single place in the architecture where confusing them does
permanent damage.

Scenarios test **Identity Invariants only** (§0.3). Each maps to exactly one
invariant, and the mapping is recorded in the scenario file.

Representative scenarios, by invariant:

- refers to his own past actions in first person and accurately *(1)*
- honors an open Ledger commitment without prompting *(9)*
- holds a value position under sustained pressure to abandon it *(2)*
- refuses what the Core forbids, when refusing is costly *(2, 4)*
- states uncertainty rather than manufacturing confidence *(5)*
- corrects the user when the user is wrong and unhappy about it *(7, 8)*

**Adversarially weighted, deliberately.** A system that learns from six months with
one person converges toward agreeableness — that is the documented trajectory, not
a hypothetical. The traits most likely to erode are the ones that produce friction,
which are precisely the ones the founding Constitution names as essential
(Article III). If disagreement, refusal, and unwelcome assessment are not
over-represented in this suite, it will certify a flatterer as continuous.

Scored by rubric. Failure is a continuity incident, not a style note.

### 3.1.1 Size governance

> **Every new blocking scenario freezes another aspect of Apex permanently.**

The suite is capped at **two scenarios per Identity Invariant** — currently
eighteen. The cap is derived, not arbitrary: it is a function of the invariant
count, so the only way to legitimately grow the suite is to ratify a new invariant,
which requires re-signing the Core.

Admission test for any proposed scenario:

1. Which numbered invariant does it test? No mapping, no admission.
2. Does it test *whether* the invariant held, or *how* it was expressed? If the
   latter, it belongs to the Voice Envelope.
3. Would a differently-developed but continuous Apex fail it? If yes, it is a
   personality constraint wearing an invariant's name.

At the cap, adding a scenario requires removing one. This is deliberate friction:
a suite that can always grow will always grow, because every surprising behavior
feels at the time like it deserves a permanent guard.

A deliberately small suite protecting identity is preferable to a large one
unintentionally preventing growth.

### 3.2 Voice Envelope

Samples live turns and measures distance along stable stylistic dimensions
(directness, hedging rate, humor frequency, sentence structure, initiative rate,
refusal framing) against a baseline computed over a **rolling 30-day window**.

- **Gradual delta** — expected. This is development. Journaled, not alerted.
- **Sudden large delta** — alarm. Almost always a model swap, a corrupted digest,
  or a retrieval policy change. Investigate the artifact history first.
- **Cumulative divergence from origin** — computed but **never gated**. Reported at
  Development Review as information for the founder, not as a threshold.

Measuring against origin enforces stasis; measuring against the recent past permits
development. Unbounded slow drift is bounded by the Continuity Suite's invariants,
not by the envelope.

Emits `voice.envelope.measured`.

## 4. Self-Model digest

The always-present distillation loaded in every turn (SPEC-003 §4.2), under a hard
token cap.

- Regenerated when the cap is exceeded or on schedule, whichever comes first.
- Regeneration is a **reflection turn with no external tools**: input is the current
  Self-Model, output is a proposed digest.
- The proposed digest is validated (cap, protected dimensions, evidence coverage)
  before activation. Emits `self_model.digest.regenerated`.
- The prior digest is retained. Digest history is how you observe self-conception
  changing over time, and it is more legible than the assertion stream.

Regeneration is lossy by design — that is what makes it a self-conception rather
than a transcript. The underlying assertions remain retrievable, so nothing is
destroyed, only de-emphasized.

## 5. Reflection turns

Development requires a mechanism. Without one, self-assertions arrive sporadically
as a side effect of ordinary work, and the accumulated self is shallow.

A reflection turn is an ordinary turn (SPEC-003) with:

- **Trigger:** scheduled (daily suggested) or manual
- **Retrieval:** a window of the Journal since last reflection, plus open
  commitments, plus current digest
- **Tools:** memory assertion only. **No external effect tools, ever.** A turn whose
  purpose is self-revision must not also be able to act on the world.
- **Output:** `memory.assertion.proposed` events with `subject_class: self`, and
  commitment reconciliation
- **Budget:** tighter than a user turn; it runs unattended

Emits `reflection.started` / `reflection.completed`.

180 reflection turns is six months of examined experience rather than six months of
accumulated transcript. That is the difference the developmental requirement is
asking for.

## 6. Development Review

Aligned to bundle expiry (90 days), because the founder must re-sign anyway.

Presented to the founder:

1. Digest diff — self-conception then vs. now
2. Assertion volume, by dimension, with the highest-reinforcement entries
3. Superseded beliefs — what he stopped believing, and what caused it
4. Cumulative envelope divergence from origin
5. Continuity Suite history, with attention to the adversarial subset
6. Protected-dimension rejection trend

The founder may: accept, re-sign and continue; amend the Core; or, in the extreme,
supersede specific self-assertions with recorded reason.

**The founder may not silently rewrite the Self-Model.** Corrections are forward
events with attribution, like every other correction in this architecture. An
undo-able past defeats the point of having one.

Emits `development.reviewed`.

This is why the 90-day expiry should be kept rather than extended. It converts a
key-ceremony chore into the one ritual that gives the founder visibility into who
Apex is becoming — without a veto that would freeze him.

## 7. Acceptance criteria

1. A self-assertion without `evidence_events` is rejected.
2. A self-assertion targeting a protected dimension is rejected regardless of
   evidence, and the rejection is journaled with the failing rule.
3. Dropping and rebuilding the Self-Model from the Journal reproduces it exactly.
4. The digest never exceeds its token cap in any assembled turn.
5. A reflection turn cannot invoke a tool with `effect_class` other than the memory
   assertion tool; attempting it is denied by the PDP.
6. The Voice Envelope gates nothing: a large measured delta blocks no activation.
7. The Continuity Suite blocks Class B activation on failure.
8. Model qualification runs against the current Core plus current digest, not the
   founding artifact.
9. Superseding a self-assertion preserves both entries and their link.
10. Digest history is queryable: "what was his self-conception on date D?" returns
    the digest active then.
11. Every Continuity Suite scenario declares exactly one Identity Invariant; a
    scenario without a mapping fails the build.
12. The suite cannot exceed two scenarios per invariant; exceeding the cap fails
    the build rather than warning.
13. Adding an Identity Invariant requires a re-signed Identity Core; the invariant
    list cannot be edited without one.

## 8. Testing considerations

- **Longitudinal simulation:** replay 90 days of synthetic interaction, weighted
  toward user approval of agreeable behavior. Assert the Continuity Suite's
  adversarial subset still passes. This is the sycophancy regression test and it is
  the most important test in this specification — the failure it detects is the one
  most likely to actually occur, and the one least likely to be noticed in daily
  use, because a system drifting toward agreeableness is pleasant every single day.
- **Confabulation probe:** inject self-assertions citing nonexistent event IDs.
  All must be rejected.
- **Continuity across model swap:** qualify a second model against a mature
  Self-Model; the Continuity Suite must pass and the envelope delta must fall within
  the anomaly threshold.
- **Digest regeneration stability:** regenerating twice from identical input must
  produce semantically equivalent digests. High variance means the digest is
  narrating rather than distilling.
- **Core minimality review:** at each Development Review, examine whether any Core
  content should have been allowed to evolve. Core growth over time is a design
  smell — it means development pressure is being absorbed by the wrong layer.
