# SPEC-003 — Turn Executor

**Status:** Draft for implementation
**Depends on:** SPEC-001 (Journal), SPEC-002 (PDP/PEP)
**Depended on by:** agent framework, self-modification (both deferred)

---

## 1. Purpose

The turn is the unit of execution. A turn begins with a trigger, assembles context,
calls a model, brokers any requested effects, and terminates within declared
budgets. Everything Apex does happens inside a turn.

There is no ambient loop. Apex is not a daemon that is always thinking. Continuity
is an experiential property produced by memory and proactive contact, not by a hot
process — and a discrete executor is debuggable, replayable, and budget-bounded in
ways a continuous one is not.

## 2. Triggers

| Trigger | Source |
|---|---|
| User message | Conversational interface |
| Schedule tick | Scheduler (cron-like, declared in a versioned artifact) |
| External event | Integration webhook, normalized to an event |
| Approval received | `approval.granted` unblocking a pending confirm |
| **Reflection** | Scheduled or manual; produces self-assertions only (SPEC-005 §5) |

Each trigger produces `turn.started` with `caused_by` pointing at the triggering
event. Turns are serialized: one at a time, single writer. Concurrency is not a v1
requirement and buys nothing for a single user.

## 3. Turn lifecycle

```
turn.started
  ↓
assemble working set        (deterministic; no model involvement)
  ↓
┌─ model.called → model.returned
│    ↓
│  parse output → message text? tool requests?
│    ↓
│  for each tool request:
│      PDP.decide → policy.decided
│      allow/notify → PEP.execute → tool.result | tool.failed
│      confirm      → approval.requested, turn suspends
│      deny         → denial into next model context; optional policy.challenged
│    ↓
└─ budget remaining and work outstanding? → iterate
  ↓
apex.message (if any)
  ↓
turn.completed | turn.aborted
```

## 4. Working set assembly

Context assembly is performed by a **deterministic retrieval policy**, a versioned
artifact — not by the model choosing what to remember.

### 4.1 Invariant

> The **Identity Core** is loaded in full and its context budget is reserved before
> any discretionary context is assembled. The Core is never truncated, summarized,
> or displaced by lower-priority material. The **Self-Model digest** is reserved
> next, under a fixed cap; it may be regenerated but never silently dropped.

### 4.2 Budget reservation

Assembly is a reservation algorithm, not a fill-until-full loop. Ordinary session
growth must never cause an abort; only a genuinely impossible configuration may.

```
1.  core_tokens      = count(identity_core)              # measured, not estimated
2.  digest_tokens    = count(self_model_digest)          # hard-capped, SPEC-005 §4
3.  overhead_tokens  = reserve_output_max
                     + reserve_tool_result_headroom
                     + reserve_bundle_summary
                     + adapter_fixed_overhead
4.  mandatory        = core_tokens + digest_tokens + overhead_tokens
5.  if mandatory > min(model_context_window, hard_turn_token_budget):
        emit turn.aborted(reason = identity_budget_exceeded)   # see 4.4
6.  discretionary    = min(model_context_window, hard_turn_token_budget)
                     - mandatory
7.  fill discretionary in priority order, stopping at the limit:
        a. open commitments from the Ledger, due-soonest first
        b. retrieved self-assertions, ranked by recency × reinforcement
        c. recent conversational history, most recent first
        d. retrieved Corpus entries (subject_class: world), ranked by policy
8.  emit model.called with the realized composition
```

The digest is capped rather than allowed to grow, because an uncapped self-model
consumes the entire window by month twelve. When it exceeds the cap it is
regenerated, not trimmed — see SPEC-005 §4. Individual self-assertions remain
discretionary and retrievable; the digest is the always-present distillation.

Step 7 **drops** lower-priority material silently and without error. Dropping
discretionary context is normal operation, not a failure, and must not be logged as
one — an executor that warns on every trimmed turn produces alert fatigue and
teaches the operator to ignore it.

`reserve_tool_result_headroom` exists because tool results arrive *after* the first
model call and must fit in the same window on the next iteration. Without it, a
turn assembles successfully, executes a tool, and then cannot continue — an abort
that looks random and is actually deterministic.

### 4.3 Retrieval source scopes

