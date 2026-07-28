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
process. A discrete executor is debuggable, replayable, and budget-bounded.

## 2. Triggers

| Trigger | Source |
|---|---|
| User message | Conversational interface |
| Schedule tick | Scheduler |
| External event | Integration webhook normalized to an event |
| Approval received | `approval.granted` |
| Reflection | Scheduled or manual; self-assertions only |

Each trigger produces `turn.started` with `caused_by` pointing at the triggering
event. Turns are serialized: one at a time, single writer.

## 3. Turn lifecycle

```
turn.started
  ↓
assemble working set
  ↓
model.called → model.returned
  ↓
parse output → messages and tool requests
  ↓
PDP.decide → policy.decided
  ↓
PEP.execute or approval.requested or denial
  ↓
iterate while budgets remain
  ↓
apex.message
  ↓
turn.completed | turn.aborted
```

## 4. Working set assembly

Context assembly is performed by a deterministic retrieval policy, not by the model.

### 4.1 Invariant

The **Identity Core** is loaded in full and its context budget is reserved before
any discretionary context is assembled. It is never truncated, summarized, or
displaced. The **Self-Model digest** is reserved next under a fixed cap.

### 4.2 Budget reservation

Assembly is reservation-first:

```
1. core_tokens = count(identity_core)
2. digest_tokens = count(self_model_digest)
3. overhead_tokens = reserve_output_max
                   + reserve_tool_result_headroom
                   + reserve_bundle_summary
                   + adapter_fixed_overhead
4. mandatory = core_tokens + digest_tokens + overhead_tokens
5. if mandatory exceeds the effective limit:
       emit turn.aborted(reason = identity_budget_exceeded)
6. discretionary = effective limit - mandatory
7. fill discretionary in this order:
       a. open commitments
       b. retrieved self-assertions
       c. recent conversation
       d. world Corpus entries
8. emit model.called with realized composition metadata
```

Dropping lower-priority discretionary context is normal operation. Identity is not
a discretionary participant in trimming.

### 4.3 Retrieval source scopes

Every retrieval scope must appear in the active bundle's
`retrieval_source_scopes`. Scope expansion is an egress change and requires a
signed bundle.

### 4.4 Abort conditions

Identity-related abort occurs only when mandatory context exceeds the smaller of
the model context window and hard turn budget. Surface measured numbers on the
control plane.

## 5. Model adapter

The adapter normalizes request and response shape, tool-call encoding, token
accounting, streaming, and error taxonomy. It records model ID and version on every
return.

## 6. Budgets

Per-trigger budgets bound model calls, tool calls, total tokens, wall-clock time,
and cost. Exceeding any budget emits `turn.aborted` naming the exhausted budget.
There is no automatic retry.

## 7. Suspension and resumption

A `confirm` verdict suspends the turn. All state remains in the Journal. Approval
triggers a new turn that reconstructs and continues. Expiry or denial aborts the
original turn.

## 8. Crash recovery

Recovery scans the Journal for nonterminal turns and unresolved tool requests.
Idempotent effects may be re-issued with the same idempotency key. Non-idempotent
effects are never silently repeated and become `indeterminate_after_crash`.

## 9. Failure modes

- Model unreachable: bounded retries within budget, then abort.
- Unparseable tool call: one reprompt, then abort.
- Tool timeout: `tool.failed` and return result to the model.
- PDP unavailable: deny-all and abort.
- Journal unwritable: halt the Runtime.
- Budget exhausted: abort, no retry.
- Identity missing, mismatched, or over budget: refuse admission.
- Discretionary context overflow: drop by priority without warning.

## 10. Administrative control plane

Out-of-band, no model, no Apex participation. It may inspect stores, revoke the
bundle, halt scheduling, abort turns, restore non-expanding pointers, rebuild
projections, and terminate future agents. It may never grant authority.

Every action emits `admin.action` with `actor: user`.

## 10.1 Artifact changes and in-flight turns

| Change | Running turns | Suspended turns |
|---|---|---|
| Bundle revoked or activated | Abort | Abort |
| Identity activated | Abort | Abort |
| Runtime version change | Abort | Resume after restart |
| Retrieval policy | Continue | Continue |
| Model selection | Continue | Continue |
| Voice Suite | Continue | Continue |

A single turn must use exactly one identity version and one bundle version.

## 11. Acceptance criteria

1. A user message produces exactly one `turn.started` and one terminal event.
2. The Identity Core is present in full in every `model.called`.
3. No tool executes without a preceding executing `policy.decided` verdict.
4. Budget exhaustion produces named abort and no retry.
5. Crash recovery never duplicates a non-idempotent effect.
6. Confirmation suspension survives process restart.
7. Every `apex.message` traces through `caused_by` to its trigger.
8. Two turns never execute concurrently.
9. `model.returned` always records model ID and version.
10. Revocation causes the next turn to deny every tool request.
11. Long sessions drop discretionary context without aborting.
12. Tool-result headroom is protected by regression test.
13. Identity activation aborts running and suspended turns.
14. Retrieval policy or model selection changes take effect on the next turn.

## 12. Testing considerations

Use recorded model transcripts for deterministic replay, a Voice Suite for identity
drift, chaos tests across lifecycle stages, cost regression tracking, and explicit
denial-handling scenarios.

## Build order

1. Journal with one event type and projection
2. PDP + PEP with deny-all and one tool manifest
3. Turn executor with one model adapter
4. `fs.read_file` end to end

Everything else waits until this path works.
