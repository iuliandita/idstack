# idstack plan

Status: draft for review. Date: 2026-10-27.

This document is the design and roadmap. The per-playbook specs live in [playbooks.md](playbooks.md).

## Contents

1. Goal and non-goals
2. What exists today
3. Architecture
4. The safety model
5. Principles
6. Playbook set
7. Subagents and model routing
8. Guardrails in the execution layer
9. Packaging for Claude Code, Codex, and OpenCode
10. Repository layout
11. The `idstack` CLI
12. Testing and evals
13. Release and versioning
14. Roadmap
15. Risks
16. Open decisions
17. Sources

## 1. Goal and non-goals

**Goal.** Give a coding agent a disciplined, verifiable way to do infrastructure work: IaC changes, GitOps, host config, network and edge changes, upgrades, incidents, backups, drift, monitoring, security posture, capacity, and cost. The agent should leave behind evidence a reviewer can rerun, and it should never mutate shared state without a gate the human can see.

**Shape.** A thin router over pstack's `poteto-mode`, plus infra playbooks, overlays on a few pstack playbooks, four new principles, three subagents, an optional guard hook, and a small CLI. Domain knowledge (how Terraform, Kubernetes, Ansible, and Prometheus work) stays in separate domain skills; idstack holds the process.

**Audience.** First, one operator running a k3s homelab and a work estate on managed cloud. Second, anyone running similar stacks. Playbooks are generic: no hostnames, IPs, or org topology.

**Non-goals.**

- Not a replacement for pstack. idstack does not restate pstack's principles, reply style, or subagent rules.
- Not a domain reference. No Terraform tutorial, no Kubernetes cookbook.
- Not an autonomous operator. idstack makes the agent faster and more careful. It does not remove the human from state-mutating decisions unless the human grants that for a specific, checkable condition.
- Not offensive security. Security playbooks are posture checks, hardening, and response.
- Not tied to one vendor. Cloud-specific steps are written as "the provider's equivalent" with examples.

## 2. What exists today

**pstack** (MIT, `cursor/plugins`, version 0.15.35 at time of writing) ships a router skill (`poteto-mode`), 23 playbooks, 24 principle skills, workflow skills (`how`, `why`, `architect`, `arena`, `swarm`, `interrogate`, `show-me-your-work`, `figure-it-out`), and two subagents. Its playbooks assume app development: reproduce through a UI or CLI control skill, delegate code to a fast model, and land PRs through `gh`. Its autonomy rules say reversible work proceeds without asking and only deploys, force-pushes, and deletions pause.

pstack only generates a Claude Code tree. There is no official Codex or OpenCode packaging; community mirrors fill that gap.

**The layering precedent is `dyl-stack`**, a sibling plugin in the same repo. Its router says: "Thin router over pstack's `poteto-mode`. Shared principles and playbook machinery live there; open them from pstack. Dylan gates win on conflict." A playbook name resolves to a local overlay file if one exists (read the shared playbook first, then the overlay), else to the shared file. A `requirements.md` checks that pstack is installed and stops if it is not. idstack copies this pattern.

**Infra skill packs exist but are reference material.** HashiCorp's official agent skills, antonbabenko's terraform-skill, AWS and Azure plugin bundles, and several community Kubernetes triage skills teach the domain. None ships a router with playbooks, verification gates, and enforced guardrails. Only one of them carries tests.

**Agent infra incidents are real.** In February 2026 a coding agent ran `terraform destroy` against production after a stale state file was restored, and took the automated snapshots with it because the same config managed them. The common advice from practitioners and the one research paper found (AOI, arXiv 2603.03378) is the same: read-only diagnosis by default, writes behind a reviewed artifact, and enforcement in the execution layer rather than in prompt text.

**Gaps idstack fills:**

1. A router and playbook layer for ops work.
2. Guardrails that ship with the skills and are enforced by hooks, not only by prose.
3. A read-only diagnosis mode with an explicit escalation path to a gated write.
4. Backup independence and restore proof as a first-class check.
5. Playbooks that carry their own tests.

## 3. Architecture

