# idstack

Infra, DevOps, and SRE playbooks for coding agents, layered on
[pstack](https://github.com/cursor/plugins/tree/main/pstack).

pstack gives agents a rigorous way to do software work. idstack adds what infra work needs and app
work does not: plan before apply, pin the target before touching it, prove that backups restore,
and never let a green check stand in for the live state.

Status: pre-alpha. The installer, manifests, and CI work; the playbooks are designed but not
written yet. See the [roadmap](docs/plan.md#15-roadmap).

## Install

```sh
git clone https://github.com/iuliandita/idstack.git
cd idstack
./install.sh --check    # what is installed, what is missing
./install.sh            # install pstack (if missing) and idstack on every harness found
```

The installer finds Claude Code, Codex, and OpenCode on your PATH, installs pstack wherever it is
missing, then installs idstack. `--harness claude,codex` limits it, `--dry-run` prints the
commands without running them.

Claude Code only, without the clone:

```text
/plugin marketplace add cursor/plugins
/plugin marketplace add iuliandita/idstack
/plugin install idstack@idstack
```

idstack declares pstack as a dependency, so the last line installs both. The `cursor/plugins`
marketplace has to be added first. [INSTALL.md](INSTALL.md) covers Codex, OpenCode, updates,
channels, and removal.

## What it is

- A router skill, `/idstack:id-mode`, that sits on top of pstack's `poteto-mode` and routes infra
  tasks to idstack playbooks, and everything else to pstack's.
- 21 playbooks for change (IaC, GitOps, host config, edge, upgrades, dependency bumps), diagnosis
  (live triage, incidents), and assurance (restore drills, drift, monitoring, security posture,
  capacity and cost). The catalog is in [docs/playbooks.md](docs/playbooks.md).
- A safety model: reads are free, reversible writes are free, and anything that changes live state
  stops at a gate that shows the exact command, target, blast radius, rollback, and evidence.
- An optional decision layer that uses TypeSafe's Jev for cheap typed judgments. Its answers can
  only make a gate stricter.

Domain knowledge (how Terraform, Kubernetes, or Prometheus work) stays in separate domain skills.
idstack holds the process. The design is in [docs/plan.md](docs/plan.md).

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
