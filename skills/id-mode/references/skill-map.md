# Domain skill map

Playbooks name domain skills in bold. Load a named skill when the step needs its domain. If it is not installed, use the fallback and report `skipped: <skill> not installed, used fallback`. Any skill with the same name works; the reference set is `iuliandita/skills`.

| Skill | Used for | Minimum fallback |
| --- | --- | --- |
| **terraform** | HCL, modules, state, providers, plan reading | `fmt -check`, `validate`, `plan -out`, `show -json`, and the vendor docs for the provider |
| **kubernetes** | Manifests, Helm, Kustomize, Gateway API, ArgoCD | `helm template`, `kustomize build`, `kubectl diff --server-side`, `kubeconform -strict` |
| **kubernetes-health** | Read-only cluster health | `kubectl get nodes,pods -A`, `kubectl get events -A --sort-by=.lastTimestamp`, `kubectl top` |
| **ansible** | Roles, playbooks, inventories, Vault | `ansible-lint`, `--syntax-check`, `--check --diff --limit` |
| **networking** | DNS, reverse proxies, VPNs, firewalls, routing | `dig`, `curl -v --resolve`, `openssl s_client -connect`, `ss -tlnp`, `ip route` |
| **opnsense-pfsense** | Firewall appliances | Draft the exact GUI or config change for the human; config export before any change |
| **ci-cd** | Pipelines, runners, bots, Actions pinning | The pipeline file and the forge's run logs (`gh run view --log-failed`, `glab ci view`) |
| **docker** | Images, Compose, registries, digests | `docker buildx imagetools inspect`, `docker compose config` |
| **observability** | Metrics, logs, alerts, SLOs, Prometheus, Grafana | PromQL via the HTTP API, `amtool check-config`, `promtool check rules` |
| **security-audit** | Secrets, IAM, supply chain, CVEs | `gitleaks git --redact`, `trivy image`, the advisory text |
| **virtualization** | Proxmox, KVM, libvirt, VM backups | `qm list`, `pct list`, `pvesh get`, `virsh list --all` (read verbs only) |
| **databases** | Engines, dumps, restores, upgrades | The engine's own dump and restore tools against a scratch instance |
| **message-queues** | Kafka, RabbitMQ, lag, replay | The broker's CLI or management API, read-only |
| **debug-triage** | Localizing a live fault | Bisect by layer per the `live-diagnosis` playbook |
| **git** | Branches, rebases, PRs and MRs, forges | `git`, `gh`, `glab` |
| **arch-linux**, **debian-ubuntu**, **rhel-fedora**, **nixos** | The target host's OS | The distro's package manager docs and `/etc/os-release` |
| **jevify**, **typesafe-ai** | Typed judgments at a playbook's Jev decision points | None needed: skip Jev and use the deterministic checks |