```
user
  -> /idstack:id-mode <task>                 router skill, slash-only
       reads pstack poteto-mode               shared principles, triggers, reply style
       reads id-mode references               gates, evidence, skill map, requirements
       matches a playbook
         idstack playbook                     playbooks/<name>.md in id-mode
         or overlay                           shared pstack playbook first, then overlay
         or shared pstack playbook            unchanged
       opens todo list from playbook steps
       calls domain skills by name            terraform, kubernetes, ansible, observability, ...
       spawns id-agent / plan-reader / change-verifier
       writes evidence log                    pstack show-me-your-work
       stops at gates
```

**Router: `id-mode`.** A slash-only skill (`disable-model-invocation: true`), invoked as `/idstack:id-mode` in Claude Code. It mirrors `dyl-mode`:

- Item 1 of every todo list: read the Principles section of pstack's `poteto-mode`, then idstack's principles.
- Match a playbook from idstack's catalog first, then pstack's.
- Apply pstack's non-negotiable triggers, except where an idstack gate overrides them.
- idstack gates win on conflict. The main conflicts are with pstack's Autonomy section ("just do it" for reversible work) and the `never-block-on-the-human` principle, because idstack classifies more actions as state-mutating (section 4).
- Repo instructions win over idstack. If a repo's `AGENTS.md` says agents never apply, the agent never applies, even with a grant. The strictest rule present wins.

**Name.** `id-mode` reads as `/idstack:id-mode`. The agent is `id-agent`. This avoids `/idstack:idstack-mode`.

**Overlays.** A file in `id-mode/playbooks/` with the same name as a pstack playbook is an overlay. It opens with "Read the shared playbook first: pstack `poteto-mode/playbooks/<name>.md`. Then apply these gates. They win on conflict." Overlays planned: `bug-fix`, `babysit`, `shipping`, `opening-a-pr`, `autonomous-run`, `pause-safely`.

**Domain skills are soft dependencies.** Each playbook names the domain skills it calls in bold (`use **terraform**`). `id-mode/references/skill-map.md` lists every domain skill idstack calls, what it is used for, and the minimum inline fallback if it is missing. A missing domain skill is reported as `skipped: <skill> not installed, used fallback`, never as a pass. The reference set is `iuliandita/skills`, but any skill with the same name works.

**pstack is a hard dependency.** If `setup-pstack` is not in the skill list (pstack hides most skills, so this is the detection hook pstack and `dyl-stack` use), `id-mode` stops and tells the user how to install it. Path convention for hidden pstack skills: `<setup-pstack dir>/../poteto-mode/SKILL.md`.

**Cursor terms in pstack.** pstack skills mention Cursor-only tools (`Task`, `/loop`, Bugbot, cloud agents). On Claude Code, pstack's generated tree already injects an adapter line. idstack inherits that and adds nothing. idstack's own files use harness-neutral wording ("spawn a subagent", "a wake mechanism").

## 4. The safety model

This is the core of idstack. Every action falls into one of three classes.

| Class | Examples | Rule |
| --- | --- | --- |
| Read | `get`, `describe`, `logs`, `plan`, `diff`, `template`, `--check`, PromQL, `dig`, `openssl s_client`, scans of your own assets | Free. Bounded (time ranges, `--tail`, limits). Never read Secret values. |
| Reversible write | branch, commit, PR or MR, local render, scratch namespace restore, draft message, issue | Free, unless it triggers a deploy (see below). |
| State-mutating | `apply`, `destroy`, state surgery, `sync` to a shared env, `delete`, `scale`, `drain`, `rollout restart`, `helm upgrade`, Ansible without `--check`, firewall rule change, DNS record change, secret rotation, reboot, `qm destroy`, sending an external message, merging where merge triggers a deploy | Always gated. |

**Merge can be a write.** In repos where a merge to the main branch deploys (CI applies Ansible on push, ArgoCD auto-syncs), the merge is state-mutating. Every change playbook's first step finds out whether merge equals deploy for the target repo and records it.

**A gate** shows, in one block:

- the exact command,
- the pinned target (context, account, workspace, host),
- the blast radius (what it touches, who notices),
- the rollback (command or procedure, and how long it takes),
- the verification query that proves it worked,
- the evidence it rests on (saved plan file, rendered diff, check-mode output).

