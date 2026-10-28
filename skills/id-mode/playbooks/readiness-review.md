### Readiness review

**You own the checklist and the evidence behind each box.**

For deciding whether a new service is ready to depend on. Sized for a homelab or small team. This playbook changes nothing. Fixes go through the change playbooks (`iac-change`, `gitops-change`, `host-config-change`, `edge-change`, `dependency-bump`, `upgrade`), and blocking items become tracked issues.

1. Pin the target per `references/targets.md`: the environment the service runs in.
2. Check each item below. Mark it pass, fail, or n/a, with the command or document that shows it. No evidence means fail.
   - Owner and purpose are documented.
   - Health probes, resource requests and limits, and a PodDisruptionBudget where relevant.
   - Metrics, logs, a dashboard, and alerts with runbook links.
   - Backup configured, and a `restore-drill` passed.
   - Secrets are in the secret store, not in git.
   - Rollback path tested.
   - Exposure reviewed: ingress, authentication, NetworkPolicy.
   - Upgrade path known: who bumps it, and how breaking changes are found.
3. List the blocking items. A failed backup, secrets, or exposure item always blocks.
4. File an issue per blocking item. Re-run the review after the fixes land.

Never: mark an item pass from a claim in a README alone.

Calls: **kubernetes**, **observability**, **security-audit**.
Principles: pin-the-target, prove-it-works, prove-the-restore.

**Reply:** pass, fail, or n/a per item with evidence, and the blocking items.
