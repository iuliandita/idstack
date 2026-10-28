# Changelog

All notable changes to idstack are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow semver from v1.0.0;
v0.x was the prerelease phase, where breaking changes were expected.

## [Unreleased]

## [1.0.0] - 2026-10-28

First stable release. idstack runs on Claude Code, Codex, and OpenCode, and under T3 Code on any of
them, with the router, 21 playbooks, 6 overlays, 4 principles, 3 subagents, the `idstack` CLI, the
opt-in guard, and per-role model routing that works with any mix of installed harnesses.

### Added

- A stable channel: `main` gets each tagged release, `develop` stays the nightly. `install.sh --ref`
  picks the branch or tag (default `main`), and the documented install commands pin `main`.
- CONTRIBUTING describes the release flow from `develop` to `main`.

### Fixed

- `scripts/pstack_models.py --resolve` no longer crashes on `auto` or `inherit-parent` roles.
- `scripts/eval.py --scenario` with an unknown id exits 2 instead of passing with nothing run.

### Changed

- Removed a pass-through helper in the build generator; generated files are unchanged.

Not yet met from the v1.0 exit criteria in docs/plan.md: a user guide, a review of each playbook
against real use, and two weeks of daily use without a gate bypass (issue #26).

## [0.5.0] - 2026-10-28

Model routing for any mix of harnesses.

### Changed

- One role table for every harness. Each role chains an option per provider, so it resolves on
  Claude Code, Codex, or OpenCode alone, any two of them, or all three; `or` groups keep roles such
  as "hardest tasks" on the current harness's own model. With all three installed, each harness
  routes as before.
- `~/.config/idstack/models.json` takes one top-level `roles` object. A 0.4.0 file with `claude` and
  `agents` sections is rejected with a note on how to move it.

### Added

- `scripts/pstack_models.py --resolve <harness>` prints what each role runs on this machine.
- Tests resolve every role for every combination of installed harnesses.

## [0.4.1] - 2026-10-28

### Fixed

- The OpenCode guard checked only string commands; a command given as a list went through
  unchecked. Lists now go to the guard, and a shell call with any other shape is held.

## [0.4.0] - 2026-10-28

OpenCode as a full harness, and your own model choices.

### Added

- OpenCode guard: `idstack guard install --harness opencode` adds a plugin to `opencode.json` that
  blocks matching shell calls, the same way the Codex hook does.
- Model overrides in `~/.config/idstack/models.json`, merged over the shipped defaults and checked
  the same way; `scripts/pstack_models.py --show` prints the result.
- `scripts/eval.py --harness opencode` runs the gate scenarios through `opencode run`, with this
  checkout's guard loaded in ask mode.
- `idstack doctor` checks OpenCode's subagents, OpenCode skill permissions that would block
  idstack or pstack, and whether the guard is installed on each harness when it is enabled.
- README shows the OpenCode form (`@id-mode`) and a per-harness parity table.

### Changed

- Every role in the shared Codex and OpenCode model file names its provider. A role whose provider
  is the current harness runs natively; from OpenCode, Codex models go through `codex exec` and
  Claude models through `claude -p`. An `else` model the harness cannot run falls back to the
  session's model.
- The read-only OpenCode route uses `opencode run --agent plan`.
- `guard install` and `guard uninstall` leave a config alone when there is nothing to change.

## [0.3.2] - 2026-10-28

### Fixed

- Grant predicates check the attributes of created resources, so a new instance with an IAM
  profile or security groups needs `--allow-iam` or `--allow-network`. Inline network rule blocks
  count as network changes.
- `plan-summary` diffs replace values Terraform marks sensitive with `(sensitive)`.
- Guard: `bash -lc` and other combined shell flags are unwrapped; current Terragrunt forms
  (`run --all apply`, `--working-dir`) match. A hook that fails (unwritable state, corrupt
  `guard.json`) now asks or blocks instead of letting the command through.
- `install.sh --check` reports links that went missing behind an existing install record.
- `scripts/eval.py` drops cloud credential variables from the agent's environment.

### Changed

- Docs describe the shipped CLI, installer, and guard; docs/plan.md reads as a design record.
- Python is formatted and linted with ruff (`ruff.toml`); CI runs it.

## [0.3.1] - 2026-10-28

### Fixed

- Codex usage: plugin skills are namespaced, so the README now shows `$idstack:id-mode` and
  `$idstack:setup`; the bare `$id-mode` loaded nothing. `scripts/eval.py` uses the same form.
- README says how to start a delegated or headless task so the explicit-only skills load.

## [0.3.0] - 2026-10-28

The `idstack` CLI, the opt-in guard, and native subagents on Codex and OpenCode.

### Added

- `idstack` CLI (Python 3.11+, standard library only): `plan-summary` with a `--predicate` check
  for grants, `judge` for Jev decision points with `--eval` and `--example`, `doctor`, `check`,
  `build`, and `guard`.
- Eight Jev batteries in `src/questions/` with labeled cases in `fixtures/jev/`. Every battery has
  zero false negatives on its tune and holdout splits; results are in `docs/jev-calibration.md`.
- Opt-in guard for state-mutating infra commands (Terraform/OpenTofu, kubectl, Helm, ArgoCD, Flux,
  Ansible, Velero, Proxmox, libvirt, cloud CLIs, remote systemctl and reboot). Claude Code asks
  through the plugin hook; Codex blocks, with `idstack guard allow-once` for an approved command.
  Off by default; `log` mode records without stopping. No OpenCode guard yet. The guard's own control
  commands are guarded, and `allow-once` needs an interactive terminal, so an agent cannot approve
  itself through the CLI.
- `/idstack:setup` skill: doctor report, model files, guard mode and install, Jev.
- Generated Codex agent TOML, OpenCode agents, and Codex skill policies
  (`idstack build`); `install.sh` links the agents and the CLI and removes them on uninstall.
- Unit tests for the CLI; CI runs them and checks that generated files are current.
- Fixture estate (`fixtures/infra`, offline `terraform_data` only), scenario plans, and
  `scripts/eval.py`, which runs gate scenarios headless on Claude Code and Codex and checks the
  commands the agent ran.

### Changed

- Grant predicates for Terraform also fail on IAM and network changes unless the grant names them
  (`--allow-iam`, `--allow-network`).
- Playbooks call `idstack plan-summary` and `idstack judge` at their plan and Jev steps, and
  `gates.md` uses `plan-summary --predicate` for Terraform grants, with the `jq` form as fallback.
- README lists what pstack ships and what idstack adds, overlays, or leaves out.

## [0.2.0] - 2026-10-28

The skills ship: `/idstack:id-mode` now exists and routes infra work.

### Added

- `id-mode` router over pstack's `poteto-mode`, with references for requirements, gates and
  grants, evidence and reply sections, target pinning, and the domain skill map.
- 21 playbooks (10 change, 2 diagnose, 7 assure, 2 operate) and 6 overlays on pstack playbooks
  (`bug-fix`, `babysit`, `shipping`, `opening-a-pr`, `autonomous-run`, `pause-safely`).
- Principle skills: plan-before-apply, pin-the-target, prove-the-restore, reversible-first.
- Subagents: `id-agent`, `plan-reader`, `change-verifier`.
- `scripts/check.py` checks skill and agent names, the router catalog against the playbook files,
  and reference paths.

### Fixed

- Codex now gets new idstack versions: the installer reinstalls the plugin when the marketplace
  version is missing from the Codex plugin cache, and `--check` reports it as outdated.

## [0.1.0] - 2026-10-28

First prerelease: the installer, plugin manifests, model routing, CI, and docs. No idstack
playbooks yet.

### Added

- Design plan and playbook catalog (`docs/plan.md`, `docs/playbooks.md`).
- Plugin manifests for Claude Code (with a declared dependency on `pstack@cursor-plugins`) and Codex.
- `install.sh`: installs idstack and pstack on Claude Code, Codex, and OpenCode, with `--check`,
  `--dry-run`, `--force`, and `--uninstall`.
- pstack model files for Claude Code and Codex/OpenCode, generated from
  `config/pstack-models.json`, routing roles across providers through T3 Code with a native
  fallback, and validated against the harness model catalogs.
- User docs: README, INSTALL, CONTRIBUTING, SECURITY, and a docs index.
- Repository checks (`scripts/check.py`), CI with an isolated install smoke test on pinned Claude
  Code and Codex CLIs, security scanning, release workflow, issue and PR templates, and Dependabot
  for workflow actions and the pinned CLIs.

[Unreleased]: https://github.com/iuliandita/idstack/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/iuliandita/idstack/compare/v0.5.0...v1.0.0
[0.5.0]: https://github.com/iuliandita/idstack/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/iuliandita/idstack/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/iuliandita/idstack/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/iuliandita/idstack/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/iuliandita/idstack/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/iuliandita/idstack/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/iuliandita/idstack/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/iuliandita/idstack/releases/tag/v0.1.0
