### Upgrade

**You own the path back. Upgrade one unit, prove it, then the next.**

For a version upgrade of a cluster, platform component, managed service, hypervisor, or self-hosted app. Load the domain skill for the target. The gate block, grants, and predicates are in `references/gates.md`.

1. Find the repo's rules and which git events deploy. Pin the target per `references/targets.md`.
2. Preflight from release notes: breaking changes, version skew rules, deprecated APIs, and required intermediate versions. Do not skip minor versions where the project forbids it.
3. For Kubernetes, check live manifests for deprecated APIs, read-only.
4. Take backups and verify them for anything stateful in scope. "Verified" means restored, as in `restore-drill`.
5. Write the rollback before starting, with how long it takes.
6. Go to pre-production or a canary first: a non-prod environment, one node, one instance. Rehearse in a scratch namespace or throwaway VM where possible.
7. **Gate:** per unit. Between units, health checks must pass: nodes Ready, workloads healthy, storage replicas rebuilt, error rates and latency back to baseline. Check them with `change-verifier`.
8. For node-by-node upgrades: cordon, drain with PDBs respected, upgrade, uncordon, wait for storage rebuild, then the next node.
9. For managed services: provider maintenance window, provider backup, then upgrade.
10. When another agent owns the target environment, emit a handoff prompt for that agent instead of acting.

Never: start without a written rollback, move to the next unit before the health checks pass, or upgrade stateful units without a restored backup.

Calls: **kubernetes**, **virtualization**, **databases**, **message-queues**, the matching OS skill.
Principles: reversible-first, prove-the-restore, sequence-verifiable-units.

**Reply:** units upgraded, health between each, rollback readiness, and held units.
