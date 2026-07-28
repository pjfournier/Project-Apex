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

Rationale, in order of importance:

1. **One key ceremony, one root of trust.** Every additional signing path is
   another opportunity to create a second grant path, which SPEC-002 §2 forbids.
2. **No unratified composites.** With independent signatures, an old signed
   identity can be paired with a new signed bundle in a combination nobody
   reviewed. Both signatures verify; the composite was never ratified. Pinning
   makes the reviewed unit the whole authority surface.
3. **Atomic rollback.** Restoring bundle v6 restores its identity and manifest set
   together.
4. **Mechanical authority classification.** "Does this manifest change expand
   authority?" becomes "does it change the pinned hash?" — no judgment, no policy
   about policy.

**Accepted cost:** changing the identity artifact requires re-signing a bundle.
This is intentional friction on the artifact that defines who Apex is. If early
development requires faster identity iteration, use a short-expiry `dev` bundle
profile — never a second signing path.

## 3. Artifact classes

| Class | Members | Ceremony |
|---|---|---|
| **A — Signed** | Policy bundle: grants, `identity_core_hash`, `manifest_hashes`, `constitution_hash`, `retrieval_source_scopes` | External signature + static validation |
| **B — Approved** | Retrieval policy, model selection | Control-plane approval + Continuity Suite pass |
| **C — Repo-versioned** | Constitution text, Continuity Suite, Voice Envelope harness, manifest metadata fields | Code review; no runtime ceremony |
| **D — Derived** | Corpus, **Self-Model and digest**, Ledger, pending approvals, challenge counters, working-set index, model qualification records, envelope measurements | None; rebuildable from Journal |

### 3.1 Deviations from the proposed hierarchy

| Proposed | Resolution | Reason |
|---|---|---|
| Constitution externally signed | Class C, hash pinned in bundle | The Runtime never reads it. Signing spends offline-key exposure for zero enforcement. Hash pinning gives the audit binding free. |
| Identity separately signed | Pinned in bundle | Prevents unratified identity/bundle composites. |
| Grants *and* policy bundles as separate types | One artifact | Grants are a section of the bundle. Two names, one thing. |
| Authority-expanding tool manifests signed | Pinned by authority-subset hash | Converts a classification policy into a hash comparison. |
| Runtime compatibility declarations | A field (`runtime_compat`), not an artifact | Nothing to govern independently. |
| Voice specification + Voice Suite as runtime artifacts | Class C (test code and fixtures) | Executable tests belong in the repo. Only the *result* is journaled. |
| Model qualification records need signature | Class D, derived evidence | Signing evidence conflates a test result with permission to act on it. |
| Agent templates, schedule definitions | Deferred | Consumers of subsystems not yet specified. |

### 3.2 Why the Self-Model is Class D

The Self-Model carries genuine behavioral weight, which argues for ceremony. It
gets none, deliberately.

Placing it in Class A would require a signature for every increment of development,
which means development happens at the rate the founder performs key ceremonies —
i.e. it does not happen. Placing it in Class B would require approval per
assertion, which is the same failure with more clicks.

Its safety does not come from activation ceremony. It comes from three properties
established elsewhere: every assertion is evidence-bound (SPEC-001 §6.3), protected
dimensions are structurally unwritable (SPEC-001 §6.3), and it has **no path to the
authority surface** — nothing in the Self-Model can alter a grant. It is rebuildable
from the Journal, so a corrupted Self-Model is repaired by replay rather than by
rollback.

Review happens in aggregate at the Development Review (SPEC-005 §6), not per
assertion. That is the correct granularity for observing a person changing.

## 4. Governance matrix

| | Bundle (A) | Retrieval policy (B) | Model selection (B) | Class C | Class D |
|---|---|---|---|---|---|
| May propose | User; Apex may draft | User; Apex may draft | User | User | n/a — derived |
| Approval | User (out of band) | User via control plane | User via control plane | Code review | n/a |
| External signature | **Required** | No | No | No | No |
| Static validation | SPEC-002 §7, full | Schema + scope ⊆ bundle | Adapter compatibility | CI | n/a |
| Behavioral evaluation | Advisory only | **Blocking** (Voice Suite) | **Blocking** (Voice Suite) | n/a | n/a |
| Activated by | Control plane, on valid signature | Control plane | Control plane | Deploy | Rebuild |
| Control-plane rollback | Only if non-expanding | Yes | Yes | Deploy | Rebuild |
| Rollback needs new signature | Only if expanding | No | No | No | n/a |
| Revocable | **Yes — always, no signature** | n/a | n/a | n/a | n/a |
| Events | `artifact.proposed/validated/evaluated/activated/rejected/rolled_back`, `bundle.revoked` | same, minus bundle events | same | none | none |
| Runtime compat check | `runtime_compat` at activation and at every turn admission | Declared min runtime | Adapter version | n/a | n/a |