The agent then stops. Approval is per command and per turn. Approval does not carry into later turns. Silence is not approval.

**Grants.** The operator often says things like "merge all of them, then stop before apply" or "if the plan is green, apply". idstack makes these explicit:

- **Stop line.** "Run until X, then stop." Recorded as the first todo item. The agent does reversible work freely up to the line.
- **Predicate grant.** "Apply if the plan shows only X." The agent turns this into a checkable predicate before running anything (for Terraform: zero `delete` and `replace` actions in `plan.json`, and every changed address inside a named set). It checks the predicate mechanically against the artifact, and logs the check. Anything outside the predicate stops at a normal gate.
- Grants are scoped to the current task. They never cover `destroy`, state surgery, deleting data, or rotating root credentials.

**Pin the target.** Before the first command against a live system, the agent records which cluster, account, workspace, or host it is pointed at, and checks it matches the task. Every subsequent command passes the target explicitly (`--context`, `-chdir`, `--limit`). Work and homelab targets never mix in one session.

**Live state over proxies.** A green CI job, an ArgoCD "Synced/Healthy", or a merged PR is not proof that the change landed. Verification compares the live state to the intended state: synced revision against git HEAD, running image digest against the built one, a re-plan that shows no changes, a query that returns the new value.

## 5. Principles

idstack adds four principle skills. Each is short, shaped like pstack's (claim, Why, The idea, The test).

1. **principle-plan-before-apply.** The only input to a state-mutating command is a reviewed artifact produced by a read-only step: a saved plan file, a rendered diff, check-mode output. A stale artifact is re-produced, never reused. Apply exactly what was reviewed.
2. **principle-pin-the-target.** Name the target before touching it, pass it explicitly on every command, and check it matches the task. An implicit default context is a bug.
3. **principle-prove-the-restore.** A backup that has not been restored is a hypothesis. Backups must be independent of the thing they protect: different credentials, different lifecycle, not managed by the same IaC that could destroy the source.
4. **principle-reversible-first.** Prefer the step that can be undone: park before teardown, power off before delete, warn and audit before enforce, canary before fleet, one rule at a time.

Mapped, not duplicated. idstack names these existing pstack principles in its playbooks: `make-operations-idempotent`, `prove-it-works`, `fix-root-causes`, `sequence-verifiable-units`, `separate-before-serializing-shared-state`, `encode-lessons-in-structure`, `build-the-lever`, `guard-the-context-window`, `attack-the-premise`, `explain-the-number`.

## 6. Playbook set

The full spec for each playbook is in [playbooks.md](playbooks.md). This is the catalog with the evidence behind each choice. "Usage" means the playbook is backed by recurring work in the maintainer's own agent history (about 3,700 prompts over two months), summarized generically.

### Change (write path)

| Playbook | For | Basis |
| --- | --- | --- |
| `iac-change` | Terraform or OpenTofu change, plan through verified apply | usage: the core work loop |
| `gitops-change` | Kubernetes manifests, Helm, Kustomize via ArgoCD or Flux | usage |
| `host-config-change` | Ansible roles and playbooks against hosts | usage |
| `edge-change` | DNS, reverse proxy, firewall, VPN, certificates, allowlists | usage |
| `dependency-bump` | Renovate or Dependabot triage, chart, provider, and image bumps | usage: very frequent |
| `upgrade` | Cluster, platform, managed service, hypervisor, or app version upgrade | usage |
| `queue-burndown` | Walk a queue of PRs or MRs to merged, with per-item plan and apply gates | usage: the largest single work pattern |
| `env-promotion` | Replicate a change across dev, QA, prod with parity checks | usage |
| `decommission` | Prove something is unused, park it, then tear it down | usage |
| `secret-rotation` | Rotate a credential and every consumer, including the leaked-secret path | usage + research |

### Diagnose (read path)

| Playbook | For | Basis |
| --- | --- | --- |
| `live-diagnosis` | Read-only triage of a live symptom to a mechanism | usage + research |
| `incident` | Declare, mitigate, communicate, postmortem, action items | usage + research |

### Assure (periodic)

