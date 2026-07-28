# Security

Scope: key custody and incident response. Design rationale lives in SPEC-002 §2;
this document covers operations, which no SPEC does.

## Root of trust

The policy bundle is the only signed artifact. Every control in this system
resolves to one assumption:

> **The private signing key never exists on the runtime host.**

If that assumption fails, nothing else in the architecture holds. Grants, identity
pinning, manifest integrity, and the prohibition on self-granted authority all
collapse simultaneously and silently.

### Acceptable custody

- Hardware token, signing performed off-host
- Key material on a machine the runtime cannot reach, with bundles transferred as
  signed files

### Unacceptable

- Key file anywhere on the runtime host, at any permission level
- Key in an environment variable in the runtime's process
- Key in the repository, in CI secrets used by the runtime, or in any path an
  Apex-invoked tool could enumerate
- Any script in this repository that generates a signing key

The runtime holds the **public key only**. A PR adding key generation or private
key handling to this repository is rejected on sight.

## Verification

`make test-keyless` runs the full control-plane suite on a host with no private key
present. Everything the control plane is permitted to do must pass; everything it
is forbidden to do must fail. This is the strongest available evidence that no
second grant path exists. Run it before every release and after any change under
`apex/policy/`, `apex/enforcement/`, or `apex/control/`.

## Incident response

**Revoke first.** Revocation requires no signature, is always available, and moves
the system to deny-all. Do not attempt diagnosis, rollback, or a corrective bundle
before revoking.

```
apex-ctl revoke          # → deny-all, immediate
apex-ctl halt-schedules
apex-ctl abort-turns
```

Then investigate. Rollback is not an incident tool: an expanding rollback is
refused without a signature, and the key may not be reachable during an incident.
This is intentional — the fast path is always toward less authority.

## Reporting

Security concerns go directly to the repository owner. Do not open a public issue
describing a bypass in the enforcement path.