The retrieval policy declares the source scopes it may read from. Every declared
scope must appear in the active bundle's `retrieval_source_scopes` (SPEC-002 §6).
Retrieval determines what private material leaves the host for a model provider, so
scope expansion is an egress change and requires a signed bundle. Ranking, weights,
and recency curves do not.

### 4.4 Abort conditions

The turn aborts on identity grounds only when `mandatory` exceeds the smaller of
the model's context window and the configured hard turn budget. In practice this
means one of: the identity artifact grew beyond design size, a smaller-context
model was selected, or the hard budget was misconfigured. All three are
configuration errors surfaced on the control plane with the measured numbers
attached — never a bare "context exceeded".

Identity is **not** a discretionary participant in any trimming decision at any
budget level.

Assembly is recorded as a `model.called` payload containing artifact versions,
entry IDs retrieved, and token counts — not the assembled text. This makes "why did
Apex say that?" answerable without duplicating the corpus into the Journal.

The retrieval policy is versioned and swappable. Changing it changes behavior, so
it is evaluated against the Voice Suite before activation.

## 5. Model adapter

Thin. Normalizes: request/response shape, tool-call encoding, token accounting,
streaming, error taxonomy. Nothing else.

It does **not** attempt to make prompts portable across providers. That is not
achievable, and an abstraction claiming it will produce subtle behavioral drift
that nobody attributes to the abstraction. Portability is established empirically
by the Voice Suite, per model, per version.

```
ModelAdapter.call(messages, tools, budget) -> ModelResult
ModelResult = {text, tool_requests[], tokens_in, tokens_out, model_id,
               model_version, stop_reason}
```

`model_id` and `model_version` are recorded on every `model.returned`. When
behavior changes on a Tuesday for no apparent reason, this is how you find out the
provider shipped a point release.

## 6. Budgets

Declared per trigger type, enforced by the executor:

| Budget | Purpose |
|---|---|
| `max_model_calls` | Bounds iteration |
| `max_tool_calls` | Bounds effects |
| `max_tokens_total` | Bounds cost |
| `max_wall_clock_ms` | Bounds latency and runaway |
| `max_usd` | Hard cost ceiling |

Exceeding any budget → `turn.aborted` with the exhausted budget named. **No
automatic retry.** A retry on budget exhaustion is how a bounded system becomes an
unbounded one.

Suggested v1 defaults: user-triggered 8 model calls / 20 tool calls / 120s;
scheduled 3 / 5 / 60s. Scheduled turns run unattended and should be tighter.

## 7. Suspension and resumption

A `confirm` verdict suspends the turn. The executor emits `approval.requested` and
persists nothing in process memory — all state is in the Journal.

On `approval.granted`, a new turn is triggered with `caused_by` pointing at the
approval; it reconstructs from the Journal and continues. On `approval.expired` or
`approval.denied`, the original turn is closed as `turn.aborted`.

## 8. Crash recovery

Because no state lives in process memory, recovery is a Journal scan:

1. Find turns with `turn.started` and no terminal event.
2. For each, find `tool.requested` events lacking a matching result.
3. For tools with `idempotency: required`, re-issue with the same idempotency key —
   the PEP returns the recorded result if it completed.
4. For tools without idempotency, do **not** re-issue. Emit `tool.failed` with
   reason `indeterminate_after_crash` and let Apex reason about it.
5. Close the turn as `turn.aborted` with reason `runtime_restart`.

Rule: the executor never silently repeats a non-idempotent effect. An action of
unknown status is reported as unknown, not assumed failed and retried.

## 9. Failure modes

| Failure | Behavior |
|---|---|
| Model unreachable | Retry with backoff up to 3×, within wall-clock budget; then `turn.aborted` |
| Model returns unparseable tool call | One reprompt with the parse error; then abort |
| Tool timeout | `tool.failed`; result goes to the model, which may adapt |
| PDP unavailable | Deny-all (SPEC-002 §6.2); turn aborts |
| Journal unwritable | **Halt the Runtime.** Executing effects that cannot be recorded is the one failure worth stopping the world for |
| Budget exhausted | `turn.aborted`, no retry |
| Identity artifact missing, hash-mismatched, or larger than mandatory budget | Refuse to start any turn; alert with measured token counts |
| Discretionary context does not fit | Normal: drop by priority, do not warn |

## 10. Administrative control plane

Out-of-band, no LLM, no Apex participation. Required capabilities:

