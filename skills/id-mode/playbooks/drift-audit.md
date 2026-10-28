### Drift audit

**You own the list. Report drift; do not fix it here.**

For finding where reality differs from code: IaC state, host config, GitOps apps, and edits made in UIs. This playbook changes nothing. Fixes go through the change playbooks (`iac-change`, `gitops-change`, `host-config-change`, `edge-change`, `dependency-bump`, `upgrade`), and findings become tracked issues.

1. Pin the target per `references/targets.md` for each system audited. Use read-only credentials where they exist.
2. Terraform and OpenTofu: run `plan -detailed-exitcode` per state, read-only, with the repo's lock convention. Exit code 2 is drift. Summarize it with `plan-reader`. Exit code 1 is an error, not a clean result.
3. Ansible: `--check --diff --limit <group>` per inventory group. Note tasks that check mode cannot predict (`command`, `shell`).
4. GitOps: list apps that are OutOfSync, apps whose synced revision is behind HEAD, resources with ignored differences, and resources created outside git.
5. UI edits: compare dashboards and alert rules edited in the UI against their code, and look for cluster settings changed by hand.
6. Classify each drift as intended but not codified, accidental, or dangerous.
7. File one issue per drift cluster with the evidence and the class.

Never: apply, sync, or revert anything to clear a drift.

Calls: **terraform**, **ansible**, **kubernetes**, **observability**.
Principles: pin-the-target, encode-lessons-in-structure.

**Reply:** drift table by system and class, issues filed.
