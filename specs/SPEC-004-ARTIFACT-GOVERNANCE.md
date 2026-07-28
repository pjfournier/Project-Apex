# SPEC-004 — Artifact Governance

**Status:** Draft for implementation
**Depends on:** SPEC-001 (Journal), SPEC-002 (PDP/PEP)
**Scope note:** Covers only artifacts required by the first milestone. Agent
templates and schedule definitions are deferred with their consuming subsystems.

---

## 1. Purpose

Defines who may propose, validate, evaluate, sign, activate, roll back, and revoke
each class of artifact, and what the Journal records at each step.

Without this, "versioned artifact" is a filing convention. With it, it is a control.

## 2. Architectural basis: single signature, pinned composite

**The policy bundle is the only externally signed artifact.** Everything else
bearing authority is pinned into it by hash.

This gives one root of trust, prevents unratified composites, supports atomic
rollback, and converts authority classification into hash comparison.

Changing the Identity Core requires re-signing a bundle. Early development uses a
short-expiry `dev` bundle profile, never a second signing path.

## 3. Artifact classes

| Class | Members | Ceremony |
|---|---|---|
| **A — Signed** | Policy bundle and pinned authority surface | External signature + static validation |
| **B — Approved** | Retrieval policy, model selection | Control-plane approval + Continuity Suite pass |
| **C — Repo-versioned** | Constitution text, Continuity Suite, Voice Envelope harness, manifest metadata | Code review |
| **D — Derived** | Corpus, Self-Model, digest, Ledger, approvals, counters, indexes, qualification records, measurements | None; rebuildable from Journal |

### 3.1 Deviations from the proposed hierarchy

The Constitution is Class C and hash-pinned, the Identity Core is pinned in the
bundle, grants are part of the bundle, authority-relevant manifest fields are
hash-pinned, runtime compatibility is a field, behavioral harnesses are repo code,
qualification records are derived evidence, and agent/schedule artifacts are
deferred.

### 3.2 Why the Self-Model is Class D

The Self-Model changes frequently and must not require ceremony per assertion. Its
safety comes from evidence binding, structurally protected dimensions, absence of
an authority path, and replayability from the Journal.

## 4. Governance matrix

Class A requires external signature and validation. Class B requires approval and a
blocking Continuity Suite pass. Class C is governed by code review. Class D is
derived and rebuilt.

The control plane may activate valid artifacts, perform non-expanding rollback, and
revoke authority. It may never grant or sign.

### 4.1 Asymmetry of behavioral evaluation

Class B activation is blocked by Continuity Suite failure. Class A activation is
not. Behavioral evaluation must not veto the owner's signed authority decision.

The Voice Envelope never gates anything.

### 4.2 Drift on an unchanged artifact

Continuity failure without an artifact change is an alarm, not an automatic
rollback. Investigate provider or runtime changes.

### 4.3 Model qualification targets the current self

Candidate models are qualified against the current Identity Core, current digest,
and recent Voice Envelope baseline, not against the founding state.

## 5. Activation sequence

```
draft → artifact.proposed
      → static validation → artifact.validated | artifact.rejected
      → behavioral evaluation → artifact.evaluated
      → external signing for Class A
      → control-plane activation → artifact.activated
      → pointer swap and in-flight handling
```

Rejections are journaled with the same weight as activations.

## 6. Rollback

- Class A rollback is permitted without a new signature only when authority is
  narrowing or neutral.
- Class B rollback is permitted to a prior valid version.
- Emergency response uses revocation, not rollback.

## 7. Control plane limits

The control plane may revoke, halt scheduling, abort turns, restore a non-expanding
prior pointer, rebuild projections, and read stores.

It may not create grants, sign artifacts, activate unsigned authority expansion,
write Journal events as Apex, or mutate artifacts in place.

## 8. Acceptance criteria

1. Identity hash mismatch prevents loading and turn admission.
2. Unknown manifest hashes fail bundle validation.
3. Retrieval scopes outside the bundle fail validation.
4. Retrieval policy activation is blocked by Continuity Suite failure.
5. Bundle activation is not blocked by Voice or Continuity failure, but is journaled.
6. Class A activation without valid signature fails.
7. Expanding rollback is refused and narrowing rollback permitted.
8. Revocation works with no signing key present.
9. Every activation and rejection is journaled with hash and validation result.
10. Replay reconstructs complete artifact history at any timestamp.

## 9. Testing considerations

Test unratified composites, `authority_delta` properties, the full key-absence
suite, and governance replay.
