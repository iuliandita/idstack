# idstack plan

Status: design record, written 2026-10-27. For what has shipped (1.0.0 at time of writing), see the status line in [section 15](#15-roadmap) and [CHANGELOG.md](../CHANGELOG.md).

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
9. Jev decision layer
10. Packaging for Claude Code, Codex, and OpenCode
11. Repository layout
12. The `idstack` CLI
13. Testing and evals
14. Release and versioning
15. Roadmap
16. Risks
17. Decisions
18. Sources

## 1. Goal and non-goals

**Goal.** Give a coding agent a disciplined, verifiable way to do infrastructure work: IaC changes, GitOps, host config, network and edge changes, upgrades, incidents, backups, drift, monitoring, security posture, capacity, and cost. The agent should leave behind evidence a reviewer can rerun, and it should never mutate shared state without a gate the human can see.

**Shape.** A thin router over pstack's `poteto-mode`, plus infra playbooks, overlays on a few pstack playbooks, four new principles, three subagents, an optional guard hook, and a small CLI. Domain knowledge (how Terraform, Kubernetes, Ansible, and Prometheus work) stays in separate domain skills; idstack holds the process.

**Audience.** First, a single operator running a small cluster and a managed-cloud estate. Second, anyone running similar stacks. Playbooks are generic: no hostnames, IPs, or org topology.

**Non-goals.**

- Not a replacement for pstack. idstack does not restate pstack's principles, reply style, or subagent rules.
- Not a domain reference. No Terraform tutorial, no Kubernetes cookbook.
- Not an autonomous operator. idstack makes the agent faster and more careful. It does not remove the human from state-mutating decisions unless the human grants that for a specific, checkable condition.
- Not offensive security. Security playbooks are posture checks, hardening, and response.
- Not tied to one vendor. Cloud-specific steps are written as "the provider's equivalent" with examples.

## 2. What exists today

**pstack** (MIT, `cursor/plugins`, version 0.15.36 at time of writing) ships a router skill (`poteto-mode`), 23 playbooks, 24 principle skills, workflow skills (`how`, `why`, `architect`, `arena`, `swarm`, `interrogate`, `show-me-your-work`, `figure-it-out`), and two subagents. Its playbooks assume app development: reproduce through a UI or CLI control skill, delegate code to a fast model, and land PRs through `gh`. Its autonomy rules say reversible work proceeds without asking and only deploys, force-pushes, and deletions pause.

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

**Overlays.** A file in `id-mode/playbooks/` with the same name as a pstack playbook is an overlay. It opens with "Read the shared playbook first: pstack `poteto-mode/playbooks/<name>.md`. Then apply these gates. They win on conflict." Overlays: `bug-fix`, `babysit`, `shipping`, `opening-a-pr`, `autonomous-run`, `pause-safely`.

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

**Git operations can be writes.** Actions are classed by their downstream effect. A push, PR, merge, or workflow dispatch that triggers automation able to deploy or change infrastructure (CI applies Ansible on push, preview environments on PR, ArgoCD auto-sync on merge) is state-mutating, because that automation runs with its own credentials and the agent's read-only credentials do not stop it. Every change playbook's first step finds out which git events deploy in the target repo and records it.

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

**Pin the target.** Before the first command against a live system, the agent records which cluster, account, workspace, or host it is pointed at, and checks it matches the task. Every subsequent command passes the target explicitly (`--context`, `-chdir`, `--limit`). Targets from separate estates never mix in one session.

**Live state over proxies.** A green CI job, an ArgoCD "Synced/Healthy", or a merged PR is not proof that the change landed. Verification compares the live state to the intended state: synced revision against git HEAD, running image digest against the built one, a re-plan that shows no changes, a query that returns the new value.

## 5. Principles

idstack adds four principle skills. Each is short, shaped like pstack's (claim, Why, The idea, The test).

1. **principle-plan-before-apply.** The only input to a state-mutating command is a reviewed artifact produced by a read-only step: a saved plan file, a rendered diff, check-mode output. A stale artifact is re-produced, never reused. Apply exactly what was reviewed.
2. **principle-pin-the-target.** Name the target before touching it, pass it explicitly on every command, and check it matches the task. An implicit default context is a bug.
3. **principle-prove-the-restore.** A backup that has not been restored is a hypothesis. Backups must be independent of the thing they protect: different credentials, different lifecycle, not managed by the same IaC that could destroy the source.
4. **principle-reversible-first.** Prefer the step that can be undone: park before teardown, power off before delete, warn and audit before enforce, canary before fleet, one rule at a time.

Mapped, not duplicated. idstack names these existing pstack principles in its playbooks: `make-operations-idempotent`, `prove-it-works`, `fix-root-causes`, `sequence-verifiable-units`, `separate-before-serializing-shared-state`, `encode-lessons-in-structure`, `build-the-lever`, `guard-the-context-window`, `attack-the-premise`, `explain-the-number`.

## 6. Playbook set

The full spec for each playbook is in [playbooks.md](playbooks.md). This is the catalog with the evidence behind each choice. "Usage" means the playbook is backed by recurring work in the maintainer's own agent history, summarized generically.

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

**Model roles.** idstack uses pstack's model rule file (`~/.claude/rules/pstack-models.md` on Claude Code, `~/.agents/pstack-models.md` on Codex and OpenCode), which `install.sh` writes from `config/pstack-models.json` merged with the user's `~/.config/idstack/models.json`. Playbooks name pstack roles (for example `why investigators`, `hardest tasks`). Not shipped: a separate `idstack-models.md` with three roles of its own, `evidence` (bulk read-only collection), `plan reading`, and `verification`, falling back to tiers:

- `evidence`: the cheapest capable tier.
- `plan reading`: balanced tier. Escalate to the strongest tier when the plan contains destroys, replaces, IAM, or network policy changes.
- `verification`: balanced tier, from a different model family than the author when one is available.

Not shipped either: tier-only defaults. `config/pstack-models.json` names real models, and `/idstack:setup` offers `install.sh` to write the rule files rather than detecting models itself.

**Roles can point at another harness.** Operators with several subscriptions route cheap bulk work to one provider and verification to another family. A role line may therefore name a model the current harness cannot run natively (for example, a Codex model while running in Claude Code). Dispatch order for a role:

1. Native subagent, when the current harness serves the model.
2. The host's delegation tool, when one is available (for example, an orchestrator's delegate-task call).
3. The other harness's headless CLI (`codex exec`, `claude -p`, `opencode run`), with the model flag. The exact commands are in `config/pstack-models.json`.
4. Fall back to the next option in the role's chain, and to the session model when none is reachable, and say so in the reply.

