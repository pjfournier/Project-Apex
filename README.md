# Project Apex

Project Apex is a persistent executive intelligence built around an append-only Journal, deterministic policy enforcement, auditable effects, and developmental identity continuity.

## Status

Architecture is frozen at SPEC-001 through SPEC-005. Implementation begins with Milestone M0 as defined in `docs/HANDOFF-IMPLEMENTATION-GUIDE.md`.

## Repository map

- `specs/` — authoritative architecture specifications
- `docs/` — implementation handoff guidance
- `apex/policy/AGENTS.md` — policy-module coding-agent rules
- `apex/enforcement/AGENTS.md` — enforcement-module coding-agent rules
- `AGENTS.md` — repository-wide coding-agent guidance
- `SECURITY.md` — key custody and incident-response rules
- `.github/pull_request_template.md` — architectural review checklist
- `.github/CODEOWNERS` — ownership for sensitive paths
- `AMENDMENTS.md` — append-only architecture amendment and deviation log

## Authority order

Architecture tests > SPECs > implementation handoff guide > AGENTS.md.

When sources conflict, the higher authority wins.

## Next milestone

Milestone M0: ports, continuous integration, and blocking architecture tests. Do not reorder M0.
