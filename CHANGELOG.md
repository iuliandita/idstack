# Changelog

All notable changes to idstack are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow semver from v1.0.0;
v0.x is the prerelease phase, where breaking changes are expected.

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