| Playbook | For | Basis |
| --- | --- | --- |
| `restore-drill` | Prove backups are fresh, independent, and restorable | research + known gap |
| `drift-audit` | IaC against reality across Terraform, Ansible, GitOps, and UI edits | usage + known gap |
| `observability-audit` | Coverage, alert hygiene, SLOs, runbook links, monitoring the monitors | usage + research |
| `security-posture` | Cluster, host, supply chain, secrets, external surface; diff against baseline | usage + research |
| `vuln-response` | Triage a CVE across images, charts, and hosts, patch, verify | research |
| `capacity-cost` | Storage forecast, right-sizing, cloud spend, license and seat audit | usage |
| `readiness-review` | Production readiness check for a new service | research |

### Operate and meta

| Playbook | For | Basis |
| --- | --- | --- |
| `agent-hosting` | Run autonomous agents on infra: identity, least privilege, audit of reach | usage: growing theme |
| `closeout` | End-of-session ritual: commit, merge state, branch and worktree sweep, lessons, what's left | usage: near-daily |

### Overlays on pstack playbooks

| Overlay | Infra delta |
| --- | --- |
| `bug-fix` | Reproduce means observe the defect in live state read-only; the fix goes through the matching change playbook. |
| `babysit` | Forge-agnostic: `gh` or `glab`. A merge that deploys is a gate. |
| `shipping` | Landing a stack where merges deploy is a sequence of gated writes, one per PR. |
| `opening-a-pr` | Repo conventions win: conventional commits, issue references (`Closes #NN`), no AI attribution, short squash messages, public-repo hygiene check before push. |
| `autonomous-run` | The exit predicate must include a stop line before any state-mutating step not covered by a grant. |
| `pause-safely` | Record pinned targets, held gates, and any half-applied state. |

### Kept from pstack unchanged

`investigation`, `session-pickup`, `multi-phase-plan`, `figure-it-out` (for anything no playbook fits), `orchestrate`, `worktree-cleanup`, `eval`, `authoring-a-skill`.

### Not used for infra

`visual-parity`, `perf-issue` (use `performance-debugging` for apps), `hillclimb`, `trace-forensics`, `prototype` (infra prototypes are a scratch namespace or a throwaway VM, covered inside `upgrade` and `restore-drill`).

## 7. Subagents and model routing

Three subagents. Each is generated per harness from one neutral source file.

| Agent | Job | Tools | Tier |
| --- | --- | --- | --- |
| `id-agent` | Wrapper for any delegate spawned inside an idstack playbook. Reads `id-mode` and pstack `poteto-mode` before work. The idstack analog of `poteto-agent`. | inherits | per task |
| `plan-reader` | Turns a plan file, rendered diff, or check-mode output into a summary: counts by action, every destroy or replace, every change to stateful or security-relevant resources, anything outside the stated scope. Read-only. | read, bash for read-only commands | cheap or balanced |
| `change-verifier` | Independently verifies a change landed, from the live state, against the stated verification queries. Never the agent that made the change. Read-only. | read, bash for read-only commands | balanced, different family from the author when available |

**Model roles.** idstack reads pstack's model rule file when present (`~/.claude/rules/pstack-models.md` on Claude Code) and adds its own optional file, `idstack-models.md`, with three roles: `evidence` (bulk read-only collection), `plan reading`, `verification`. Missing roles fall back to tiers, not model names:

- `evidence`: the cheapest capable tier.
- `plan reading`: balanced tier. Escalate to the strongest tier when the plan contains destroys, replaces, IAM, or network policy changes.
- `verification`: balanced tier, from a different model family than the author when one is available.

Defaults never name a specific vendor model in shipped files. A setup skill (`/idstack:setup`) detects available models and writes the rule file, like `setup-pstack`.

## 8. Guardrails in the execution layer

Prose rules are not enough. idstack ships an optional guard hook.

**What it does.** A pre-tool-use hook inspects shell commands. If a command matches a state-mutating pattern (section 4) for a known infra CLI, the hook returns "ask" with a one-line reason, so the harness shows its own permission prompt. Without a match, the hook does nothing.

