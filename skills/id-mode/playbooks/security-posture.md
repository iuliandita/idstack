### Security posture

**You own what is new since last time.**

A periodic security check of clusters, hosts, CI, secrets, and the external surface, compared to the last baseline. Defensive, own assets only, no exploitation. This playbook changes nothing. Fixes go through the change playbooks (`iac-change`, `gitops-change`, `host-config-change`, `edge-change`, `dependency-bump`, `upgrade`), and findings become tracked issues.

1. Pin the target per `references/targets.md`, and confirm each asset in scope is yours. Load the last stored baseline.
2. Cluster: CIS benchmark with `kube-bench` using the distro's profile, `kubescape scan`, namespaces without Pod Security enforcement, RBAC review (cluster-admin bindings, wildcard verbs, who can read secrets), namespaces without NetworkPolicy, and admission policy state.
3. Hosts: `sshd -T` for effective SSH config, `lynis audit system`, pending security updates, and firewall rule review.
4. CI and supply chain: actions pinned by SHA, `zizmor` on GitHub Actions workflows, token permissions, image signatures verified, SBOMs present.
5. Secrets: scan repos with `gitleaks git --redact` or trufflehog, check secret store key backups, and check controller versions with known issues. Never print a secret value.
6. External surface: port scan your own public IPs against an expected-ports list, check TLS config, and check certificate expiry.
7. Diff against the baseline. Triage only new findings as fix, accept with an expiry, or not applicable.
8. File issues. Update the baseline after triage.

Never: probe assets you do not own, attempt exploitation, or read Secret values.

Calls: **security-audit**, **kubernetes-health**, **ci-cd**, **docker**, **networking**.
Principles: pin-the-target, encode-lessons-in-structure.

**Reply:** new findings by severity, accepted risks with expiry, issues filed.
