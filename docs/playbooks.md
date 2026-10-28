# idstack playbook catalog

Status: design specs. The shipped playbooks are in [skills/id-mode/playbooks/](../skills/id-mode/playbooks/), in pstack's format. Where a spec names `idstack plan-summary` or `idstack judge`, the shipped playbooks use the `plan-reader` subagent and optional Jev decision points until the CLI exists.

Conventions used below:

- **Gate** means the block defined in [plan.md section 4](plan.md#4-the-safety-model): exact command, pinned target, blast radius, rollback, verification query, evidence. Then stop.
- **Calls** lists domain skills by name. A missing skill is reported as skipped with the inline fallback used.
- Where a playbook has a Jev decision point (plan reading, release notes, outgoing claims, log filtering, suspect changes, decommission evidence, public hygiene), the step runs `idstack judge` as defined in [plan.md section 9](plan.md#9-jev-decision-layer). Jev answers only tighten a gate. Without a key, the step uses its deterministic checks and says Jev was not used.
- Every playbook starts with two implicit steps: read the principles (pstack and idstack), and pin the target if the task touches a live system.
- Every playbook ends with pstack's Writing the reply, plus idstack's reply sections: **Target**, **State now** (current state, not a change narrative), **Evidence** (each claim labeled verified or inferred), **Held** (gates not passed and what each needs), **Next**.

## Change

### iac-change

For a Terraform or OpenTofu change, from edit to verified apply.

Owner line: you own the plan. Nothing applies that was not reviewed.

1. Find the repo's rules: does an agent ever apply here, is apply manual or CI-driven, which binary (Terraform or OpenTofu) and version, where state lives. Repo rules win.
2. State sanity before planning: backend reachable, state serial and lineage look current, no unexpected local state file. A state that looks older than the last known apply stops here. This is the failure mode behind the February 2026 production `destroy`.
3. Make the change. Prefer `moved`, `import`, and `removed` (with `destroy = false` when keeping the real resource) blocks over state commands, because they show up in the plan.
4. Static checks: `fmt -check`, `validate`, the repo's linters and scanners (tflint, trivy or checkov). Fix new findings or record why not.
5. Plan to a file: `plan -out=<name>.tfplan`, then `show -json` into `plan.json`. Read-only plans in shared state use the repo's lock convention.
6. Summarize with `idstack plan-summary plan.json` (or `plan-reader`): counts, every delete and replace, changes to stateful, IAM, and network resources, addresses outside the intended scope. Anything unexpected sends you back to step 3.
7. For multi-tenant or risk-grouped repos, split into targeted plans per group, one file each, lowest risk first.
8. Open the PR with the plan summary in the body. Merging does not apply unless the repo says it does.
9. **Gate:** apply the saved plan file, nothing else. A predicate grant can pass this gate only if `plan-summary` passes the predicate.
10. After apply, re-plan. Expect no changes. Anything else is drift or a partial apply: stop and report.
11. Run the verification queries from the gate. Log the result.

Never: apply without a saved plan, reuse a plan after any other apply to the same state, run `destroy` or state surgery under a grant.

Calls: **terraform**, **security-audit** (for IAM or network-heavy diffs).
Principles: plan-before-apply, pin-the-target, make-operations-idempotent, sequence-verifiable-units.
Reply: plan summary per group, what applied, re-plan result, held groups.

### gitops-change

For Kubernetes manifests, Helm values or charts, and Kustomize overlays delivered by ArgoCD or Flux.

Owner line: you own the rendered diff. Git is the only way in.

1. Find how the target is delivered: which ArgoCD app or Flux kustomization owns these files, auto-sync and prune settings, sync waves. If it is GitOps-managed, never `kubectl apply` it directly.
2. Make the change in git.
3. Render: `helm template` or `kustomize build` for every affected app.
4. Validate the render: `kubeconform -strict` with CRD schemas, the repo's linters and policy checks (kube-linter, Kyverno CLI, or conftest), if present.
5. Diff against live: `argocd app diff` (or `flux diff`, `kubectl diff --server-side` read-only). Use `plan-reader` for large diffs. Call out CRD changes, PVC and storage changes, RBAC, NetworkPolicy, and anything with `Prune=true` that would be deleted.
6. Open the PR with the render-and-diff summary.
7. **Gate** at merge if merge triggers auto-sync, else at sync.
8. After sync: compare the app's synced revision to the merged git commit, not just "Synced/Healthy". Wait for health with a timeout. Check the running image digests or config values that should have changed.
9. Rollback is `git revert` through the same path.

Calls: **kubernetes**, **kubernetes-health**.
Principles: plan-before-apply, prove-it-works, reversible-first.
Reply: apps affected, diff summary, synced revision vs. HEAD, health, held items.

### host-config-change

For Ansible roles and playbooks against hosts and VMs.

Owner line: you own convergence. A second run changes nothing.

1. Find the delivery path: run by hand, or applied by CI on merge. If CI applies on merge, the merge is the gate.
2. Make the change.
3. `ansible-lint` with the repo's profile, `--syntax-check`.
4. `--check --diff --limit <one canary host>`. Note tasks that check mode cannot predict (`command`, `shell`).
5. **Gate:** run on the canary.
6. Run the same play again on the canary. Expect `changed=0`. Anything else is an idempotence bug: fix before going wider.
7. **Gate:** the rest of the fleet with `serial`, restart-sensitive services last.
8. Verify per host with a read-only check of the service the change affects.

Calls: **ansible**, the matching OS skill for the target distro.
Principles: make-operations-idempotent, reversible-first, sequence-verifiable-units.
Reply: canary result, idempotence result, hosts converged, hosts held.

### edge-change

For DNS records, reverse proxy routes, firewall rules, VPN users and peers, TLS certificates, and IP allowlists, including the same change across several repos.

Owner line: you own reachability. Keep a way back in.

1. List every place the change must land (DNS zone, proxy config, firewall, several IaC repos for one allowlist). Find stale entries the change replaces.
2. Back up the current config: zone export, firewall config export, proxy config in git.
3. Confirm an out-of-band path exists (console, second VPN, a session kept open) before touching anything that could cut access.
4. Make the change in IaC where it lives in IaC. For appliances without an API, draft the exact change for the human to apply.
5. For DNS, lower TTL ahead of a cutover. For certificates, use a staging issuer first when available.
6. **Gate** per location. One rule at a time on firewalls, with a revert-on-timeout where the appliance supports it.
7. Verify from each side: `dig` against the authoritative server and a public resolver, `curl --resolve`, `openssl s_client` for the served chain and expiry, a connection test from each network segment, and the VPN client actually connecting.
8. Remove the stale entries found in step 1, gated.

Calls: **networking**, **opnsense-pfsense**, **terraform**.
Principles: reversible-first, pin-the-target, prove-it-works.
Reply: locations changed, verification per side, stale entries removed, held locations.

### dependency-bump

For a backlog of Renovate or Dependabot PRs, or a single chart, provider, module, or image bump.

Owner line: you own what the bump changes, not just that CI passed.

1. List open bot PRs. Classify each: patch, minor, major; image, chart, provider, module, action; stateful or not; does merge deploy.
2. For each non-trivial bump, read the release notes between the two versions for breaking changes, deprecations, and migrations.
3. For charts: diff default values between versions, render old and new with the repo's values, diff the renders, diff CRDs separately (Helm does not upgrade CRDs).
4. For providers and modules: run the plan and summarize it, as in `iac-change`.
5. For GitHub Actions: confirm the new ref is pinned by SHA and comes from the original repo.
6. Merge the ones that are green, low-risk, and do not deploy on merge, with short squash messages. Stop at the operator's stop line.
7. **Gate** for each bump whose merge deploys, and for every major.
8. If the bot has gone quiet, diagnose it read-only: bot logs, dashboard issue, config errors, rate limits, token expiry.

Calls: **ci-cd**, **kubernetes**, **terraform**, **docker**.
Principles: explain-the-number (for "CI is green"), sequence-verifiable-units.
Reply: table of bumps with class, risk, action taken; held bumps and why.

### upgrade

For a version upgrade of a cluster, platform component, managed service, hypervisor, or self-hosted app.

Owner line: you own the path back. Upgrade one unit, prove it, then the next.

1. Preflight from release notes: breaking changes, version skew rules, deprecated APIs, required intermediate versions. No skipping minor versions where the project forbids it.
2. Check for deprecated APIs in live manifests when upgrading Kubernetes.
3. Backups taken and verified for anything stateful in scope (see `restore-drill` for what "verified" means).
4. Write the rollback before starting, with how long it takes.
5. Pre-production or canary first: a non-prod environment, one node, one instance.
6. **Gate** per unit. Between units, health checks must pass: nodes Ready, workloads healthy, storage replicas rebuilt, error rates and latency back to baseline.
7. For node-by-node upgrades: cordon, drain with PDBs respected, upgrade, uncordon, wait for storage rebuild, next.
8. For managed services: provider maintenance window, provider backup, then upgrade.
9. When another agent owns the target environment, emit a handoff prompt for that agent instead of acting.

Calls: **kubernetes**, **virtualization**, **databases**, **message-queues**, the matching OS skill.
Principles: reversible-first, prove-the-restore, sequence-verifiable-units.
Reply: units upgraded, health between each, rollback readiness, held units.

### queue-burndown

For a queue of PRs or MRs to land in order, where some merges need a plan and apply.

Owner line: you own the merge frontier and the stop line.

1. Record the stop line the operator gave ("merge all, stop before apply", "stop at the first red plan").
2. List the queue with dependencies and order. Find which merges deploy and which need a manual apply after.
3. Per item, in order: rebase if needed, check CI, review threads resolved, merge with a short squash message.
4. After each merge that needs an apply: re-plan (the previous apply makes older plans stale), summarize, **Gate** or predicate grant.
5. Clean up after each item: delete merged branches, update the queue.
6. Stop at the stop line or the first item that fails a gate.

Overlay relation: runs pstack's `babysit` per item for conflicts, threads, and CI. Works with `gh` or `glab`.
Calls: **git**, **terraform**.
Principles: sequence-verifiable-units, plan-before-apply.
Reply: merged items, applied items with plan summaries, where it stopped and why, what is left.

### env-promotion

For replicating a change across environments (dev, QA, prod) where parity matters.

Owner line: you own the difference between environments. Make it intentional.

1. Diff the source and target environments for the component: values, versions, resources, secrets references, storage.
2. Classify every difference as intended (sizing, hostnames, secrets) or drift.
3. Port the change, keeping intended differences.
4. Render both environments and compare. The only remaining differences should be the intended list.
5. Continue through the target environment's change playbook (`iac-change` or `gitops-change`), with its gates.
6. Verify the target behaves like the source: same dashboards populated, same alerts loaded, same health.

Calls: **terraform**, **kubernetes**, **observability**.
Principles: model-the-domain (an explicit list of intended differences), prove-it-works.
Reply: intended differences, drift found, promotion state per environment.

### decommission

For removing a VM, host, app, cluster resource, bucket, DNS name, or account believed to be unused, or parking an app.

Owner line: "unused" is a hypothesis. Prove it before anything goes dark.

1. Gather evidence from several independent sources: traffic and connection metrics, logs, recent logins, DNS lookups, firewall and NAT rules pointing at it, references in IaC and config repos, tickets and docs, dependents in the cluster.
2. Decide park or tear down. Parking keeps data and config and stops the workload. Teardown removes it. A component another service depends on is parked, not torn down.
3. **Gate:** reversible step first (scale to zero through git, power off, rename with an `OFF-` prefix, disable the DNS name).
4. Soak period agreed with the operator. Watch for breakage.
5. **Gate:** teardown, with a final backup if any data is kept.
6. Remove every reference: monitoring targets, alerts, backups jobs, DNS, firewall rules, secrets, docs, inventory.

Calls: **virtualization**, **kubernetes**, **networking**.
Principles: reversible-first, prove-the-restore.
Reply: evidence per item, parked vs. removed, references cleaned, items held.

### secret-rotation

For rotating a credential, key, token, or certificate, and for responding to a leaked secret.

Owner line: you own every consumer. Rotation ends when the old value no longer works and nothing breaks.

1. Inventory consumers: which services, CI pipelines, IaC providers, and people use the secret. Where it is stored (sealed secret, SOPS file, vault, CI variable, cloud secret manager).
2. For a leak: revoke or rotate at the provider first, then check provider logs for use during the exposure window. Do not rewrite published git history; fix forward and rotate.
3. Create the new value at the source. Never print it, never pass it on a command line.
4. Update the store, then roll consumers. For sealed secrets, re-seal with the current key.
5. **Gate** for revoking the old value.
6. Verify: every consumer works with the new value, the old value is rejected, provider logs show no use of the old value after the switch.
7. Add a scanning rule if the leak pattern was not caught.

Calls: **security-audit**, **kubernetes**, **terraform**, **ansible**, **ci-cd**.
Principles: pin-the-target, prove-it-works.
Reply: consumers updated, old value status, exposure check result (for leaks).

## Diagnose

### live-diagnosis

For a live symptom (alert, outage, error spike, slow service, failed job) where the cause is unknown. Read-only.

Owner line: you own the diagnosis. Observe before you theorize, and change nothing.

1. Pin the target. Confirm VPN and access. Use read-only credentials if they exist.
2. Open a timeline file (UTC timestamps, one line per observation or command).
3. Define the symptom with a query that shows it (an error rate, a failing check, a log line count).
4. Bisect by layer: network and DNS, ingress and certificates, workload, storage, node, upstream dependency, recent changes (deploys, bumps, config, cert expiry). Each pass picks the split that rules out the most.
5. Bulk log and metric reading goes to cheap-tier subagents. Keep the reduced findings in the main thread.
6. Confirm the mechanism with evidence, not a plausible story.
7. If mitigation is needed now, propose it as a **Gate** (rollback, failover, scale, restart) and hand to `incident`.
8. Hand the fix to the matching change playbook.

Calls: **debug-triage**, **kubernetes-health**, **observability**, **networking**, **databases**.
Principles: fix-root-causes, attack-the-premise, guard-the-context-window.
Reply: symptom query, mechanism with evidence, ruled-out causes, proposed mitigation and fix.

### incident

For user-visible impact that needs coordination: declare, mitigate, communicate, learn.

Owner line: you own the timeline. Mitigate first, root-cause second.

1. Declare: impact in user terms, severity from impact, start time.
2. Run `live-diagnosis` for the cause, in parallel with mitigation.
3. **Gate** each mitigation. After it, hold the symptom query below threshold for an agreed period before calling it mitigated.
4. Drafts, never sent by the agent: a technical update, a short non-technical summary, and an external message for customers or vendors when needed. Numbers over adjectives. Do not overstate what was done or verified. Have a second model check external drafts before the operator sends them.
5. Postmortem when it meets the trigger (user-visible downtime, data loss, manual intervention, monitoring missed it): impact, timeline, contributing causes, what went well, action items.
6. Every action item becomes a tracked issue with an owner.

Calls: **debug-triage**, **observability**.
Principles: fix-root-causes, encode-lessons-in-structure.
Reply: incident state, timeline summary, mitigations with evidence, drafts, issues filed.

## Assure

### restore-drill

For proving backups exist, are fresh, are independent of what they protect, and actually restore.

Owner line: you own the restore, not the backup job's exit code.

1. Inventory backup sources: VM backups, cluster resource backups, volume backups, datastore snapshots, database dumps, file backups, managed-service backups. For each, record RPO and RTO targets (operator signs off).
2. Freshness: last successful run per source, compared to its RPO.
3. Independence: can the credentials or IaC that manage the source also delete the backup? Is there an off-site copy with different credentials? Is the cluster datastore token backed up with the snapshot?
4. **Gate:** restore into isolation (scratch namespace, isolated VM network, throwaway database). Never over the live target.
5. Prove the data: application-level checks (row counts, checksums, a health endpoint, opening a file), not "PVC Bound" or "restore Completed".
6. Measure the restore time against RTO.
7. **Gate:** clean up the drill resources.
8. Record the drill result with date and evidence so the next drill can compare.

Calls: **virtualization**, **databases**, **kubernetes**.
Principles: prove-the-restore, explain-the-number.
Reply: table per source with freshness, independence, restore result, measured RTO.

### drift-audit

For finding where reality differs from code: IaC state, host config, GitOps apps, and edits made in UIs.

Owner line: you own the list. Report drift; do not fix it here.

1. Terraform and OpenTofu: `plan -detailed-exitcode` per state, read-only. Exit code 2 is drift; summarize it.
2. Ansible: `--check --diff` per inventory group.
3. GitOps: apps OutOfSync, apps whose synced revision is behind HEAD, resources with ignored differences, resources created outside git.
4. UI edits: dashboards and alert rules edited in the UI versus their code, cluster settings changed by hand.
5. Classify each drift: intended but not codified, accidental, or dangerous.
6. File one issue per drift cluster. Fixes go through the change playbooks.

Calls: **terraform**, **ansible**, **kubernetes**, **observability**.
Principles: encode-lessons-in-structure.
Reply: drift table by system and class, issues filed.

### observability-audit

For checking that monitoring would catch what matters, and that alerts are worth reading.

Owner line: you own the gaps. An unmonitored failure is a future incident.

1. Coverage: every service has metrics, logs, and health checks. Dead scrape targets.
2. Watch the watchers: alerts exist for backup failures, certificate expiry, disk and storage growth, NFS or network mounts, the monitoring stack itself, and the alert delivery path.
3. Alert hygiene: noisiest alerts over 30 days, flapping alerts, rules that never fired (check retention first), rule evaluation failures, missing runbook links.
4. SLOs: where they exist, check burn-rate alert windows. Where they should exist, propose them.
5. Routing: grouping, inhibition, repeat intervals, digest vs. page split. Validate config with `amtool`.
6. Cardinality: top series by metric name, head series growth.
7. File issues for gaps. Changes go through `gitops-change`.

Calls: **observability**.
Principles: explain-the-number, encode-lessons-in-structure.
Reply: gap table, alert hygiene table, issues filed.

### security-posture

For a periodic security check of clusters, hosts, CI, secrets, and the external surface, compared to the last baseline.

Owner line: you own what is new since last time.

1. Cluster: CIS benchmark (kube-bench with the distro's profile), Kubescape, namespaces without Pod Security enforcement, RBAC review (cluster-admin bindings, wildcard verbs, who can read secrets), namespaces without NetworkPolicy, admission policy state.
2. Hosts: SSH config (`sshd -T`), Lynis, pending security updates, firewall rule review.
3. CI and supply chain: actions pinned by SHA, workflow audit (zizmor for GitHub Actions), token permissions, image signatures verified, SBOMs present.
4. Secrets: scan repos (gitleaks or trufflehog), secret store key backups, controller versions with known issues.
5. External surface: port scan of your own public IPs against an expected-ports list, TLS config, certificate expiry.
6. Diff against the stored baseline. Triage only new findings: fix, accept with an expiry, or not applicable.
7. File issues. Fixes go through change playbooks. Update the baseline after triage.

Scope: defensive, own assets only.
Calls: **security-audit**, **kubernetes-health**, **ci-cd**, **docker**, **networking**.
Principles: encode-lessons-in-structure.
Reply: new findings by severity, accepted risks with expiry, issues filed.

### vuln-response

For a specific CVE or advisory: where are we exposed, and is it fixed.

Owner line: you own the proof that the vulnerable version is gone from what runs.

1. Find every place the component runs: image SBOMs, chart renders, host package lists.
2. Prioritize: listed in CISA KEV, EPSS score, internet-facing or not, reachable or not, vendor fix available.
3. Patch through `dependency-bump` or `upgrade`.
4. Verify: rescan the new artifact, confirm running pods use the new digest, confirm host package versions.
5. If no fix exists: mitigation (disable the feature, restrict exposure) as a gate, and an issue with a review date.

Calls: **security-audit**, **docker**, **kubernetes**.
Principles: prove-it-works.
Reply: exposure table, patched locations with evidence, mitigations and their review dates.

### capacity-cost

For storage growth, resource right-sizing, cloud spend, and licenses or seats.

Owner line: you own the forecast and the evidence behind each cut.

1. Storage: days-to-full per filesystem, volume, pool, and hypervisor storage from growth trends. Flag anything under the agreed horizon.
2. Compute: requests vs. actual use (krr or VPA in recommend mode), CPU throttling, OOM kills.
3. Cloud spend: idle volumes, unattached IPs, oversized managed databases, unused buckets, by tag or project.
4. Licenses and seats: inventory from real usage (hosts that are off, users who left), not from the billing page alone.
5. Propose changes with evidence. Changes go through change playbooks.

Calls: **observability**, **virtualization**, **kubernetes**.
Principles: explain-the-number.
Reply: forecast table, right-sizing proposals, savings with evidence.

### readiness-review

For deciding whether a new service is ready to depend on. Sized for a homelab or small team.

Owner line: you own the checklist and the evidence behind each box.

1. Owner and purpose documented.
2. Health probes, resource requests and limits, PodDisruptionBudget where relevant.
3. Metrics, logs, dashboard, alerts with runbook links.
4. Backup configured and a restore drill passed.
5. Secrets in the secret store, not in git.
6. Rollback path tested.
7. Exposure reviewed: ingress, authentication, NetworkPolicy.
8. Upgrade path known: who bumps it, how breaking changes are found.

Calls: **kubernetes**, **observability**, **security-audit**.
Reply: pass, fail, or n/a per item with evidence; blocking items.

## Operate and meta

### agent-hosting

For running autonomous agents or bots on your own infrastructure.

Owner line: you own what each agent can reach.

1. Inventory agents: where they run, what identity they use, what tokens, kubeconfigs, and SSH keys they hold.
2. Least privilege: read-only by default, write access scoped to named namespaces or repos, no cluster-admin, no shared human credentials.
3. Containment: resource limits, network policy, no access to secret stores beyond their own.
4. Audit: actions logged somewhere the agent cannot edit.
5. Lifecycle: how tokens are rotated, how an agent is disabled quickly.
6. Changes go through change playbooks.

Calls: **kubernetes**, **security-audit**.
Principles: pin-the-target, reversible-first.
Reply: reach table per agent, over-privileged items, issues filed.

### closeout

For the end of a work session.

Owner line: you own leaving nothing ambiguous.

1. Everything intended is committed and pushed. Nothing intended is only local.
2. PR and MR states: merged, open with reason, or abandoned.
3. Gates still held and what each needs.
4. Branch and worktree sweep, local and remote: list merged or abandoned ones, delete only after the operator confirms.
5. Lessons: repo-specific lessons go to the repo's agent instructions (tracked or local-only, by sensitivity), cross-project facts to the operator's memory store if one is configured.
6. A short "what's left" list.

Overlay relation: uses pstack's `worktree-cleanup` for the sweep.
Reply: the what's-left list first, then the state lines.

## Overlays

Each overlay starts by reading the shared pstack playbook, then applies these gates. idstack gates win on conflict.

- **bug-fix:** for infra defects, "reproduce" means observing the defect in live state with read-only commands or a fixture. The fix is delivered through the matching change playbook with its gates. Keep the failing check first in the commit order when one exists.
- **babysit:** works with `gh` or `glab`. A merge that deploys is a gate. CI retriggers are classified first (flake, infra, real) and limited to one fresh run.
- **shipping:** when merges deploy, landing a stack is a series of gated writes, one per PR, with verification between each.
- **opening-a-pr:** the repo's conventions win over pstack's PR body format. Conventional commit titles. Reference the tracking issue. No AI attribution lines. Before pushing to a public repo, check the diff and the PR text for private hostnames, IPs, internal URLs, and secrets.
- **autonomous-run:** the exit predicate must include a stop line before any state-mutating step not covered by a grant. Reaching the stop line is a successful stop, not a dead end.
- **pause-safely:** the checkpoint records pinned targets, held gates, saved plan files and their staleness, and any partly applied change.
