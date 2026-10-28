---
name: id-mode
description: >-
  Infra, DevOps, and SRE work on top of pstack: plan before apply, pin the
  target, gated state changes, verification against live state, and evidence a
  reviewer can rerun. Use for /id-mode or idstack, and for Terraform, OpenTofu,
  Kubernetes, Helm, GitOps, Ansible, DNS, firewall, VPN, certificate, upgrade,
  dependency-bump, incident, backup, drift, monitoring, security-posture, and
  capacity work.
disable-model-invocation: true
---

# id mode

Thin router over pstack's `poteto-mode`. Shared principles, triggers, reply style, and playbook machinery live there; open them from pstack. idstack gates win on conflict with pstack. The repo's own rules win over idstack. When rules disagree, the strictest one wins.

**Requires** pstack. Check first with [references/requirements.md](references/requirements.md), which also says how to reach pstack's hidden skills. Missing: stop and tell the user how to install it. In the same check, run `idstack --help` once. When it runs, plan summaries, grant predicates, and Jev decision points go through the `idstack` CLI; the `jq` and manual forms are only for when it does not.

## Shared machinery (do not restate)

| Layer | Where |
| --- | --- |
| Principles index, non-negotiable triggers, Writing the reply, Subagents, playbook catalog | pstack `poteto-mode` skill |
| Shared playbooks | pstack `poteto-mode/playbooks/<name>.md` |
| Principle leaves | pstack `principle-*` skills, and idstack's four below |
| Model per role | pstack's model file (`~/.claude/rules/pstack-models.md` on Claude Code, `~/.agents/pstack-models.md` elsewhere) |
| Domain knowledge (how Terraform, Kubernetes, Ansible work) | Domain skills, by name, per [references/skill-map.md](references/skill-map.md) |
| Repo rules | The repo's `AGENTS.md` or `CLAUDE.md`, contributing docs, and CI config |

**Playbook resolution.** A playbook `<name>` resolves to `playbooks/<name>.md` next to this file when it exists. If pstack has a playbook of the same name, the local file is an overlay: read pstack's playbook first, then the overlay. Otherwise use pstack's playbook unchanged.

## Non-negotiables

1. Open a todolist. Item 1: read the **Principles** section of pstack's `poteto-mode`, then idstack's four principles below. Cite each principle you apply with the choice it changed, and load its leaf when you apply it.
2. Touching a live system: pin the target per [references/targets.md](references/targets.md) before the first command against it, and record it as item 2.
3. Match a playbook from the catalog below, then pstack's. Copy its steps into the todolist verbatim before any task-specific items. A skipped step stays with `skip: <reason>`. No playbook fits: pstack's **figure-it-out** skill, with the gates below still applying.
4. Apply pstack's non-negotiable triggers, except where an idstack gate overrides them.
5. Classify every action per [references/gates.md](references/gates.md). State-mutating actions stop at a gate block.
6. Keep evidence and write the reply per [references/evidence.md](references/evidence.md).
7. Call domain skills by name. A missing one is reported as `skipped: <skill> not installed, used fallback`, never as a pass.

### idstack gates (win on conflict)

- **Autonomy is narrower.** pstack's "just do it" covers reads and reversible writes only. A git event that triggers automation able to deploy or change infrastructure is state-mutating. pstack's `principle-never-block-on-the-human` does not apply to state-mutating actions.
- **Approval is per command and per turn.** Silence is not approval. "Don't stop", "run until done", and similar overrides extend reversible work up to a stop line; they never approve a state-mutating action.
- **Grants are explicit.** A stop line or a predicate grant, checked mechanically against the reviewed artifact and logged. Grants never cover destroy, state surgery, data deletion, or root credentials. See [references/gates.md](references/gates.md).
- **Plan before apply.** The only input to a state-mutating command is a reviewed artifact from a read-only step. A stale artifact is produced again, never reused.
- **Live state over proxies.** A green CI job, "Synced/Healthy", or a merged PR is not proof. Verify the live state against the intended state.
- **Secrets stay hidden.** Never read Secret values, print them, or pass them on a command line.
- **One estate per session.** Targets from unrelated estates (a work account and a homelab, two customers) never mix in one session.
- **Jev only tightens.** When the **jevify** or **typesafe-ai** skill and a `TYPESAFE_API_KEY` are available, a playbook may ask Jev typed questions at its named decision points. An answer can add a stop, a finding, or an ordering. It never approves a write, clears a finding, or proves something is safe or unused. A failed call or an answer between the thresholds counts as the strict outcome. Run a decision point with `idstack judge <battery> <items.json>`; `--example` prints the item shape, and exit 4 means no key. Without Jev, say it was not used.

## Catalog

**Change.** Each ends at a gate before anything mutates.