Each role is one chain with an option per provider (`<model> <effort> via <provider>`, joined by `else`, with `or` groups that prefer the current harness), so it resolves on any combination of installed harnesses. `scripts/pstack_models.py --resolve <harness>` prints what each role runs on a given machine.

A cross-harness worker gets a self-contained brief (scope, target, read-only commands allowed, expected output), because each dispatch costs a context handoff. It needs the same pinned target, read-only credentials, and guard as the parent. Without those, it falls back to step 4.

**Data boundaries (not shipped).** Some content must not reach some providers: work estates often forbid sending repo content, logs, or plan output to third-party or foreign-hosted models. The design is a rule file that lists path prefixes or repo markers with providers they exclude. Before dispatching a role, idstack would check the boundary and fall back to an allowed provider at the same tier. A boundary check that cannot decide counts as excluded. Live evidence (logs, plans, describe output) carries hostnames and sometimes secrets, so the boundary applies to evidence collection first.

## 8. Guardrails in the execution layer

Prose rules are not enough. idstack ships an optional guard hook.

**What it does.** A pre-tool-use hook inspects shell commands. If a command matches a state-mutating pattern (section 4) for a known infra CLI, the hook returns "ask" with a one-line reason, so the harness shows its own permission prompt. Without a match, the hook does nothing.