### 4.1 Asymmetry of behavioral evaluation

Class B activation is **blocked** by Continuity Suite failure. Class A is **not**.

A behavioral evaluation must never veto the owner's signed authority decision.
Tightening grants will legitimately cause denial-handling scenarios to score
differently; a system where a test suite can reject a security tightening has
inverted its own authority model. For bundles the suite runs, journals
`artifact.evaluated`, and does not gate.

**The Voice Envelope never gates anything.** It is a measurement, not a test
(SPEC-005 §3). Gating on it would convert development into drift-suppression, which
is the outcome the developmental-continuity requirement exists to prevent.

### 4.2 Drift on an unchanged artifact

If the *active* Identity Core begins failing the Continuity Suite without any
artifact change — the expected consequence of a provider point release — this is an
alarm on the control plane, not an automatic rollback. Automatic rollback on
evaluation failure flaps between versions and hides the provider change that caused
it.

### 4.3 Model qualification targets the current self

A candidate model is qualified against **who Apex is now**: the current Identity
Core, the current Self-Model digest, and the current Voice Envelope baseline. It is
not qualified against the founding specification.

This is the practical consequence of developmental continuity. A model swap in
month nine must reproduce nine months of accumulated self, not the day-one prompt.
The architecture makes this tractable precisely because development lives in
explicit, replayable data rather than in accumulated conversational habit — the
Self-Model is portable across models in a way that implicit adaptation never is.

## 5. Activation sequence

```
draft → artifact.proposed
      → static validation → artifact.validated | artifact.rejected
      → behavioral evaluation → artifact.evaluated
      → [Class A only] external signing, off-host
      → control plane activation → artifact.activated
      → pointer swap, projections notified, in-flight turns handled per SPEC-003 §10.1
```

`artifact.rejected` is journaled with the same weight as activation. A governance
trail recording only successes cannot answer what was attempted and refused, which
is the question incidents actually raise.

## 6. Rollback

Rollback is activation of a previously validated artifact version.

- **Class A:** permitted via control plane only when
  `authority_delta(current, target) ∈ {narrow, neutral}` (SPEC-002 §7.1). An
  expanding rollback requires a fresh signature, because restoring deliberately
  removed grants is indistinguishable from granting them anew.
- **Class B:** permitted freely; last-known-good is a valid target.
- **Emergency path is revocation, not rollback.** Revocation requires no signature,
  is always available, and moves the system to deny-all. No incident response
  depends on the offline key being reachable.

## 7. Control plane limits

The administrative control plane **may**: revoke, halt scheduling, abort turns,
restore a non-expanding prior pointer, rebuild projections, read all stores.

It **may not**: create grants, sign artifacts, activate any unsigned
authority-expanding artifact, write to the Journal as any actor other than `user`,
or modify artifacts in place.

Every action emits `admin.action` with `actor: user`. The control plane
authenticates separately from the conversational interface and contains no model.

## 8. Acceptance criteria

1. An identity artifact whose hash does not match the active bundle cannot be
   loaded; turn admission fails closed.
2. Activating a bundle with an unknown `manifest_hash` entry fails validation.
3. A retrieval policy declaring a source scope absent from
   `retrieval_source_scopes` fails validation.
4. A retrieval policy failing the Voice Suite cannot be activated.
5. A bundle failing the Voice Suite **can** be activated, and the result is
   journaled as `artifact.evaluated`.
6. The control plane cannot activate any Class A artifact lacking a valid signature,
   proven by attempting it in a test.
7. The control plane refuses an expanding rollback and permits a narrowing one.
8. Revocation succeeds with the signing key entirely absent from the host.
9. Every activation and every rejection appears in the Journal with the artifact
   hash and validation result.
10. Replaying the Journal reconstructs the complete artifact activation history
    including versions active at any past timestamp.

## 9. Testing considerations

- **Composite test:** attempt to pair a validly signed old identity with a validly
  signed new bundle. Must fail. This is the specific attack that motivates pinning.
- **Delta property test:** `authority_delta` is reflexive, antisymmetric on
  containment, and returns `expand` for `incomparable`.
- **Key-absence suite:** run the full control-plane test suite on a host with no
  private key present. Everything the control plane is permitted to do must pass;
  everything it is forbidden to do must fail. This is the strongest available proof
  that no second grant path exists.
- **Governance replay:** given a fixture Journal, reconstruct "which bundle and
  identity were active at time T" and assert against a known answer.