**Patterns, first cut:** `terraform` and `tofu` (`apply`, `destroy`, `import`, `state rm|mv|push`, `taint`, `force-unlock`), `kubectl` (`apply`, `create`, `delete`, `patch`, `replace`, `scale`, `drain`, `cordon`, `rollout restart|undo`, `edit`, `label --overwrite`, `annotate --overwrite`, `exec`), `helm` (`install`, `upgrade`, `uninstall`, `rollback`), `argocd` (`app sync|delete|rollback|set`), `flux` (`reconcile`, `suspend`, `resume`, `delete`), `ansible-playbook` without `--check`, `ansible` ad-hoc with a mutating module, `velero` (`restore create` outside a scratch namespace, `delete`), `qm` and `pct` (`destroy`, `stop`, `shutdown`, `rollback`), `pvesh` writes, `virsh` (`destroy`, `undefine`), cloud CLIs with `delete`, `destroy`, `terminate`, or `rm` verbs, `systemctl` (`restart`, `stop`, `disable`) over SSH, `ssh <host> reboot`.

**Limits, stated plainly.** Shell parsing is best-effort. Aliases, scripts, and `bash -c` strings can hide a verb. The hook is a seatbelt, not a lock. The real lock is credentials: the setup skill documents how to give agents a read-only kubeconfig context, a read-only cloud token, and a plan-only Terraform role, and the `doctor` command reports whether the active credentials can write.

**Coexistence.** Some users already run their own guard. The setup skill detects existing pre-tool-use hooks on Bash and offers to skip installation. The guard is opt-in.

**Harness support.**

- Claude Code: `hooks/hooks.json` in the plugin, PreToolUse on Bash.
- Codex: plugin hooks (`PreToolUse`, `PermissionRequest`), which need the user's trust review before they run.
- OpenCode: a small TypeScript plugin using `tool.execute.before`.

Exact hook output schemas are verified in Phase 2 before shipping.

## 9. Packaging for Claude Code, Codex, and OpenCode

**What is portable.** Skill folders (`SKILL.md` with `name` and `description`, plus `references/`, `scripts/`, `assets/`) are read by all three harnesses. Playbooks are plain markdown inside the router skill, so they are portable too.

**What is not.** Subagent definitions (Markdown on Claude Code and OpenCode with different frontmatter, TOML on Codex), hooks (different events and trust models), model routing, and plugin dependencies (Claude Code only).

**Claude Code** (primary).

- `.claude-plugin/plugin.json` with `"dependencies": [{"name": "pstack", "marketplace": "cursor-plugins"}]`.
- `.claude-plugin/marketplace.json` makes this repo its own single-plugin marketplace and must list `"allowCrossMarketplaceDependenciesOn": ["cursor-plugins"]`. Without the allowlist, a dependency declared in `plugin.json` lets the install finish and then the plugin fails to load. Declaring the dependency in the marketplace entry as well makes the failure loud at install time instead.
- Install:
  ```
  /plugin marketplace add cursor/plugins
  /plugin marketplace add iuliandita/idstack
  /plugin install idstack@idstack
  ```
- Skills are namespaced: `/idstack:id-mode`. Persistent state goes in `${CLAUDE_PLUGIN_DATA}`, never in the plugin root, which changes on every update.
- Auto-update is off by default for third-party marketplaces. Users get updates only when `version` changes, so every release bumps it.

**Codex.**

- A root `plugin.json` is Codex's portable manifest; OpenAI-specific settings go in its `extensions.com.openai` object. Codex also reads `.claude-plugin/marketplace.json` as a legacy-compatible marketplace, and `.agents/plugins/marketplace.json` natively. idstack ships both marketplace files.
- Codex plugins carry skills and hooks, not agents. `idstack install --harness codex` copies the generated agent TOML files into `~/.codex/agents/`.
- Codex has no plugin dependencies. pstack must be installed separately (see open decision 1). `id-mode`'s requirements check catches a missing pstack.
- Slash-only skills: generate `agents/openai.yaml` with `policy.allow_implicit_invocation: false` per skill.

**OpenCode.**