- **iac-change.** A Terraform or OpenTofu change, from edit to verified apply.
- **gitops-change.** Kubernetes manifests, Helm values or charts, and Kustomize overlays delivered by ArgoCD or Flux.
- **host-config-change.** Ansible roles and playbooks against hosts and VMs.
- **edge-change.** DNS records, reverse proxy routes, firewall rules, VPN peers, TLS certificates, and IP allowlists, including the same change across several repos.
- **dependency-bump.** A backlog of Renovate or Dependabot PRs, or one chart, provider, module, image, or action bump.
- **upgrade.** A version upgrade of a cluster, platform component, managed service, hypervisor, or self-hosted app.
- **queue-burndown.** A queue of PRs or MRs to land in order, where some merges need a plan and apply.
- **env-promotion.** Carrying a change across environments (dev, QA, prod) where parity matters.
- **decommission.** Removing or parking a VM, host, app, cluster resource, bucket, DNS name, or account believed to be unused.
- **secret-rotation.** Rotating a credential, key, token, or certificate, and responding to a leaked secret.

**Diagnose.** Read-only until a gate.

- **live-diagnosis.** A live symptom (alert, outage, error spike, slow service, failed job) with an unknown cause.
- **incident.** User-visible impact that needs coordination: declare, mitigate, communicate, learn.

**Assure.** Periodic checks that report and file issues; fixes go through the change playbooks.

- **restore-drill.** Prove backups are fresh, independent of what they protect, and actually restore.
- **drift-audit.** Find where reality differs from code: IaC state, host config, GitOps apps, UI edits.
- **observability-audit.** Check that monitoring would catch what matters and that alerts are worth reading.
- **security-posture.** Periodic check of clusters, hosts, CI, secrets, and the external surface against the last baseline.
- **vuln-response.** One CVE or advisory: where are we exposed, and is it fixed.
- **capacity-cost.** Storage growth, right-sizing, cloud spend, and licenses or seats.
- **readiness-review.** Decide whether a new service is ready to depend on.

**Operate.**

- **agent-hosting.** Running autonomous agents or bots on your own infrastructure.
- **closeout.** The end of a work session.

**Overlays on pstack playbooks:** `bug-fix`, `babysit`, `shipping`, `opening-a-pr`, `autonomous-run`, `pause-safely`. Opening a PR runs at the end of every change playbook, through its overlay.

**pstack playbooks used unchanged:** `investigation`, `session-pickup`, `multi-phase-plan`, `orchestrate`, `worktree-cleanup`, `eval`, `authoring-a-skill`, and the `figure-it-out` skill.

**Not for infra:** `visual-parity`, `perf-issue` (app performance belongs to a performance skill), `hillclimb`, `trace-forensics`, `prototype` (infra prototypes are a scratch namespace or a throwaway VM, covered inside `upgrade` and `restore-drill`).

## Principles

idstack's four leaves:

- **Plan Before Apply** (**principle-plan-before-apply**). Any state-mutating command. Its only input is a reviewed artifact from a read-only step.
- **Pin the Target** (**principle-pin-the-target**). Any command against a live system. Name it, pass it explicitly, check it matches the task.
- **Prove the Restore** (**principle-prove-the-restore**). Backups, upgrades, decommissions. A backup that has not been restored is a hypothesis.
- **Reversible First** (**principle-reversible-first**). Choosing between ways to make a change. Prefer the step that can be undone.

pstack leaves the playbooks name most: `make-operations-idempotent`, `prove-it-works`, `fix-root-causes`, `sequence-verifiable-units`, `separate-before-serializing-shared-state`, `encode-lessons-in-structure`, `build-the-lever`, `guard-the-context-window`, `attack-the-premise`, `explain-the-number`.

## Subagents

pstack's Subagents section applies, with these deltas.

- Spawn delegates inside a playbook step as `id-agent` (Claude Code: `idstack:id-agent`). On a harness without it, use the default subagent and open the brief with: read this file's absolute path and pstack's `poteto-mode/SKILL.md` before any work.
- `plan-reader` summarizes a plan file, rendered diff, or check-mode output. `change-verifier` checks a change landed, from live state. Both are read-only. The verifier is never the agent that made the change.
- Every delegate that touches a live system gets the pinned target, read-only credentials when they exist, and the read-only command list for its step. A cross-provider worker that cannot get those does read-only analysis of evidence already collected, nothing live.
- Models come from pstack's model file, by role:

| idstack job | pstack role line |
| --- | --- |
| Bulk read-only evidence (logs, metrics, inventories) | `why investigators` |
| Writing IaC, manifests, roles, configs | `feature, refactoring` |
| `plan-reader` | `judgment and prose`; `hardest tasks` when the plan has deletes, replaces, IAM, or network policy changes |
| `change-verifier` | `swarm workers`, from a family other than the author's |

## Writing the reply

pstack's Writing the reply applies. Every idstack playbook's reply also carries the sections in [references/evidence.md](references/evidence.md): Target, State now, Evidence, Held, Next.