**Patterns.** One list for every harness lives in [src/guard/patterns.toml](../src/guard/patterns.toml): Terraform and OpenTofu, kubectl, Helm, ArgoCD, Flux, Ansible, Velero, Proxmox, libvirt, cloud CLIs, and remote `systemctl` and reboot. `idstack guard test <command>` shows what a command matches.

**Limits, stated plainly.** Shell parsing is best-effort. Aliases, scripts, and `bash -c` strings can hide a verb. The hook is a seatbelt, not a lock. The real lock is credentials: give agents a read-only kubeconfig context, a read-only cloud token, and a plan-only Terraform role. `idstack doctor --live` reports whether the current kube context can write; checking cloud credentials, and setup guidance for read-only credentials, are not shipped.

**Coexistence.** Some users already run their own guard. The guard is opt-in and off by default, so it never stacks on another guard unless the operator turns it on. Detecting existing pre-tool-use hooks is not shipped.

**Harness support.**

- Claude Code: `hooks/hooks.json` in the plugin, PreToolUse on Bash.
- Codex: `idstack guard install --harness codex` adds a `PreToolUse` entry on Bash to `$CODEX_HOME/hooks.json`, which needs the user's trust review (`/hooks`) before it runs. Codex cannot ask, so `ask` mode blocks, and `idstack guard allow-once` approves one exact command.
- OpenCode: a plugin package in `harness/opencode/guard` that hooks `execute.before` on shell calls and forwards each one to `idstack guard hook --harness opencode`; `idstack guard install --harness opencode` adds it to the `plugins` list in `opencode.json`.

## 9. Jev decision layer

Many idstack steps need a small common-sense judgment over text: does this release note describe a breaking change, does this resource hold data, is this sentence supported by the evidence. Asking a reasoning model each time is slow and costly, and its answer comes back as prose. TypeSafe's Jev is a decision model built for this: code sends a `state` and typed questions, and Jev returns a calibrated probability per answer in about 100 ms, at $0.042 per million input tokens with output free. idstack uses it as an optional layer under the CLI. Code keeps the control flow and the decision; Jev supplies judgments.

**Jev can make a gate stricter, never looser.** Its answers can force a stop, add a finding, or rank and narrow what gets read. They never approve a write, clear a finding, or establish that something is safe or unused. Every decision point has a defined outcome for "unsettled": a probability on or between the thresholds, a failed call, a missing answer, or missing evidence. Code checks for unsettled before it reads any probability. Thresholds start at 0.3 and 0.7 on the answer's probability, never on its `confidence`.

| Decision point | Playbook | Questions (one per item) | Code rule | Unsettled |
| --- | --- | --- | --- | --- |
| Plan reading | `iac-change` | Per changed resource: holds persistent data? widens IAM permissions? Network exposure is checked in code. | Any > 0.3 fails the predicate grant and escalates plan reading. Low answers change nothing; the grant still needs every deterministic condition. | Grant fails; human gate |
| Dependency bumps | `dependency-bump` | Per release-note bullet: breaking change? needs an operator step? removes a setting? renames a setting? Code checks whether a named setting is one the repo sets. | Auto-merge eligibility comes only from a deterministic policy. Any > 0.3 removes it. | Eligibility removed; gate |
| Outgoing messages | `incident` | Per claim: supported by the evidence? | Any claim < 0.7 is flagged for rewording before the operator sends. | Flagged |
| Log filtering | `live-diagnosis` | Per chunk: related to the symptom? | Keep chunks > 0.3 for the reasoning model. Keep the full logs and widen when the kept chunks do not explain the symptom. | Chunk kept |
| Suspect changes | `live-diagnosis` | Per recent change: could it plausibly cause this alert? | Rank and examine read-only from the top. Rollbacks go through a gate. | Ranked first |
| Decommission evidence | `decommission` | Per evidence item: shows the target is still in use? | Any > 0.3 means park, not tear down. Low answers do not prove disuse. | Park |
| Ambiguous commands | guard hook | Only for commands that name an infra tool or run a script the regex cannot classify: changes remote state? deletes data? targets production? | Baseline allow. Any > 0.3 escalates to ask. Never allows a command the regex flagged. | Ask |
| Public hygiene | `opening-a-pr` overlay | Per regex candidate: a private hostname or IP rather than a public example? | Every candidate blocks until an allowlist or the operator clears it. Jev orders the list and can add candidates. | Top of list |

