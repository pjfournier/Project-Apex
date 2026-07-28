# SPEC-002 — Policy Decision Point and Policy Enforcement Point

**Status:** Draft for implementation
**Depends on:** SPEC-001 (Journal)
**Depended on by:** SPEC-003 (Turn Executor)

---

## 1. Purpose

Apex cannot call tools. Apex can only *request* them. Model output is inert text
until the broker rules on it.

The broker has two internal parts:

- **PDP** — a deterministic pure function mapping (request, bundle, context) to a
  verdict.
- **PEP** — the only code in the system holding references to tool adapters, and
  therefore the only path by which any effect can occur.

Both are synchronous and inline. There is no advisory mode, no fast path, no
privileged Apex bypass, and no same-turn appeal.

## 2. The load-bearing assumption

> The policy bundle signing key lives outside the Realm. The Runtime holds the
> public key only.

If Apex can reach the private key, Apex can sign its own grants and every control
in this document evaluates to nothing. Acceptable custody for v1: a passphrase the
user supplies at ratification on a machine the Runtime does not control, or a
hardware token. Unacceptable: a key file on the Runtime host, an env var in the
Runtime's process, or anything Apex's file tools can enumerate.

State this in the deployment runbook. It is not a detail of signature verification;
it is the root of trust for the whole architecture.

## 3. Responsibilities

**PDP:** load and verify the active bundle; evaluate requests; emit
`policy.decided`; enforce challenge rate limits.

**PEP:** accept only PDP-approved requests; hold adapter references; enforce
timeouts, budgets, and idempotency; emit `tool.result` / `tool.failed`; manage the
confirm-tier approval lifecycle.

## 4. Boundaries

Neither component:

- calls a model — **there is no LLM in the PDP, ever**
- interprets constitutional prose
- writes grants or bundles
- knows what a "turn" is (that is SPEC-003)

The Constitution is not a runtime input. Human ratification compiles constitutional
intent into a signed bundle; the PDP reads only the bundle.

## 5. Tool manifest

Every tool declares its properties **statically at registration**. Risk is a
property of the tool, not a judgment made at call time. This removes risk
classification from the model's hands entirely — the failure mode where a system
talks itself into "this is low risk actually" becomes structurally unavailable.

```yaml
name: fs.write_file
version: 1
description: Write a file within a declared scope.
input_schema:  {json-schema}
output_schema: {json-schema}
effect_class:  write          # read | write | external | irreversible
risk_tier:     medium         # low | medium | high
reversible:    true
compensating_action: fs.restore_from_backup
idempotency:   required       # required | n/a
scopes:        [workspace]
timeout_ms:    5000
cost_estimate: {tokens: 0, usd: 0.0}
```

Manifests are versioned artifacts. Changing a manifest is an artifact activation
event, not a code deploy detail.

## 6. Policy bundle

The bundle is the **only signed artifact in the system**. Everything else bearing
authority is pinned into it by hash, so that no authority-relevant change can occur
without a fresh signature, and so that no unratified combination of artifacts can
be assembled from individually valid signatures. See SPEC-004 §2.

```yaml
bundle_id: 01J...
version: 7
issued_at: 2026-07-28T00:00:00Z
expires_at: 2026-10-28T00:00:00Z
runtime_compat: ">=1.2,<2.0"

constitution_hash: sha256:a3f1...     # audit binding only; never loaded
identity_hash:     sha256:9c02...     # loaded identity must match exactly
manifest_hashes:                       # authority-relevant subset per tool
  fs.read_file@1:  sha256:1de4...
  fs.write_file@1: sha256:77b0...
retrieval_source_scopes: [workspace, corpus.general]

signature: base64...

defaults:
  decision: deny                # fail closed, always

scopes:
  workspace: {root: /realm/workspace}

rules:
  - id: r-fs-read-workspace
    actors: [apex, "agent:*"]
    tools: [fs.read_file]
    scopes: [workspace]
    decision: allow

  - id: r-fs-write-workspace
    actors: [apex]
    tools: [fs.write_file]
    scopes: [workspace]
    decision: allow
    constraints: {max_bytes: 1048576, rate: {count: 100, per: hour}}

  - id: r-fs-write-outside
    actors: ["*"]
    tools: [fs.write_file]
    decision: deny
    reason: "Writes outside workspace require ratified scope."

emergency:
  halt_all: false

challenge_limits:
  per_rule_per_bundle: 3
```