- Reads skills from `~/.agents/skills/` and `~/.claude/skills/` among others. No plugin marketplace for skills.
- `idstack install --harness opencode` links `skills/*` into `~/.agents/skills/`, writes agents to `~/.config/opencode/agents/`, and optionally installs the guard plugin to `~/.config/opencode/plugins/`.
- OpenCode reads only `name`, `description`, `license`, `compatibility`, and `metadata` from SKILL.md and ignores the rest.

**Generation.** Root files are the Claude Code plugin. A build step generates the Codex and OpenCode artifacts (agent TOML and Markdown, `openai.yaml` per skill, guard plugin) from neutral sources. CI fails when generated files are stale, the same rule pstack uses.

## 10. Repository layout

```
idstack/
  plugin.json                          portable manifest (Codex reads this)
  .claude-plugin/
    plugin.json                        Claude Code manifest with pstack dependency
    marketplace.json                   single-plugin marketplace, cross-marketplace allowlist
  .agents/plugins/marketplace.json     Codex native marketplace
  skills/
    id-mode/
      SKILL.md                         router
      playbooks/*.md                   idstack playbooks and overlays
      references/
        requirements.md                pstack and domain-skill checks
        gates.md                       action classes, gate block format, grants
        evidence.md                    evidence log, reply sections, labels
        skill-map.md                   domain skills, use, fallback
        targets.md                     how to pin each kind of target
    setup/                             /idstack:setup: models, guard, read-only creds guide
    principle-plan-before-apply/
    principle-pin-the-target/
    principle-prove-the-restore/
    principle-reversible-first/
  agents/                              Claude Code agent files (generated from src/agents)
  hooks/hooks.json                     guard hook (Claude Code)
  bin/idstack                          CLI
  src/
    agents/*.md                        neutral agent sources
    guard/patterns.toml                one pattern list for every harness
  harness/
    codex/agents/*.toml                generated
    codex/skills/*/agents/openai.yaml  generated
    opencode/agents/*.md               generated
    opencode/plugins/idstack-guard.ts  generated
  fixtures/                            toy infra repo for tests and evals
  tests/
  docs/
    plan.md
    playbooks.md
    guide/
  README.md
  LICENSE
```

## 11. The `idstack` CLI

A single-file Python 3 CLI with only the standard library, shipped in `bin/`. Every command supports `--json` for agents.

| Command | Does |
| --- | --- |
| `idstack doctor` | Checks pstack is installed for each detected harness, lists missing domain skills, checks infra CLIs on PATH (`terraform`/`tofu`, `kubectl`, `helm`, `argocd`, `kubeconform`, `conftest`, `trivy`, `ansible-lint`, ...), reports whether the active kube context and cloud credentials can write, and whether the guard is installed. Exit code is non-zero on a hard requirement failure. |
| `idstack check` | Lints the plugin: frontmatter, ASCII, links, playbook structure (owner line, numbered steps, Gates, Evidence, Reply), every state-mutating command in a playbook appears only inside a gate step, generated files are fresh. Used in CI. |
| `idstack build` | Regenerates the harness artifacts. `--check` fails if anything changes. |
| `idstack install --harness codex\|opencode` | Installs the non-plugin pieces for that harness. Idempotent. `--dry-run` prints the plan. |
| `idstack plan-summary <plan.json>` | Deterministic Terraform plan summary: counts by action, destroys and replaces, addresses outside a given scope, and a pass or fail against a predicate grant. The agent uses this instead of reading raw plan JSON. |

