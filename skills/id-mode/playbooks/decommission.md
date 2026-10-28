### Decommission

**"Unused" is a hypothesis. Prove it before anything goes dark.**

For removing or parking a VM, host, app, cluster resource, bucket, DNS name, or account believed to be unused. The gate block, grants, and predicates are in `references/gates.md`. Destroy and data deletion are never grantable.

1. Pin the target per `references/targets.md`, and find which git events deploy in the repos that define it.
2. Gather evidence from several independent sources: traffic and connection metrics, logs, recent logins, DNS lookups, firewall and NAT rules pointing at it, references in IaC and config repos, tickets and docs, and dependents in the cluster. Use cheap read-only delegates for bulk logs.
   Jev decision point (optional): `idstack judge decommission-evidence <evidence.json>`. Any `flag` or `unsettled` item (still in use above 0.3) means park, not tear down. Low answers never prove disuse.
3. Decide park or tear down. Parking keeps data and config and stops the workload. Teardown removes it. A component another service depends on is parked, not torn down.
4. **Gate:** the reversible step first (scale to zero through git, power off, rename with an `OFF-` prefix, disable the DNS name). Run **Opening a PR** when the step goes through git.
5. Agree a soak period with the operator. Watch for breakage and for new traffic.
6. **Gate:** teardown, with a final backup if any data is kept. Restore it to scratch first, per `restore-drill`.
7. Remove every reference: monitoring targets, alerts, backup jobs, DNS, firewall rules, secrets, docs, inventory. Check the result with `change-verifier`.

Never: tear down without a soak period, skip the reversible step, or run teardown under a grant.

Calls: **virtualization**, **kubernetes**, **networking**.
Principles: reversible-first, prove-the-restore.

**Reply:** evidence per item, parked vs. removed, references cleaned, and items held.