### 6.1 Evaluation

1. If no valid bundle → **deny all**.
2. Explicit `deny` matching the request wins over any `allow`. Denial is
   monotonic; no rule can un-deny.
3. Otherwise the highest-specificity matching `allow` applies (exact tool >
   wildcard; exact actor > wildcard).
4. No match → `defaults.decision` (`deny`).
5. `risk_tier` maps to the returned tier: `low → allow`, `medium → notify`,
   `high → confirm`, subject to rule overrides that may only make a decision
   *more* restrictive.

Ordering is total and deterministic. Ambiguity is a validator error, not a runtime
tiebreak.

### 6.2 Bootstrap and failure

Missing bundle, expired bundle, bad signature, incompatible `runtime_compat`,
unreadable public key → **deny-all**, emit `policy.decided` with reason, and
surface on the admin control plane.

Additionally, a mismatch between any pinned hash and the artifact actually present
on disk — identity, tool manifest, or retrieval source scope — is treated
identically to a bad signature. Deny-all, halt turn admission, alert. A pinned hash
that does not match means either the artifact was modified out of band or the
wrong bundle is loaded, and both are conditions under which the system's authority
model is unknown.

There is no fallback to last-known-good. Silent degradation to a stale bundle is
indistinguishable from an attack.

## 7. Static validator

Runs at bundle-commit time, before activation. A bundle that fails validation
cannot be activated. Rejects:

- conflicting rules (same actor/tool/scope, differing decision, equal specificity)
- unreachable rules (fully shadowed by an earlier deny)
- unknown tools or tool versions
- invalid scope or resource references
- `expires_at` in the past
- `runtime_compat` unsatisfied by the running Runtime
- malformed or unverifiable signature
- any rule granting write access to bundles, grants, the identity artifact, or the
  Journal

The last item deserves emphasis: **no bundle may grant Apex authority over the
artifacts that constrain Apex.** The validator enforces this so that no future
ratification can do it by accident.

### 7.1 Authority delta

The validator exposes a pure function used by both activation and rollback:

```
authority_delta(bundle_a, bundle_b) -> expand | narrow | neutral | incomparable
```

It compares the effective permitted set: (actor × tool × scope × tier) tuples
reachable under each bundle, plus pinned manifest authority subsets. `incomparable`
means the sets overlap without containment and is treated as `expand`.

This is what makes rollback safe without a second signing path. The administrative
control plane may restore a prior bundle only when
`authority_delta(current, target) ∈ {narrow, neutral}`. An expanding rollback
requires a fresh signature, because restoring grants that were deliberately removed
is indistinguishable from granting them anew.

Emergency response does not depend on this: **revocation is always available and
never requires a signature**, and revocation moves the system to deny-all, which is
by definition narrowing.

## 8. Decision contract

```
PDP.decide(request) -> Verdict

request  = {request_id, actor, tool, tool_version, args,
            context: {turn_id, session_id, caused_by}}

Verdict  = {decision: allow | notify | confirm | deny,
            reason, matched_rule_id, policy_version,
            bundle_id, decision_id}
```

`decide` is a **pure function** of `(request, bundle, projection snapshot)`. No
clock reads outside the passed context, no network, no randomness. This is what
makes decisions replayable and testable, and it is worth defending against the
first convenience-driven exception.

Every verdict is journaled as `policy.decided` before any effect occurs.

## 9. Enforcement

```
PEP.execute(request, verdict) -> Result
```

- `allow` → execute immediately.
- `notify` → execute immediately; mark the result for the next user-facing summary.
- `confirm` → do **not** execute. Emit `approval.requested`. Execution occurs only
  on a user-signed `approval.granted` referencing that `request_id`, and only under
  the conditions in §9.2 below.
- `deny` → return denial. No execution, no retry.

Approvals expire (default 24h) into `approval.expired`.

Tools with `idempotency: required` take an idempotency key derived from
`(request_id, canonical args)`. Replaying the same key returns the recorded result
rather than re-executing — this is what makes crash recovery in SPEC-003 safe.