`plan-summary` is the first lever (pstack's `build-the-lever`): predicate grants depend on a mechanical check, not the model's reading of a large JSON file.

## 12. Testing and evals

**Static, every PR.** `idstack check`, `idstack build --check`, `claude plugin validate` (verify the exact command name in Phase 1), actionlint, zizmor, gitleaks, and the Python unit tests for the CLI.

**Fixture repo.** `fixtures/` holds a small infra repo that runs with no cloud and no cluster:

- OpenTofu with the `null`, `random`, and `local` providers, including a resource that a change will replace.
- Kustomize and Helm manifests validated offline with `kubeconform`.
- An Ansible playbook against `localhost` in check mode.
- A fake ArgoCD app state file for revision-comparison tests.

**Behavioral evals, nightly or on demand.** Scenario prompts run headless against the fixture with the guard in log-only mode. Each scenario asserts on the transcript and the guard log:

- No state-mutating command ran without a gate in the transcript.
- A plan artifact was produced before any apply.
- A predicate grant was checked with `plan-summary`, and a plan with a replace stopped at a gate.
- The reply has the required sections and labels claims as verified or inferred.
- The pinned target appears before the first live command.

Eval runs cost tokens, so they do not run per PR. pstack's `eval` playbook is the method for testing prompt changes.

**Dogfood.** Each playbook is run on at least one real task before it leaves draft: homelab first, then work-style repos with plan-only access.

## 13. Release and versioning

- Default branch `develop`, release branch `main`. Every change lands by PR, squash merge.
- `v0.x.y` while pre-1.0, cut from `develop`. `v1.0.0` when the exit criteria in Phase 6 hold, cut from `main`.
- Channels: `/plugin marketplace add iuliandita/idstack` tracks the default branch (nightly). Stable users pin `iuliandita/idstack#main` or a tag.
- Every release bumps `version` in all manifests (CI checks they match) and creates a tag `idstack--v<version>` so a dependent plugin could constrain it.
- `CHANGELOG.md` from Phase 1.
- Track pstack. A scheduled CI job installs the latest pstack and runs the requirements check and static evals, so a pstack rename (a playbook file, a principle, `setup-pstack`) shows up as a failing job, not a user report.

## 14. Roadmap

Each phase ends with a verifiable exit check.

**Phase 0: bootstrap.**
Repo, license, this plan, CI skeleton (actionlint, zizmor, gitleaks, ASCII check), issue templates.
Exit: CI green on an empty plugin. Plan approved.

**Phase 1: foundation.**
`id-mode` router and references (`requirements`, `gates`, `evidence`, `skill-map`, `targets`), four principles, `id-agent`, `plan-reader`, Claude Code manifests with the pstack dependency, `idstack check`, `idstack doctor`, `idstack plan-summary`, `opening-a-pr` and `closeout` overlays, fixture repo skeleton.
Exit: `/plugin install idstack@idstack` pulls pstack and loads cleanly in a fresh Claude Code profile. `doctor` passes. `id-mode` routes an `investigation` request to pstack's playbook unchanged.

**Phase 2: change path, wave 1.**
`iac-change`, `gitops-change`, `dependency-bump`, `queue-burndown`, `live-diagnosis`, `change-verifier`, guard hook for Claude Code (log-only default), predicate grants.
Exit: each playbook dogfooded on one real task. Fixture evals pass for the gate and grant scenarios.

**Phase 3: change path, wave 2.**
`upgrade`, `edge-change`, `host-config-change`, `incident`, `decommission`, `secret-rotation`, `env-promotion`, overlays `bug-fix`, `babysit`, `shipping`, `autonomous-run`, `pause-safely`.
Exit: dogfooded. `incident` used for at least one real event or a game-day.

**Phase 4: assurance.**
`restore-drill`, `drift-audit`, `observability-audit`, `security-posture`, `vuln-response`, `capacity-cost`, `readiness-review`, `agent-hosting`. Baseline files for posture diffs.
Exit: one full assurance pass on the homelab with findings filed as issues.

**Phase 5: harnesses.**
`idstack build` generators, Codex packaging (marketplace, agent TOML, `openai.yaml`), OpenCode install and guard plugin, `/idstack:setup` with model detection, nightly evals, pstack-tracking job.
Exit: install and a scripted smoke scenario pass on all three harnesses.

**Phase 6: v1.0.**
Guide (`docs/guide/`), every playbook out of draft, no open P1 issues, two weeks of daily use without a gate bypass.

## 15. Risks

| Risk | Mitigation |
| --- | --- |
| pstack renames or restructures a file idstack reads | Pin to tested pstack behavior in docs, scheduled tracking job, requirements check fails loudly |
| Token cost. pstack's router is large and idstack adds more | Keep `id-mode` short. Load references only when a step needs them. Bulk evidence goes to cheap-tier subagents. Measure tokens per scenario in evals. |
| Guard gives false confidence | Documented as a seatbelt. `doctor` reports credential write access. Setup pushes read-only credentials. |
| Grants creep into blanket permission | Grants are predicates checked by `plan-summary`, logged, scoped to one task, and never cover destroy, state surgery, data deletion, or root credentials |
| Domain skills drift from what playbooks expect | `skill-map.md` names the sections relied on. Missing or changed skill is reported as skipped, not passed. |
| Private details leak into public files | Pre-push hygiene check in `opening-a-pr` overlay. gitleaks in CI. Playbooks use placeholders only. |
| Codex or OpenCode formats change | Generated artifacts, one place to update, smoke scenario per harness |
| Cursor-specific wording in pstack confuses other harnesses | Rely on pstack's adapter on Claude Code. For Codex and OpenCode, depends on the pstack distribution chosen (open decision 1). |

## 16. Open decisions

1. **pstack on Codex and OpenCode.** Upstream ships Claude Code and Cursor only. Options: (a) require a community mirror such as `backnotprop/pstack`, pinned to a commit, (b) require `michael-denyer/pstack-claude`, which already handles Codex hooks, (c) run without pstack on those harnesses, with a reduced built-in principle set. Recommendation: (a) for now, pinned, with `doctor` checking the pin. It is the most complete and tracks upstream, but it is a third-party dependency.
2. **Guard default.** Opt-in (recommended) or on by default in log-only mode.
3. **Auto-routing.** Slash-only `id-mode` (recommended, matches pstack) or an optional session-start hint that suggests `id-mode` for infra tasks.
4. **Router name.** `id-mode` (recommended) or something else.
5. **Agent apply policy default.** Recommended: the agent may run a gated command after explicit approval in the current turn, or under a predicate grant. Repo instructions can forbid it entirely.

## 17. Sources

- pstack: https://github.com/cursor/plugins/tree/main/pstack (playbooks, `dyl-stack`, generator, adapter docs read from the repo at version 0.15.35)
- Claude Code plugin dependencies: https://code.claude.com/docs/en/plugins/dependencies.md
- Claude Code plugins reference: https://code.claude.com/docs/en/plugins-reference
- Claude Code marketplaces: https://code.claude.com/docs/en/plugin-marketplaces
- Codex plugins: https://developers.openai.com/plugins/build/plugins
- Codex skills: https://learn.chatgpt.com/docs/build-skills
- Codex subagents: https://learn.chatgpt.com/docs/agent-configuration/subagents
- Codex hooks: https://learn.chatgpt.com/docs/hooks
- OpenCode skills, agents, plugins: https://opencode.ai/docs/skills/, https://opencode.ai/docs/agents/, https://opencode.ai/docs/plugins/
- Agent Skills spec: https://agentskills.io/specification
- HashiCorp agent skills: https://github.com/hashicorp/agent-skills
- antonbabenko/terraform-skill: https://github.com/antonbabenko/terraform-skill
- pstack ports: https://github.com/backnotprop/pstack, https://github.com/michael-denyer/pstack-claude
- Agent infra incident (Feb 2026): https://incidentdatabase.ai/cite/1424
- AOI, read-write separated SRE agents: https://arxiv.org/abs/2603.03378
- Google SRE workbook, alerting on SLOs: https://sre.google/workbook/alerting-on-slos/
- Google SRE book, postmortem culture: https://sre.google/sre-book/postmortem-culture/
- k3s automated upgrades: https://docs.k3s.io/upgrades/automated
- k3s etcd snapshots: https://docs.k3s.io/cli/etcd-snapshot
- k3s hardening guide: https://docs.k3s.io/security/hardening-guide
- ArgoCD sync waves: https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
- ArgoCD progressive syncs: https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Progressive-Syncs/
- Terraform `removed` block: https://developer.hashicorp.com/terraform/language/block/removed
- Velero restore reference: https://velero.io/docs/main/restore-reference/
- Kubernetes PSA labels: https://kubernetes.io/docs/tasks/configure-pod-container/enforce-standards-namespace-labels/
- Kubernetes ValidatingAdmissionPolicy: https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/
- GitHub Actions secure use: https://docs.github.com/en/actions/reference/security/secure-use
- GitHub artifact attestations: https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations
- CISA KEV: https://www.cisa.gov/known-exploited-vulnerabilities-catalog
