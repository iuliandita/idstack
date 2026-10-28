# idstack

Infra, DevOps, and SRE playbooks for coding agents, layered on
[pstack](https://github.com/cursor/plugins/tree/main/pstack).

pstack gives agents a rigorous way to do software work. idstack adds what infra work needs and app
work does not: plan before apply, pin the target before touching it, prove that backups restore,
and never let a green check stand in for the live state.

Status: pre-alpha. The router, playbooks, principles, subagents, `idstack` CLI, opt-in guard, and
setup skill ship. Dogfooding on real work and the v1.0 exit criteria are next. See the
[roadmap](docs/plan.md#15-roadmap).

## Install

```sh
git clone https://github.com/iuliandita/idstack.git
cd idstack
./install.sh --check    # what is installed, what is missing
./install.sh            # install pstack (if missing) and idstack on every harness found
```

The installer finds Claude Code, Codex, and OpenCode on your PATH, installs pstack wherever it is
missing, then installs idstack. It also writes pstack's per-role model choices from
[config/pstack-models.json](config/pstack-models.json) instead of pstack's `xhigh` defaults.
`--harness claude,codex` limits it, `--dry-run` prints the commands without running them.

Claude Code only, without the clone:

```text
/plugin marketplace add cursor/plugins
/plugin marketplace add iuliandita/idstack
/plugin install idstack@idstack
```

idstack declares pstack as a dependency, so the last line installs both. The `cursor/plugins`
marketplace has to be added first. [INSTALL.md](INSTALL.md) covers Codex, OpenCode, updates,
channels, and removal.

## Usage

Start a new session after installing, then hand the router the task:

```text
/idstack:id-mode bump the ingress-nginx chart and stop before sync     # Claude Code
$idstack:id-mode rotate the leaked CI deploy token                      # Codex
```

Codex namespaces plugin skills, so the bare `$id-mode` loads nothing. Run `/idstack:setup` (Claude
Code) or `$idstack:setup` (Codex) once to check what is installed and to choose a guard mode. Both
skills are explicit-only: when you hand a task to another agent (a T3 delegate, `claude -p`, or
`codex exec`), start the task text with the slash or dollar form above. On OpenCode, ask for the `id-mode` skill. It reads pstack's `poteto-mode`, picks a playbook, copies
its steps into a todo list, and stops at a gate before anything changes live state. Infra tasks go
to idstack's playbooks; everything else goes to pstack's, unchanged.

## What it is

- A router skill, `/idstack:id-mode`, that sits on top of pstack's `poteto-mode` and routes infra
  tasks to idstack playbooks, and everything else to pstack's.
- 21 playbooks for change (IaC, GitOps, host config, edge, upgrades, dependency bumps), diagnosis
  (live triage, incidents), and assurance (restore drills, drift, monitoring, security posture,
  capacity and cost), plus six overlays on pstack playbooks. The catalog is in
  [skills/id-mode/SKILL.md](skills/id-mode/SKILL.md).
- A safety model: reads are free, reversible writes are free, and anything that changes live state
  stops at a gate that shows the exact command, target, blast radius, rollback, and evidence.
- Four principles (plan before apply, pin the target, prove the restore, reversible first) and
  three subagents: `id-agent` for delegates, `plan-reader`, and `change-verifier`.
- Optional Jev decision points for cheap typed judgments. Their answers can only make a gate
  stricter.

- An `idstack` CLI the playbooks call: `plan-summary` (counts, deletes and replaces, stateful, IAM,
  and network changes, and a predicate check for grants), `judge` (one Jev decision point),
  `doctor`, and `guard`.
- An opt-in guard that asks (Claude Code) or blocks (Codex) before state-mutating infra commands.
  OpenCode has none yet. Off by default. It is a seatbelt, not a lock: the gates apply with it off.

Domain knowledge (how Terraform, Kubernetes, or Prometheus work) stays in separate domain skills.
idstack holds the process. The design is in [docs/plan.md](docs/plan.md).

## What's inside

What pstack ships (as of pstack 0.15.36) and what idstack adds. **Bold** rows come from idstack.

### Routers

| Skill | Source | Role |
| --- | --- | --- |
| `poteto-mode` | pstack | Main router: principles, triggers, reply style, subagent rules, playbook catalog |
| `poteto-help` | pstack | Helps pick a skill, playbook, or principle |
| `setup-pstack` | pstack | Model per role, set interactively; idstack's installer writes this file instead |
| **`id-mode`** | **idstack** | **Infra router over `poteto-mode`; idstack gates win, repo rules win over idstack** |

### Playbooks

In idstack: **new** is an idstack playbook, **overlay** means pstack's playbook plus idstack gates,
**unchanged** means pstack's as-is, **not for infra** means `id-mode` doesn't route infra work there.

| Playbook | Source | In idstack | For |
| --- | --- | --- | --- |
| investigation | pstack | unchanged | Read-only questions: how does X work, X or Y |
| bug-fix | pstack | overlay | Reproduce in live state read-only; fix through a change playbook |
| perf-issue | pstack | not for infra | App slowness against a baseline |
| hillclimb | pstack | not for infra | Iterative improvement of one metric |
| runtime-forensics | pstack | unchanged | Diagnose a live app symptom from instrumentation |
| trace-forensics | pstack | not for infra | Diagnose a captured profile or trace |
| feature | pstack | unchanged | New app behavior from a data shape |
| refactoring | pstack | unchanged | Behavior-preserving restructure |
| prototype | pstack | not for infra | Throwaway sketch to settle a decision |
| visual-parity | pstack | not for infra | Pixel-exact UI match |
| authoring-a-skill | pstack | unchanged | Write or edit a SKILL.md |
| eval | pstack | unchanged | Test a skill or prompt change on agent behavior |
| babysit | pstack | overlay | `gh` or `glab`; a deploying merge is a gate; classify CI failures before one retry |
| shipping | pstack | overlay | One gate per deploying merge, live verification between merges |
| autonomous-run | pstack | overlay | The exit predicate stops before any live change no grant covers |
| orchestrate | pstack | unchanged | Multi-day program with one coordinator |
| autopilot-full | pstack | unchanged | Queue of PRs driven to merged |
| autopilot-stack | pstack | unchanged | The same, operator merges |
| session-pickup | pstack | unchanged | Take over another agent's work |
| pause-safely | pstack | overlay | Checkpoint also records targets, held gates, stale plans, half-applied changes |
| multi-phase-plan | pstack | unchanged | Work across phases or stacked PRs |
| worktree-cleanup | pstack | unchanged | Prune worktrees and simulators |
| opening-a-pr | pstack | overlay | Repo conventions, issue reference, no AI attribution, public-repo hygiene check |
| **iac-change** | **idstack** | **new** | **Terraform or OpenTofu, from edit to verified apply** |
| **gitops-change** | **idstack** | **new** | **Kubernetes, Helm, Kustomize via ArgoCD or Flux** |
| **host-config-change** | **idstack** | **new** | **Ansible: canary, idempotence rerun, then the fleet** |
| **edge-change** | **idstack** | **new** | **DNS, proxy, firewall, VPN, TLS, allowlists** |
| **dependency-bump** | **idstack** | **new** | **Renovate or Dependabot backlogs; chart, provider, image, action bumps** |
| **upgrade** | **idstack** | **new** | **Clusters, platforms, managed services, hypervisors, apps** |
| **queue-burndown** | **idstack** | **new** | **A queue of PRs landed in order, with plan and apply** |
| **env-promotion** | **idstack** | **new** | **dev to QA to prod with only intended differences** |
| **decommission** | **idstack** | **new** | **Prove unused, park, soak, then tear down** |
| **secret-rotation** | **idstack** | **new** | **Rotate a credential across every consumer, including leaks** |
| **live-diagnosis** | **idstack** | **new** | **Read-only triage of a live symptom to a mechanism** |
| **incident** | **idstack** | **new** | **Declare, mitigate, draft messages, postmortem** |
| **restore-drill** | **idstack** | **new** | **Prove backups are fresh, independent, and restorable** |
| **drift-audit** | **idstack** | **new** | **Where live state differs from code** |
| **observability-audit** | **idstack** | **new** | **Coverage, alert hygiene, SLOs, cardinality** |
| **security-posture** | **idstack** | **new** | **Periodic own-asset security check against a baseline** |
| **vuln-response** | **idstack** | **new** | **One CVE: exposure, patch, proof it is gone** |
| **capacity-cost** | **idstack** | **new** | **Storage forecasts, right-sizing, spend, seats** |
| **readiness-review** | **idstack** | **new** | **Is a new service ready to depend on** |
| **agent-hosting** | **idstack** | **new** | **What self-hosted agents and bots can reach** |
| **closeout** | **idstack** | **new** | **End-of-session sweep and what's left** |

### Principles

| Principle | Source | Applies when |
| --- | --- | --- |
| laziness-protocol | pstack | Sizing a diff, tempted to add layers |
| foundational-thinking | pstack | Choosing core types and structures first |
| redesign-from-first-principles | pstack | Fitting a new requirement into an old design |
| attack-the-premise | pstack | Two fixes with one premise failed |
| subtract-before-you-add | pstack | Removing dead weight before building |
| minimize-reader-load | pstack | Code that is hard to trace |
| outcome-oriented-execution | pstack | Planned rewrites and migrations |
| experience-first | pstack | Product and UX tradeoffs |
| exhaust-the-design-space | pstack | A novel decision with no precedent |
| build-the-lever | pstack | Building the tool that does or proves the work |
| model-the-domain | pstack | Stateful or heavily branching logic |
| boundary-discipline | pstack | Validation and errors at system boundaries |
| type-system-discipline | pstack | Designing types and signatures |
| make-operations-idempotent | pstack | Anything that runs amid crashes and retries |
| migrate-callers-then-delete-legacy-apis | pstack | Replacing an internal API |
| separate-before-serializing-shared-state | pstack | Concurrent writers to one file, branch, or key |
| prove-it-works | pstack | Before declaring done |
| fix-root-causes | pstack | Debugging |
| sequence-verifiable-units | pstack | Multi-step work and commit or PR order |
| test-behavior-not-implementation | pstack | Writing or keeping tests |
| explain-the-number | pstack | Before trusting a measured number |
| guard-the-context-window | pstack | Context filling up |
| never-block-on-the-human | pstack | Reversible work only; idstack never applies it to live changes |
| encode-lessons-in-structure | pstack | The same instruction a second time |
| **plan-before-apply** | **idstack** | **Any live change: only a reviewed plan, diff, or check output goes in** |
| **pin-the-target** | **idstack** | **Any live command: name, check, and pass the target explicitly** |
| **prove-the-restore** | **idstack** | **Backups: unrestored is unproven, and independent of the source** |
| **reversible-first** | **idstack** | **Park before teardown, canary before fleet, one rule at a time** |

### Subagents

| Agent | Source | Job |
| --- | --- | --- |
| poteto-agent | pstack | Delegate inside a `poteto-mode` run |
| comment-sicko | pstack | Hunts needless code comments |
| **id-agent** | **idstack** | **Delegate inside an `id-mode` run: pinned target, read-only unless a gate passed** |
| **plan-reader** | **idstack** | **Read-only plan, diff, or check-mode summary: deletes, replaces, data, IAM, network, out of scope** |
| **change-verifier** | **idstack** | **Independent read-only check, from live state, that a change landed** |

### pstack workflow skills

idstack adds none of these and calls some of them from its playbooks.

| Skill | For | Used by idstack |
| --- | --- | --- |
| how, why, teach | Walkthroughs, design rationale, plain explanations | through pstack |
| architect, arena, swarm, interrogate | Design sketches, bakeoffs, fan-out, adversarial review | through pstack |
| blast-radius | What a change could break beyond the diff | through pstack |
| figure-it-out | A one-off playbook when none fits | fallback router target |
| show-me-your-work | Decision trail for long or unattended work | evidence log |
| recall, reflect, correct, automate-me | Context recovery, learning, mistake-proofing, style capture | |
| sharpen, in-your-own-words, ketchup, ketchup-video, bro | Prompting and catch-up | |
| unslop, technical-writing, no-comments | Prose and comment hygiene | |
| tdd, benchmark-checklist, statechart | Tests, measurements, state models | |
| create-verification-skill, maintain-verification-skill | Project skill that drives the app like a user | |
| create-formal-verification-skill, maintain-formal-verification-skill | Formal proofs of key properties | |
| typescript-best-practices, make-bot-ui | Language and UI specifics | |

### idstack tooling

| Item | Status | What it does |
| --- | --- | --- |
| `install.sh` | shipped | Installs pstack where missing, then idstack, on Claude Code, Codex, and OpenCode |
| pstack model files | shipped | Per-role models from `config/pstack-models.json`, routed across providers through T3 Code or each provider's CLI, with a native fallback |
| `scripts/check.py` | shipped | ASCII, manifests, links, router catalog against playbook files, names |
| `idstack plan-summary` | shipped | Deterministic Terraform/OpenTofu plan summary and grant predicate (`--predicate`, exit 1 on fail) |
| `idstack judge` | shipped | Runs one Jev battery from `src/questions/`; `--eval` checks it against labeled cases ([calibration](docs/jev-calibration.md)) |
| `idstack doctor` | shipped | Harnesses, pstack, domain skills, infra CLIs, Jev key, guard mode; `--live` probes kube write access read-only |
| `idstack guard` | shipped | Opt-in hook: `log` or `ask` mode, `allow-once` tokens for harnesses that cannot ask, optional Jev for ambiguous commands |
| `idstack build` | shipped | Generates Codex agent TOML, OpenCode agents, and Codex skill policies from the sources |
| `/idstack:setup` | shipped | Doctor report, model files, guard mode and install, Jev |
| Codex and OpenCode subagent files | shipped | `id-agent`, `plan-reader`, `change-verifier`, linked by `install.sh` |

## Compatibility

| Harness | idstack | pstack |
| --- | --- | --- |
| Claude Code | plugin from this repo's marketplace | `pstack@cursor-plugins`, installed as a declared dependency |
| Codex | plugin from this repo's marketplace | the `backnotprop/pstack` mirror, pinned to one commit, in `~/.agents/skills` |
| OpenCode | skills linked into `~/.config/opencode/skills` | the same pinned mirror in `~/.agents/skills` |

## License

MIT

## Project and support

Made by [iuliandita](https://iuliandita.com). [Other projects](https://iuliandita.com/projects/).

See [installation and recovery](INSTALL.md), [contributing](CONTRIBUTING.md),
[documentation](docs/README.md), and [private security reporting](SECURITY.md).

[agents](https://github.com/iuliandita/agents) provides global prompts and role definitions;
[skills](https://github.com/iuliandita/skills) provides the domain skills idstack calls by name;
[mods](https://github.com/iuliandita/mods) provides Claude Code mods. Installing one collection
does not install the others.
