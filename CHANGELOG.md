# Changelog

All notable changes to idstack are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow semver from v1.0.0;
v0.x is the prerelease phase, where breaking changes are expected.

## Unreleased

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
