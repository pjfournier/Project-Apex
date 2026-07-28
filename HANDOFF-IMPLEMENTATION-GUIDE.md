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

These are not preferences. A change violating any of them is reverted regardless of
what it enables.

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

Print these. They are the review checklist's spine.

---

## 2. Repository structure

Layout is not cosmetic here: module boundaries are how the dependency rules become
mechanically checkable.

```
apex/
  journal/              # SPEC-001: envelope, append, replay, hash chain
    events.py           #   frozen event types + registry
    store.py            #   SQLite; the only SQL in the project
    chain.py            #   hashing, verification
  projections/          # SPEC-001 §6: ledger, corpus, approvals, counters
    base.py             #   fold protocol, last_applied_seq
    ledger.py corpus.py approvals.py counters.py
  policy/               # SPEC-002: PDP, bundle model, static validator
    bundle.py           #   parse, verify signature, pinned hashes
    decide.py           #   pure decision function — NO IO
    validator.py        #   commit-time validation, authority_delta
  enforcement/          # SPEC-002: PEP
    pep.py              #   the ONLY importer of adapters/tools
    approvals.py        #   confirm lifecycle, idempotency
  adapters/
    tools/              #   fs_read.py, fs_write.py, ...
    models/             #   anthropic.py, ...
  runtime/              # SPEC-003
    executor.py assembly.py budgets.py recovery.py
  artifacts/            # SPEC-004: load, hash, activate, rollback
  identity/             # SPEC-005: core, self_model, digest, reflection
  control/              # admin control plane (CLI)
  ports.py              # Clock, Rng, Signer(verify-only) — injected, never global

tests/
  unit/ integration/ replay/ architecture/ continuity/
fixtures/
  journals/ bundles/ manifests/ scenarios/

specs/                  # SPEC-001..005, verbatim
AMENDMENTS.md           # append-only log of spec amendments
```

**Language:** Python 3.12+. Chosen for SDK availability, JSON Schema tooling, and
first-class SQLite. The architecture does not depend on this; it depends on the
boundaries above.

---

## 3. Dependency rules

### 3.1 Permitted

| Module | May import |
|---|---|
| `journal` | stdlib, `ports` |
| `projections` | `journal`, `ports` |
| `policy` | `journal` (read-only types), `ports` |
| `enforcement` | `policy`, `journal`, `adapters/tools`, `ports` |
| `adapters/*` | stdlib, third-party SDKs, `ports` |
| `runtime` | `journal`, `projections`, `policy`, `enforcement`, `artifacts`, `identity`, `adapters/models` |
| `artifacts` | `journal`, `policy`, `ports` |
| `identity` | `journal`, `projections`, `ports` |
| `control` | `journal`, `projections`, `artifacts` |

### 3.2 Forbidden — enforced by `tests/architecture/`

| Forbidden | Why |
|---|---|
| Anything except `enforcement` importing `adapters/tools` | Creates a second effect path (invariant 2) |
| `policy` importing `adapters/*`, `runtime`, or any model SDK | Puts inference in the decision path (invariant 3) |
| `policy` importing `datetime`, `random`, `requests`, or `os.environ` | Destroys purity and replayability |
| `control` importing `runtime.executor` or `adapters/tools` | Control plane must not be able to act as Apex |
| `journal` importing any other apex module | Foundation must stay dependency-free |
| Any module writing SQL outside `journal/store.py` | Bypasses the log |
| Global mutable singletons anywhere | Hidden state defeats replay |

---

## 4. Implementation order

Each step exists because the next one cannot be tested without it.

1. **`ports.py` + architecture tests.** Before any component. The import-graph test
   and no-clock-in-policy test cost an hour and are worthless if written after the
   violations exist.
2. **Journal.** Nothing can be observed, tested, or debugged until events are
   recorded. Everything downstream is a fold over it.
3. **Projections.** Needed by the PDP (rate counters) and the executor (Ledger).
   Build `counters` and `approvals` first; `ledger` and `corpus` can lag.
4. **Policy: bundle model + validator.** Before the PDP, because the PDP's input
   type is a validated bundle. Writing them in the other order produces a PDP that
   accepts unvalidated bundles "temporarily."
5. **PDP.** Pure function. Fully testable with fixtures and no runtime.
6. **PEP + one tool adapter (`fs.read_file`).** First point at which an effect can
   occur. The import-graph test must already be green.
7. **Model adapter.** Isolated; test against recorded transcripts.
8. **Turn executor.** Requires all of the above. Build assembly and budgets first,
   then the iteration loop, then recovery.
9. **Control plane.** Needed before the system runs unattended for the first time.

---

## 5. Coding philosophy

**Simplicity.** One SQLite file, one process, one writer. Reject queues, brokers,
async frameworks, and plugin systems. If a component seems to need concurrency,
re-read SPEC-003 §2 — turns are serialized deliberately.