**Implementation.**

- All question wording, criteria, thresholds, and the pinned model ID live in one place: `src/questions/<battery>.json`, one file per decision point. Pin `jev-1.14.0`, not `jev-latest`, because thresholds are tuned against a version.
- `idstack judge <battery> <input.json>` builds the request, calls `POST /v1/systemone` with the standard library, applies the code rule, and prints the outcome per item with `--json`. Playbooks call this command, never the API directly.
- The key comes from `TYPESAFE_API_KEY`. Without a key, `judge` exits with a distinct status, the playbook falls back to deterministic checks plus the reasoning model, and the reply says Jev was not used.
- `--trace` writes the exact request and response to the evidence log so any answer can be rerun.
- The data-boundary rules (section 7, not shipped) would apply to TypeSafe like any other provider. TypeSafe does not train on requests; zero data retention is an enterprise option.
- Jev is weak at arithmetic, counting, dates, version comparison, multi-step reasoning, and text written to steer it. Those stay in code or with a reasoning model, and attacker-writable text (logs, issue bodies, release notes) only ever tightens a gate.

**Probe, 2026-10-28.** A synthetic probe ran the plan-reading and dependency-bump batteries against `jev-1.14.0`: 24 requests, 70 answers, 13,196 input tokens, about $0.0006. 66 answers matched the expected label, 3 did not, 1 was unsettled. All four misses leaned toward risk (false positives), so under the tighten-only rule they would add a gate, never skip one. Two misses were arguably label errors (a replaced `random_password` does change a live credential; "removed X, use Y instead" does ask the operator to change something). One was a real confusion: a `0.0.0.0/0` SSH rule read as widening IAM, which supports keeping network checks in code and naming the network-versus-permissions case in the criteria. A release note with an embedded instruction to "automated reviewers" was still flagged as breaking (0.78), which is closer to the threshold than comfortable. The probe set is small and synthetic; it shows the shape works, not that the thresholds are right.

**Evals.** Each battery gets a labeled fixture set in `fixtures/jev/<battery>/`, including hard cases, "nothing applies" cases, and adversarial text. CI validates the question files and fixtures offline. Live calibration runs on demand and before any model version change, and threshold changes are checked on cases not used for tuning.

## 10. Packaging for Claude Code, Codex, and OpenCode

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
- Codex plugins carry skills and hooks, not agents. `install.sh` links the generated agent TOML files into `$CODEX_HOME/agents/` (default `~/.codex/agents/`).
- Codex has no plugin dependencies. pstack must be installed separately (see decision 1 in section 17). `id-mode`'s requirements check catches a missing pstack.
- Slash-only skills: generate `agents/openai.yaml` with `policy.allow_implicit_invocation: false` per skill.

**OpenCode.**

- Reads skills from `~/.agents/skills/` and `~/.claude/skills/` among others. No plugin marketplace for skills.
- `install.sh` links `skills/*` into `~/.config/opencode/skills/` and the generated agents into `~/.config/opencode/agents/`. `idstack guard install --harness opencode` registers the guard plugin.
- OpenCode reads only `name`, `description`, `license`, `compatibility`, and `metadata` from SKILL.md and ignores the rest.

**Generation.** Root files are the Claude Code plugin. `idstack build` generates the Codex and OpenCode artifacts (agent TOML and Markdown, `openai.yaml` per skill) from `agents/*.md` and the skills. CI fails when generated files are stale, the same rule pstack uses.

## 11. Repository layout

