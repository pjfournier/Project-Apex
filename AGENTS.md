# AGENTS.md

Guidance for coding agents working in this repository.

This file contains **rules and routing**. It contains no architecture. When you
need to understand *why* something is required, read the SPEC — do not infer it
from this file.

**Authority order:** architecture tests > SPECs > HANDOFF guide > this file.
If this file conflicts with a SPEC, the SPEC is correct and this file is a bug.

---

## Never

These ten are absolute. A change violating any of them is reverted regardless of
what it enables. Canonical list with rationale: `HANDOFF-IMPLEMENTATION-GUIDE.md`
§1.3.

1. Never `UPDATE` or `DELETE` rows in the events table.
2. Never produce an external effect outside `enforcement/pep.py`.
3. Never put a model call, network call, clock read, or randomness in `policy/`.
4. Never create, store, or reference a private signing key on this host.
5. Never fall back to a previous bundle on validation failure — deny all instead.
6. Never retry a denied request or an exhausted budget.
7. Never trim, summarize, or defer the Identity Core to fit a context window.
8. Never hold turn state in process memory.
9. Never write memory from model output directly — propose, validate, then apply.
10. Never add a code path that grants, signs, or widens authority.

## Never, in code shapes

Reject these patterns on sight. Each is locally reasonable and globally fatal.

- `DEV_MODE`, `skip_policy`, `force=True`, `allow_unsafe`, `bypass` — use a `dev`
  bundle profile instead of a code path
- A wrapper in `runtime/` that calls a tool adapter
- `datetime.now()`, `random`, `os.environ` outside `ports.py`
- Direct assignment to a projection row
- SQL anywhere except `journal/store.py`
- Module-level mutable state or singletons
- Assemble-then-trim context building
- Reading rate-limit counters from a projection rather than transactionally

## Stop and ask

Do not proceed; open a question instead.

- A test cannot pass without weakening an architecture test
- A SPEC acceptance criterion appears impossible as written
- A change would require a key on this host
- A change would let `policy/` become impure
- You are about to add a file under `specs/`
- You believe a SPEC is wrong

Working around any of these is worse than stopping.

## Where to look

| Question | Source |
|---|---|
| Event envelope, hash chain, projections, Corpus rules | SPEC-001 |
| Bundles, tool manifests, PDP/PEP, challenges, approvals | SPEC-002 |
| Turn lifecycle, context assembly, budgets, recovery | SPEC-003 |
| Artifact classes, signing, activation, rollback | SPEC-004 |
| Identity Core, Self-Model, invariants, Continuity Suite | SPEC-005 |
| Repo layout, dependency rules, milestones, common mistakes | HANDOFF §2–§12 |
| Key custody and incident response | SECURITY.md |

Read the specific section. Do not read all five SPECs for a scoped task.

## Commands

```bash
make test           # full suite
make test-arch      # architecture tests — run before proposing any diff
make test-replay    # golden replay
make lint
```

`make test-arch` must be green before you open a PR. If it fails, the diff is
wrong — do not adjust the test.

## Working rules

- One SPEC section per PR where possible. Reference it in the commit:
  `SPEC-002 §6.1: implement deny-precedence`.
- Every acceptance criterion in the section you implement gets a named test.
- Write negative tests for prohibitions, not only positive paths.
- Never edit a SPEC and code in separate PRs. If behavior must change, amend the
  SPEC in the same PR and append to `AMENDMENTS.md`.
- Never regenerate a golden file without stating the semantic change in the PR.
- Do not add dependencies without asking. Standard library first.
