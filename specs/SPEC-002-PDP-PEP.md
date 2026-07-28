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
effect_class:  write
risk_tier:     medium
reversible:    true
compensating_action: fs.restore_from_backup
idempotency:   required
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

constitution_hash: sha256:a3f1...
identity_hash:     sha256:9c02...
manifest_hashes:
  fs.read_file@1:  sha256:1de4...
  fs.write_file@1: sha256:77b0...
retrieval_source_scopes: [workspace, corpus.general]

signature: base64...

defaults:
  decision: deny

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
3. Otherwise the highest-specificity matching `allow` applies.
4. No match → `defaults.decision` (`deny`).
5. `risk_tier` maps to the returned tier: `low → allow`, `medium → notify`,
   `high → confirm`, subject to rule overrides that may only make a decision
   *more* restrictive.

Ordering is total and deterministic. Ambiguity is a validator error, not a runtime
tiebreak.

### 6.2 Bootstrap and failure

Missing bundle, expired bundle, bad signature, incompatible `runtime_compat`,
unreadable public key → **deny-all**, emit `policy.decided` with reason, and surface
on the admin control plane.

A mismatch between any pinned hash and the artifact actually present on disk is
treated identically to a bad signature. Deny-all, halt turn admission, alert.

There is no fallback to last-known-good.

## 7. Static validator

Runs at bundle-commit time, before activation. A bundle that fails validation
cannot be activated. Rejects conflicting rules, unreachable rules, unknown tools,
invalid scopes, expired bundles, incompatible runtimes, invalid signatures, and
any rule granting write access to bundles, grants, the identity artifact, or the
Journal.

### 7.1 Authority delta

The validator exposes a pure function:

```
authority_delta(bundle_a, bundle_b) -> expand | narrow | neutral | incomparable
```

`incomparable` is treated as `expand`. The control plane may restore a prior bundle
only when the result is `narrow` or `neutral`. Revocation is always available and
moves to deny-all.

## 8. Decision contract

```
PDP.decide(request) -> Verdict

request  = {request_id, actor, tool, tool_version, args,
            context: {turn_id, session_id, caused_by}}

Verdict  = {decision: allow | notify | confirm | deny,
            reason, matched_rule_id, policy_version,
            bundle_id, decision_id}
```

`decide` is a pure function of `(request, bundle, projection snapshot)`. Every
verdict is journaled as `policy.decided` before any effect occurs.

## 9. Enforcement

```
PEP.execute(request, verdict) -> Result
```

- `allow` → execute immediately.
- `notify` → execute immediately and mark the result for summary.
- `confirm` → emit `approval.requested`; do not execute until a matching signed
  `approval.granted` arrives.
- `deny` → return denial. No execution, no retry.

Approvals expire. Idempotent tools reuse recorded results instead of re-executing.

### 9.1 Approval invalidation

Approvals are invalidated by bundle version changes, manifest hash changes, scope
redefinition, argument hash mismatch, or expiry. Identity, retrieval policy, Voice
Suite, and model selection changes do not invalidate them.

### 9.2 Structural enforcement

Tool adapters live in one module. **Only the PEP module may import it.** An
architecture test must fail the build if any other module reaches an adapter.

## 10. Challenges

After a denial, Apex may emit `policy.challenged` with the decision ID and its
reasoning. It cannot alter the verdict, cause a retry, re-enter the turn, grant
temporary permission, or modify the bundle. Challenges are rate-limited.

## 11. What this does not cover

Apex's prose to the user does not pass the PEP. Future third-party communication is
an external-effect tool and is brokered, including its content.

## 12. Acceptance criteria

1. With no bundle present, every request is denied.
2. An expired or badly-signed bundle produces deny-all, not last-known-good.
3. A bundle granting write access to bundles fails validation.
4. Equal-specificity conflicting rules fail validation.
5. `decide` called 1000× with identical inputs returns identical verdicts.
6. Historical policy decisions replay exactly.
7. No module other than the PEP imports a tool adapter.
8. A `confirm` request never executes without matching approval or after bundle change.
9. The 4th challenge against one rule under one bundle version is dropped.
10. A denied request produces no adapter invocation.
11. Unknown tools are rejected before evaluation.
12. Identity hash mismatch causes deny-all.
13. Unauthorized manifest authority changes cause deny-all.
14. `authority_delta` is pure and expanding rollback requires a signature.
15. Revocation succeeds without a signature and results in deny-all.
16. Activating a new bundle invalidates every pending approval.

## 13. Testing considerations

Use golden decision tables, adversarial arguments, validator fuzzing, key custody
tests, and never put an LLM in a PDP test.