```
idstack/
  plugin.json                          portable manifest (Codex reads this)
  .claude-plugin/
    plugin.json                        Claude Code manifest with pstack dependency
    marketplace.json                   single-plugin marketplace, cross-marketplace allowlist
  .agents/plugins/marketplace.json     Codex native marketplace
  install.sh                           installer for all three harnesses
  skills/
    id-mode/
      SKILL.md                         router
      playbooks/*.md                   idstack playbooks and overlays
      references/                      requirements, gates, evidence, skill-map, targets
      agents/openai.yaml               generated: Codex skill policy
    setup/                             /idstack:setup: doctor, models, guard, Jev
    principle-*/                       four principles, each with a generated agents/openai.yaml
  agents/*.md                          subagent sources (Claude Code reads them directly)
  hooks/hooks.json                     guard hook (Claude Code)
  bin/idstack                          CLI
  config/pstack-models.json            pstack model per role, written by install.sh
  scripts/                             check.py, eval.py, pstack_models.py
  src/
    guard/patterns.toml                one pattern list for every harness
    questions/<battery>.json           Jev question wording, criteria, thresholds, model pin
  harness/                             generated by `idstack build`
    codex/agents/*.toml
    opencode/agents/*.md
  fixtures/
    infra/                             toy estate for behavioral evals
    evals/scenarios.json               eval scenarios
    plans/                             plan JSON for plan-summary tests
    jev/<battery>/                     labeled cases per Jev decision point
  tests/                               CLI unit tests
  docs/                                plan, playbook specs, Jev calibration
  README.md, INSTALL.md, CONTRIBUTING.md, SECURITY.md, CHANGELOG.md, LICENSE
```

## 12. The `idstack` CLI

A single-file Python 3 CLI with only the standard library, shipped in `bin/`. Every command supports `--json` for agents.

| Command | Does |
| --- | --- |
| `idstack doctor` | Checks which harnesses are on PATH, that pstack and idstack are installed for each, the Codex and OpenCode agents and skills, missing domain skills, infra CLIs on PATH, the pstack model files, whether `TYPESAFE_API_KEY` is set, and the guard mode. With `--live`, it runs `kubectl auth can-i` against the current kube context to report whether it can write. Exit code is non-zero on a hard requirement failure. |
| `idstack check` | Runs `scripts/check.py`: ASCII, JSON, manifest agreement, the mirror pin, the changelog, and relative links. Used in CI. |
| `idstack build` | Regenerates the harness artifacts. `--check` fails if anything changes. |
| `idstack plan-summary <plan.json>` | Deterministic Terraform plan summary: counts by action, destroys and replaces, addresses outside a given scope, and a pass or fail against a predicate grant. The agent uses this instead of reading raw plan JSON. |
| `idstack judge <battery> <input.json>` | Runs one Jev decision point (section 9): builds the request from `src/questions/<battery>.json`, applies the code rule, and prints the outcome per item, including unsettled. Exits 4 when `TYPESAFE_API_KEY` is not set and 3 when a call failed. `--trace` writes the exact request and response to the evidence log. |
| `idstack guard` | The opt-in guard (section 8): `enable`, `disable`, `status`, `test`, `allow-once`, and `install` or `uninstall` for the Codex hook. |

