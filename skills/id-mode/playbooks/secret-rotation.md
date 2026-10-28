### Secret rotation

**You own every consumer. Rotation ends when the old value no longer works and nothing breaks.**

For rotating a credential, key, token, or certificate, and for responding to a leaked secret. The gate block, grants, and predicates are in `references/gates.md`. Revoking root or break-glass credentials is never grantable.

1. Find the repo's rules and which git events deploy. Pin the target (provider account, cluster, vault) per `references/targets.md`.
2. Inventory consumers: services, CI pipelines, IaC providers, and people using the secret. Record where it is stored (sealed secret, SOPS file, vault, CI variable, cloud secret manager).
3. For a leak, revoke or rotate at the provider first, then check provider logs for use during the exposure window. Do not rewrite published git history. Fix forward and rotate.
4. Create the new value at the source. Never print it, never pass it on a command line.
5. Update the store, then roll consumers one at a time. For sealed secrets, re-seal with the current key. Run **Opening a PR** for any change that lands through git.
6. **Gate:** revoke the old value.
7. Verify with `change-verifier`: every consumer works with the new value, the old value is rejected, and provider logs show no use of the old value after the switch.
8. Add a scanning rule if the leak pattern was not caught.

Never: print or read secret values, pass them as arguments, or revoke the old value before every consumer works with the new one.

Calls: **security-audit**, **kubernetes**, **terraform**, **ansible**, **ci-cd**.
Principles: pin-the-target, prove-it-works.

**Reply:** consumers updated, old value status, and the exposure check result (for leaks).