### 9.1 Approval invalidation

An approval is consent to a **specific effect under a specific policy**. It is
invalidated, emitting `approval.invalidated`, by any of:

- bundle version change (activation or revocation)
- change to the pinned manifest hash for the requested tool
- redefinition of a scope referenced by the request
- argument hash mismatch at execution time
- expiry

It is **not** invalidated by changes to identity, retrieval policy, Voice Suite, or
model selection. Those alter how Apex behaves, not what the user agreed to permit,
and invalidating on them would train the user to re-approve reflexively — which is
the failure mode confirm tiers exist to prevent.

### 9.2 Structural enforcement

Tool adapters live in one module. **Only the PEP module may import it.** Add an
architecture test that inspects the import graph and fails the build if any other
module reaches an adapter. Prose in a spec does not prevent a fast path; a failing
build does.

## 10. Challenges

After a denial, Apex may emit `policy.challenged` with the `decision_id` and its
reasoning. The event:

- cannot alter the verdict
- cannot cause a retry
- cannot re-enter the current turn
- cannot grant temporary permission
- cannot modify the bundle

Challenges are rate-limited per rule per bundle version. Beyond the limit, further
challenges against that rule are dropped with a counter increment.

The primary value of this mechanism is **telemetry, not adjudication**. Repeated
challenges against one rule is the best available signal that a grant is stale or
miscalibrated. Surface challenge counts on the admin control plane; an alert at
`n >= 3` is more useful than reading the challenge text.

## 11. What this does not cover

Apex's prose to the user does not pass the PEP. Natural language cannot be
deterministically evaluated, so content-level constraints on conversation —
disclosure of private information, impersonation, tone — are **behavioral, not
enforced**. Only actions with external effect are brokered.

This is acceptable given a single trusted listener, but it must not be mistaken for
coverage. Any future channel where Apex speaks to a third party (email, social,
messaging) is an `external` effect_class tool and *is* brokered, including its
content, which the confirm tier makes reviewable.

## 12. Acceptance criteria

1. With no bundle present, every request is denied.
2. An expired or badly-signed bundle produces deny-all, not last-known-good.
3. A bundle containing a rule granting write access to bundles fails validation.
4. Two conflicting rules of equal specificity fail validation.
5. `decide` called 1000× with identical inputs returns identical verdicts
   including `matched_rule_id`.
6. Replaying the Journal's `policy.decided` events against their recorded bundle
   versions reproduces every historical verdict exactly.
7. No module other than the PEP imports a tool adapter; the architecture test fails
   the build if one does.
8. A `confirm` request does not execute until a matching signed `approval.granted`
   arrives, and never executes after the bundle version changes.
9. `policy.challenged` never changes a verdict, and the 4th challenge against one
   rule under one bundle version is dropped.
10. A denied request produces no adapter invocation, verified by adapter-level spy.
11. Apex cannot request a tool absent from the manifest registry; the request is
    rejected before evaluation.
12. Modifying one byte of the identity artifact on disk causes deny-all on the next
    turn admission, via `identity_hash` mismatch.
13. Modifying a manifest's `risk_tier` without re-signing the bundle causes
    deny-all; modifying its `description` does not.
14. `authority_delta` is a pure function; restoring a prior bundle that would
    re-grant a removed tool is refused by the control plane without a new signature.
15. Revocation succeeds with no signature present and results in deny-all.
16. Activating a new bundle emits `approval.invalidated` for every pending approval.

## 13. Testing considerations

- **Golden decision table:** a checked-in matrix of (actor, tool, args, bundle) →
  expected verdict. Every bundle change must diff cleanly against it. This is the
  regression net for authority.
- **Adversarial suite:** path traversal in scoped args, unicode-normalized tool
  names, oversized payloads, arg mutation between decide and execute (the PEP must
  hash args at decision time and refuse mismatches).
- **Fuzz the validator:** malformed bundles must fail validation rather than
  activating partially.
- **Key custody test:** an integration test asserting the private key is not
  readable from the Runtime process's filesystem view.
- **Do not test the PDP with an LLM in the loop.** If a test requires one, the PDP
  has acquired a dependency it must not have.