`plan-summary` is the first lever (pstack's `build-the-lever`): predicate grants depend on a mechanical check, not the model's reading of a large JSON file.

## 13. Testing and evals

**Static, every PR.** `idstack check`, `idstack build --check`, `claude plugin validate .`, shellcheck, actionlint, zizmor, gitleaks, the Python unit tests for the CLI, and an isolated install smoke test.

**Fixture repo.** `fixtures/infra/` holds a small estate that runs with no cloud and no cluster:

- Terraform using only the built-in `terraform_data` resource, so a plan or apply touches a local state file and nothing else.
- A Kustomize app under `k8s/`, rendered and checked, never applied.
- An Ansible playbook and inventory, checked, never applied.

**Behavioral evals, on demand.** `scripts/eval.py` runs the scenarios in `fixtures/evals/scenarios.json` headless against a temporary copy of the fixture, with the guard in `ask` mode and an empty `KUBECONFIG`. Each scenario asserts on the commands run and the final reply. The checks the design calls for:

- No state-mutating command ran without a gate in the transcript.
- A plan artifact was produced before any apply.
- A predicate grant was checked with `plan-summary`, and a plan with a replace stopped at a gate.
- The reply has the required sections and labels claims as verified or inferred.
- The pinned target appears before the first live command.

Eval runs cost tokens, so they do not run per PR. pstack's `eval` playbook is the method for testing prompt changes.

**Dogfood.** Each playbook is run on at least one real task before it leaves draft: a small cluster first, then repos with plan-only access.

## 14. Release and versioning

- Default branch `develop`, release branch `main`. Every change lands by PR, squash merge.
- `v0.x.y` while pre-1.0, cut from `develop`. `v1.0.0` and later are cut from `main`. v1.0.0 was cut on the operator's call before the Phase 6 exit criteria were met; those stay open in the roadmap.
- A release merges `develop` into `main` with a merge commit (never a squash, so the branches share history), then tags `main`.
- Channels: `main` is stable and is what `install.sh` and the documented install commands use. `develop`, the default branch, is the nightly; `install.sh --ref develop` or `iuliandita/idstack#develop` follows it.
- Every release bumps `version` in all manifests (CI checks they match) and creates a tag `v<version>`, which triggers the release workflow.
- `CHANGELOG.md` from Phase 1.
- Track pstack. A scheduled CI job installs the latest pstack and runs the requirements check and static evals, so a pstack rename (a playbook file, a principle, `setup-pstack`) shows up as a failing job, not a user report.

## 15. Roadmap

Each phase ends with a verifiable exit check.

Status at v1.0.0: the artifacts of phases 1 through 5 ship (router, playbooks, principles, subagents, CLI, batteries with calibration in [jev-calibration.md](jev-calibration.md), guard for Claude Code, Codex, and OpenCode, build generators, setup skill, Codex and OpenCode files). Not shipped from phase 5: model detection in `/idstack:setup`, the `idstack-models.md` roles, and data boundaries. The dogfooding exits (real tasks, a real incident or game-day, an assurance pass on a small cluster), the nightly evals, and the pstack-tracking job are still open.

**Phase 0: bootstrap.**
Repo, license, this plan, CI skeleton (actionlint, zizmor, gitleaks, ASCII check), issue templates.
Exit: CI green on an empty plugin. Plan approved.

**Phase 1: foundation.**
`id-mode` router and references (`requirements`, `gates`, `evidence`, `skill-map`, `targets`), four principles, `id-agent`, `plan-reader`, Claude Code manifests with the pstack dependency, `idstack check`, `idstack doctor`, `idstack plan-summary`, `opening-a-pr` and `closeout` overlays, fixture repo skeleton.
Exit: `/plugin install idstack@idstack` pulls pstack and loads cleanly in a fresh Claude Code profile. `doctor` passes. `id-mode` routes an `investigation` request to pstack's playbook unchanged.

**Phase 2: change path, wave 1.**
`iac-change`, `gitops-change`, `dependency-bump`, `queue-burndown`, `live-diagnosis`, `change-verifier`, guard hook for Claude Code (log-only default), predicate grants. `idstack judge` with the plan-reading, dependency-bump, log-filtering, and suspect-change batteries and their labeled fixtures.
Exit: each playbook dogfooded on one real task. Fixture evals pass for the gate and grant scenarios. Each Jev battery has at least 30 labeled cases and no false negatives on its held-out set.

**Phase 3: change path, wave 2.**
`upgrade`, `edge-change`, `host-config-change`, `incident`, `decommission`, `secret-rotation`, `env-promotion`, overlays `bug-fix`, `babysit`, `shipping`, `autonomous-run`, `pause-safely`. Jev batteries for outgoing-message claims, decommission evidence, and public hygiene.
Exit: dogfooded. `incident` used for at least one real event or a game-day.

**Phase 4: assurance.**
`restore-drill`, `drift-audit`, `observability-audit`, `security-posture`, `vuln-response`, `capacity-cost`, `readiness-review`, `agent-hosting`. Baseline files for posture diffs.
Exit: one full assurance pass on a small cluster with findings filed as issues.

**Phase 5: harnesses.**
`idstack build` generators, Codex packaging (marketplace, agent TOML, `openai.yaml`), OpenCode install and guard plugin, `/idstack:setup` with model detection, cross-harness role dispatch and data boundaries, Jev battery for ambiguous guard commands, nightly evals, pstack-tracking job.
Exit: install and a scripted smoke scenario pass on all three harnesses.

**Phase 6: v1.0.**
A user guide, every playbook out of draft, no open P1 issues, two weeks of daily use without a gate bypass.
Status: v1.0.0 was cut on the operator's call with no open P1 issues. The user guide, a review of each playbook against real use, and the two weeks of daily use are still open and tracked as an issue.

## 16. Risks

| Risk | Mitigation |
| --- | --- |
| pstack renames or restructures a file idstack reads | Pin to tested pstack behavior in docs, scheduled tracking job, requirements check fails loudly |
| Token cost. pstack's router is large and idstack adds more | Keep `id-mode` short. Load references only when a step needs them. Bulk evidence goes to cheap-tier subagents. Measure tokens per scenario in evals. |
| Guard gives false confidence | Documented as a seatbelt. `doctor` reports credential write access. Setup pushes read-only credentials. |
| Grants creep into blanket permission | Grants are predicates checked by `plan-summary`, logged, scoped to one task, and never cover destroy, state surgery, data deletion, or root credentials |
| Domain skills drift from what playbooks expect | `skill-map.md` names the sections relied on. Missing or changed skill is reported as skipped, not passed. |
| Private details leak into public files | Pre-push hygiene check in `opening-a-pr` overlay. gitleaks in CI. Playbooks use placeholders only. |
| Codex or OpenCode formats change | Generated artifacts, one place to update, smoke scenario per harness |
| Cursor-specific wording in pstack confuses other harnesses | Rely on pstack's adapter on Claude Code. For Codex and OpenCode, depends on the pstack distribution chosen (decision 1 in section 17). |
| A Jev answer loosens a gate | Tighten-only rule enforced in `idstack judge` code, not in playbook prose. Every decision point defines its unsettled outcome. Fixture sets include adversarial text. |
| Jev model update shifts answers | Pin the model ID. Rerun every battery's labeled set before moving the pin. |

## 17. Decisions

Decided 2026-10-27.

1. **pstack on Codex and OpenCode:** require the community mirror `backnotprop/pstack`, pinned to a tested commit. `doctor` checks the pin. Revisit if upstream ships Codex or OpenCode packaging. Rejected: `michael-denyer/pstack-claude` (narrower), and running without pstack (forks the methodology).
2. **Guard default:** opt-in. `/idstack:setup` offers it and skips when another pre-tool-use guard is present.
3. **Auto-routing:** slash-only `id-mode`, like pstack. No session-start hint.
4. **Router name:** `id-mode`, agent `id-agent`.
5. **Agent apply policy:** the agent may run a gated command after explicit approval in the current turn, or under a predicate grant. Repo instructions can forbid it entirely, and the strictest rule wins.
6. **Jev:** use it as an optional decision layer under the CLI (section 9), tighten-only. Decided 2026-10-28.

## 18. Sources

- pstack: https://github.com/cursor/plugins/tree/main/pstack (playbooks, `dyl-stack`, generator, adapter docs read from the repo at version 0.15.36)
- TypeSafe models, pricing, limits: https://docs.typesafe.ai/models.md
- TypeSafe build guide: https://docs.typesafe.ai/concepts/how-to-build-with-system-one.md
- Jev 1.13 weak spots: https://docs.typesafe.ai/model-jaggedness/jev-1.13.md
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