**Determinism.** Anything in `policy/` is a pure function. No ambient clock, no
environment reads, no randomness. Time and IDs enter through `ports` and are
injected. Test: calling `decide()` a thousand times with identical input returns
identical output including `matched_rule_id`.

**Testability.** Every component takes its dependencies as constructor arguments.
No module-level state. The executor must be testable with a recorded model
transcript substituted for the adapter — if it isn't, the test suite runs monthly
instead of per-commit, and the architecture erodes between runs.

**Replayability.** Given the same Journal, every projection, every decision, and
every turn reconstruction produces the same result on any machine at any time.
Anything that breaks this is a defect even if no test fails today.

**Auditability.** If an effect occurred and no event records it, that is a bug of
the same severity as data loss. Write the event before the effect where ordering
permits; where it doesn't, write intent before and outcome after.

---

## 6. Definition of Done

A component is done when **all** are true:

- [ ] Every acceptance criterion in its SPEC has a named test asserting it
- [ ] Negative tests exist for its stated prohibitions, not only positive paths
- [ ] No new architecture-test violations
- [ ] Dependencies injected; no globals; no ambient clock
- [ ] All state changes journaled
- [ ] Failure modes produce events, not silent returns
- [ ] Public functions have type annotations; no `Any` in the event envelope
- [ ] Crash behavior tested where the component can be interrupted mid-operation
- [ ] The PR references the SPEC section it implements

"Works when I run it" is not on this list.

---

## 7. Testing philosophy

| Layer | Scope | Examples |
|---|---|---|
| **Unit** | Pure logic, no IO | hash chain, canonical JSON, `authority_delta`, budget arithmetic, rule matching |
| **Integration** | Real SQLite, real adapters, no model | append → project → decide → enforce; approval lifecycle; crash recovery |
| **Replay** | Fixture Journal → expected state | golden projection snapshots; historical verdict reproduction; "who was active at time T" |
| **Architecture** | Static analysis of the codebase | import graph, forbidden imports, SQL location, key absence, no-clock-in-policy |
| **Continuity** | Model behavior against invariants | SPEC-005 §3.1; blocking; capped at 2 per invariant |

Notes that matter:

- **Architecture tests are the load-bearing suite.** They encode the constraints no
  functional test can express, because the constraints are about what must not
  exist. Treat a failure as a revert, never as a lint warning to suppress.
- **The key-absence suite** (SPEC-004 §9) runs the full control-plane test set on a
  host with no private key. Everything permitted must pass; everything forbidden
  must fail. It is the strongest available proof that no second grant path exists.
- **Never put a live model in a determinism test.** If a test needs one, the code
  under test has acquired a dependency it must not have.
- **Golden files are reviewed diffs, not regenerated artifacts.** A PR that
  regenerates a golden projection snapshot without explaining the semantic change
  is rejected on sight.

---

## 8. Common implementation mistakes

Each of these is plausible, well-intentioned, and fatal.

**Alternate execution path**
```python
# runtime/executor.py
def execute_tool(tool, args):        # "just a thin wrapper"
    return adapters.tools.run(tool, args)
```
Legal imports, second call site, PEP bypassed. All effects go through
`PEP.execute()` and nowhere else.

**Test-time bypass**
```python
if settings.DEV_MODE:
    return Verdict(decision="allow", reason="dev")
```
The single most likely fatal commit. Use a `dev` bundle profile (SPEC-004 §2), not
a code path. Grep for `DEV_MODE`, `skip_policy`, `force`, `allow_unsafe`, `bypass`
in review.

**Bypassing the Journal**
```python
self.corpus.add(entry)               # effect with no event
```
Every state change is an event first. The projection is downstream, always.

**Mutating a projection**
```python
ledger.rows[i].status = "met"        # projection edited directly
```
Emit `commitment.updated`; let the fold apply it. A hand-edited projection is
unreproducible and will silently diverge on the next rebuild.

**LLM inside a deterministic system**
```python
if await model.ask(f"Is {args} safe?"):   # in policy/
```
Destroys purity, replayability, and audit. Also unfixable by tuning.

**Runtime inferring policy**
```python
risk = "low" if tool.startswith("fs.read") else "high"
```
Risk is declared in the manifest and pinned by hash. Runtime reads it; it never
computes it.

**Hidden mutable state**
```python
class TurnExecutor:
    def __init__(self): self.pending = []    # lost on crash
```
All turn state lives in the Journal. If restarting mid-turn loses information, the
design has drifted.

**Assemble-then-trim**
```python
ctx = build_everything(); ctx = trim_to_fit(ctx, window)
```
Produces correct output in the common case and inverts SPEC-003 §4.1 in the rare
one. Reserve first, fill second.

**Rate counters from a lagging projection**
Counters must be read transactionally at decision time. A projection that trails by
even one event permits over-limit calls, and nothing will fail loudly.