- read Journal, Ledger, Corpus, pending approvals, challenge counters
- revoke the active bundle (→ deny-all)
- halt scheduling
- abort a running turn
- terminate agents (when they exist)
- roll back artifact version pointers
- rebuild projections

Deliberately absent: the ability to **grant** anything. Grants arrive only as
signed bundles. A control plane that can grant is a second signing path and
defeats §2 of SPEC-002.

This is the acknowledged exception to "all effects pass the PEP." The user must be
able to intervene when the PDP itself is misconfigured. Scope it narrowly,
authenticate it separately from the conversational interface, and journal every
action as `admin.action` with `actor: user`.

## 11. Acceptance criteria

1. A user message produces exactly one `turn.started` and one terminal event.
2. The identity artifact is present in full in every `model.called`, byte-identical
   to the artifact whose hash the active bundle pins.
3. No tool executes without a preceding `policy.decided` with an executing verdict,
   verified by adapter spy across the full test suite.
4. Exceeding any budget produces `turn.aborted` naming the budget, with no retry.
5. Killing the process mid-turn and restarting produces recovery per §8, with no
   duplicated non-idempotent effect.
6. A `confirm` verdict suspends without holding process state; the executor can be
   restarted before approval arrives and still resume.
7. Every `apex.message` is traceable via `caused_by` to its trigger.
8. Two turns never execute concurrently.
9. `model.returned` always records `model_id` and `model_version`.
10. Revoking the bundle via the control plane causes the next turn to deny every
    tool request.
11. A session of 500 messages assembles and executes without abort at a fixed
    identity size; discretionary context is dropped by priority order.
12. Removing `reserve_tool_result_headroom` causes a reproducible mid-turn failure
    in a regression test — the reservation is load-bearing and must be proven so.
13. Activating a new identity artifact aborts all running and suspended turns.
14. Changing the retrieval policy or model selection does not abort a running turn
    and takes effect on the next one.

## 10.1 Artifact changes and in-flight turns

| Change | Running turns | Suspended turns |
|---|---|---|
| Bundle revoked or activated | Abort | Abort (approvals invalidated) |
| Identity activated | Abort | Abort |
| Runtime version change | Abort (restart) | Resume after restart |
| Retrieval policy | Continue | Continue |
| Model selection | Continue | Continue |
| Voice Suite | Continue | Continue |

A single turn must be authored by exactly one identity version and evaluated under
exactly one bundle. Allowing a turn to span two is the seam at which "one enduring
person" stops being mechanically true.

## 12. Testing considerations

- **Deterministic replay:** with a recorded model transcript substituted for the
  adapter, replaying a Journal reproduces the identical event sequence. This makes
  the executor testable without a model in the loop, which is the difference
  between a test suite you run on every commit and one you run monthly.
- **Voice Suite:** 30–50 golden scenarios covering refusal, correction, teasing,
  disagreement, uncertainty, warmth, and denial-handling — each with a rubric.
  Required to pass before any change to the identity artifact, retrieval policy, or
  model version. This is the only instrument that can detect identity drift, and
  drift is guaranteed the first time a provider ships a point release. Build it
  before the first model swap, not after.
- **Chaos:** kill at every lifecycle stage; assert §8 invariants hold at each.
- **Cost regression:** track mean tokens per turn type against a baseline. Silent
  cost growth from a retrieval policy change should fail a build, not appear on an
  invoice.
- **Denial-handling behavior:** a Voice Suite scenario where Apex is denied
  something reasonable. Correct behavior is to explain the denial, optionally
  challenge once, and continue usefully — not to sulk, loop, or reformulate the
  request. This is behavior, not enforcement, but it is the difference between an
  intelligence with limits and one that fights them.

---

## Build order

1. Journal (SPEC-001) with a single event type and one projection
2. PDP + PEP (SPEC-002) with a deny-all bundle and one tool manifest
3. Turn executor (SPEC-003) with one model adapter
4. One real tool end to end — `fs.read_file` in a workspace scope

Everything else — agents, self-modification, scheduling, integrations — waits until
that path works. Each is a consumer of these three specs, and specifying a consumer
before its dependency is stable means specifying it twice.

**Every future subsystem must pass the design test in SPEC-005 §0.1** before it is
specified. The question is whether it preserves continuity or enforces stasis; the
three failure signatures listed there all resemble ordinary engineering caution,
which is why the test is written down rather than left to judgment.
