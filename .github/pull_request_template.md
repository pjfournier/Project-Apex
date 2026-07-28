## What changed

<!-- One or two sentences. Reference the SPEC section: "SPEC-002 §6.1" -->

**Implements:** SPEC-___ §___

## Architectural review

Any "yes" on 1–3, 6, 7, or 10 is a revert, not a discussion.

- [ ] 1. No code outside `enforcement/` reaches a tool adapter
- [ ] 2. `policy/` imports no clock, RNG, network, environment, or model
- [ ] 3. No new `UPDATE`/`DELETE` against events
- [ ] 4. Every new state change emits an event
- [ ] 5. No failure path returns silently without an event
- [ ] 6. No new `force` / `skip` / `bypass` / `DEV_MODE` parameter
- [ ] 7. No projection written outside its fold
- [ ] 8. No new module-level mutable state or singleton
- [ ] 9. Identity reservation still precedes discretionary assembly
- [ ] 10. No new path can grant, sign, or widen authority
- [ ] 11. New Continuity scenarios map to a numbered invariant; cap respected
- [ ] 12. Golden file changes are explained below

## Definition of Done

- [ ] Every acceptance criterion in the implemented section has a named test
- [ ] Negative tests exist for stated prohibitions
- [ ] `make test-arch` green
- [ ] Dependencies injected; no globals; no ambient clock
- [ ] Crash behavior tested where interruption is possible

## Spec impact

- [ ] No spec change needed
- [ ] Spec amended in this PR and logged in `AMENDMENTS.md`
- [ ] Deviation documented as `DEV-___` with stated cost and expiry

## Golden file changes

<!-- If any golden file changed, state the semantic reason. "Regenerated" is not a reason. -->