**Retry on denial or budget exhaustion**
Both are terminal. A retry loop turns a bounded system into an unbounded one.

---

## 9. Git workflow

**Trunk-based.** `main` always green. Short-lived branches:
`spec-002/pdp-rule-matching`, `fix/chain-verify-offbyone`.

Commits reference the spec section: `SPEC-002 §6.1: implement deny-precedence`.

**Amendments.** The architecture is frozen; amendments are not forbidden, they are
logged. Append to `AMENDMENTS.md`:

```
AMD-001 | 2026-08-04 | SPEC-003 §4.2
What:   reserve_tool_result_headroom default 2000 → 3500
Why:    observed p95 tool result 3.1k tokens; mid-turn overflow in 4% of turns
Impact: none outside assembly
```

Then edit the SPEC in the same PR. A spec that no longer matches the code is worse
than no spec.

**Deviations.** If the implementation cannot match the spec, do not silently
diverge. Open a PR that either amends the spec or documents the deviation as
`DEV-nnn` in `AMENDMENTS.md` with a stated cost and expiry. Undocumented divergence
is how the architecture dies quietly.

**Architectural blockers.** If implementation reveals one of the three reopening
conditions (SPEC-004/005 freeze note: key-absence suite unwritable, replay too slow
to rebuild during an incident, PDP cannot express a needed grant), stop and escalate
rather than working around it.

---

## 10. Architectural review checklist

Run before merging. Twelve items, under two minutes.

1. Does any new code outside `enforcement` reach a tool adapter?
2. Does `policy/` import a clock, RNG, network, environment, or model?
3. Is there any new `UPDATE`/`DELETE` against events?
4. Is every new state change accompanied by an event?
5. Does any new failure path return silently instead of emitting an event?
6. Any new `force` / `skip` / `bypass` / `DEV_MODE` parameter?
7. Does any projection get written outside its fold?
8. Any new module-level mutable state or singleton?
9. Does the identity reservation still occur before discretionary assembly?
10. Could any new path grant, sign, or widen authority?
11. Do new Continuity Suite scenarios map to a numbered invariant, and is the cap
    respected?
12. Do the golden files change, and if so is the semantic reason stated?

Any "yes" on 1–3, 6, 7, 10 is a revert, not a discussion.

---

## 11. Coding conventions

Only those that affect correctness.

- **Frozen dataclasses** for events, verdicts, manifests. Immutability by default.
- **No `Any`** in the event envelope or verdict types.
- **Canonical JSON** — one implementation, in `journal/chain.py`, used everywhere
  hashing occurs. Two serializers means two hashes for the same object.
- **Ports for the impure world.** `Clock`, `Rng`, `SignatureVerifier`. Direct
  `datetime.now()` outside a port is a review failure.
- **Explicit injection.** Constructors take dependencies. No service locator.
- **Errors are typed and journaled.** No bare `except:`; no swallowed exceptions.
- **ULIDs from one library, one place.** Ordering correctness depends on it.
- **UTC everywhere.** Naive datetimes are rejected at the envelope boundary.

---

## 12. Milestone roadmap

| M | Deliverable | Done when |
|---|---|---|
| **M0** | Ports, CI, architecture tests | Import-graph and no-clock tests green against an empty tree |
| **M1** | Journal | Chain verification detects a mutated byte; crash-injection suite green; 1M-event rebuild timed |
| **M2** | Projections: counters, approvals | Drop-and-rebuild reproduces byte-identical state |
| **M3** | Bundle model + static validator | Rejects conflicting, unreachable, self-granting bundles; `authority_delta` property tests green |
| **M4** | PDP | 1000× determinism test; golden decision table; historical verdict replay |
| **M5** | PEP + `fs.read_file` | Denied request produces zero adapter invocations (spy-verified); key-absence suite green |
| **M6** | Model adapter | Recorded-transcript replay reproduces identical events |
| **M7** | Turn executor | One full turn: user message → tool → response, fully journaled and replayable |
| **M8** | Control plane | Revoke with no key present → next turn denies everything |
| **M9** | Identity Core + Continuity Suite | 18 scenarios, each mapped to an invariant; blocking on Class B activation |
| **M10** | Ledger + commitments | Apex honors an open commitment unprompted, sourced from the Ledger not recall |
| **M11** | Corpus + Self-Model + digest | Self-assertions evidence-bound; digest capped and regenerating |
| **M12** | Reflection turns + Voice Envelope | Daily reflection producing self-assertions; envelope measuring against rolling baseline |

**First usable prototype: M10.** At that point Apex holds a conversation with
durable memory, honors commitments from a real ledger, reads files under enforced
policy, and every action is auditable and replayable. M11–M12 are what make him
develop; M1–M10 are what make him trustworthy enough to let develop.

Do not reorder M0. Every architecture test written after its violations exist is a
test that gets weakened to pass.
