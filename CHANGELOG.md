# Changelog

All notable changes to idstack are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow semver from v1.0.0;
v0.x was the prerelease phase, where breaking changes were expected.

## [Unreleased]

### Fixed

- `docs/plan.md`, INSTALL.md, and `src/questions/README.md` now match the code: the Codex guard install drops its
  own entry when the plugin ships the hook, `guard hook` accepts `--json`, and a flagged answer wins over a
  threshold tie.

## [1.2.0] - 2026-11-26

### Added

- `idstack guard trust HOST...` (and `untrust`) keep a `trusted_hosts` list in `guard.json`. The remote-only rules
  (`rm`, `kill`, `systemctl`, `docker rm`, package removal, `rsync --delete`, and the rest) no longer hold a command
  whose every ssh hop, or rsync target, is on the list. Infra-tool rules stay held behind a trusted host, and a hop
  to an untrusted host stays held. An agent cannot run `guard trust`. (#119)
- `antigravity` is a model-routing provider. A role can name `<model> <effort> via antigravity`; the script checks it
  against `agy models`, writes the `agy -p` read and write commands into `pstack-models.md`, and counts it reachable
  when `agy` is on PATH. The shipped roles do not use it. (#117)

## [1.1.5] - 2026-11-25

### Fixed

- The guard no longer holds a quoted heredoc fed to a script interpreter (`python3 - <<'EOF'` and the like) because its
  body mentions `bash -c` in backticks. The body is data there. Unquoted heredocs and a bare `bash -c` stay held.

## [1.1.4] - 2026-11-18

### Fixed

- The shipped model routes send the sol roles (`bug-fix`, `perf-issue`, `judgment and prose`,
  `hardest tasks`, `why synthesizer`, `reflect judgment, divergent, synthesizer`, and the codex
  entries in the arena, architect, and interrogate pools) to `gpt-6.2-sol` instead of
  `gpt-6.1-sol`. The INSTALL.md examples match.

## [1.1.3] - 2026-11-15

This release tightens the gates. Plans and commands that passed before can now stop or ask; each
change is listed under Security. The findings came from an independent review.

### Security

- `idstack plan-summary --predicate` needs `--scope` or `--scope-file` and exits 2 without one. A
  change with a missing or malformed `change` or `actions` fails as an unrecognized action, and any
  action list containing `delete` or `forget` is destructive.
- The predicate's IAM and network detection reads nested attributes. On create it counts `false` on
  `block_public_*`, `restrict_public_*`, and `ignore_public_*`, and unknown IAM or exposure
  attributes when the plan's `configuration` sets them or cannot show them. A Kubernetes workload
  that sets a container `port` now needs `--allow-network`, and one that sets
  `service_account_name` needs `--allow-iam`.
- Public IPs, EIPs, function URLs, CloudFront, and `kubernetes_service` count as network resources.
  Scope globs treat `[0]` and `["key"]` as literal text; only `*` and `?` are wildcards.
- `gates.md`: without the CLI a predicate grant cannot pass. The `jq` lines are a reading aid.
- The guard holds commands it cannot read: unparsable text that names a covered tool, deep nesting,
  a shell `-c` with no command, and a shell or `ssh` fed by a pipe, heredoc, or here-string. It
  recognizes commands behind launchers, substitutions, and unknown flags.
- The guard holds a command that runs something its own words do not show (`xargs`, `parallel`,
  `find -exec`, `env -S`, non-trivial `sed` and `awk`, and `tar`, `rsync`, and similar with an
  option that runs a command) whenever the command line names a covered tool. Some read-only
  pipelines that pass a covered tool's output to `xargs` or `awk` now ask.
- New guard rules: IAM grants, policy writes, firewall opens, deploys, remote commands, and
  public-access flags for `aws`, `gcloud`, and `az`; `pulumi`, `helmfile`, `eksctl`, `gsutil`,
  `vault` delete and revoke, and `docker compose down -v`; `gh` and `glab` merges and pipeline
  runs; `terraform refresh`, `test`, and `init -migrate-state`; destructive host commands over
  `ssh` and `rsync --delete` to a remote; and shell writes to the guard's own settings and
  approval files. Plain `git push` is not held.
- `guard allow-once` approvals are bound to the directory as well as the command text; pass `--cwd`
  and quote the command as one argument. `IDSTACK_GUARD_MODE` can raise the mode but no longer
  lower it. Guard state is created private (0700 directory, 0600 log).
- The plugin hooks start through `hooks/guard_hook.py`, which holds commands in ask mode when the
  CLI cannot load.
- Codex: the plugin loads its own guard hook (`hooks/codex.json` through
  `.codex-plugin/plugin.json`), shown as "idstack guard" in `/hooks` and answering `deny`. Before,
  Codex ran the Claude Code hook, whose `ask` answer Codex treats as a failed hook and then runs
  the command. Trust the hook again in `/hooks` after updating.
- `idstack judge` and the guard's judge call treat any answer that is not a number in [0, 1] as
  unsettled, and a non-object response as a failed call. `IDSTACK_JEV_URL` must be https and
  redirects are not followed. Environment assignments, secret-named values, URL credentials, and
  auth headers are masked before a command is sent.
- Playbooks stop at a gate before every state-mutating step: the leak revoke, new-value creation,
  and consumer rollout in `secret-rotation`, reference removal in `decommission`, the DNS TTL
  change in `edge-change`, and CI retriggers that hold an apply, deploy, sync, or publish job in
  `babysit`. A restore, even into a scratch namespace, is state-mutating.
- `host-config-change` runs check mode for the fleet batch before the fleet gate. It and
  `drift-audit` look for `check_mode: false` before any `--check` run. The Ansible predicate fails
  on `command`, `shell`, `raw`, and `script` tasks that would run.

### Fixed

- `install.sh`: more than one of `--check`, `--dry-run`, `--uninstall` is a usage error instead of
  the last flag winning. `--ref` is fetched and checked out on every run, so a tag pin survives a
  second run. Bash older than 4.4 and Python older than 3.11 exit 3 with one line.
- `install.sh --source` is local only when written as a path (`/abs`, `./rel`, `../rel`, `.`); a
  bare folder name is a usage error.
- An interrupted pstack copy is detected and redone: skills are staged beside the target and
  renamed into place, and the manifest gets its commit last. Failed git and harness commands land
  in `errors` with exit 1 instead of a bare abort.
- `install.sh --uninstall` no longer stops half way when a guard hook cannot be removed, keeps the
  CLI link and the shared model file while another harness still uses them, and still removes
  links when a harness CLI is not on PATH.
- `idstack guard install --harness codex` no longer adds a second entry when the plugin ships the
  hook, and removes one left by an earlier run; `idstack doctor` warns about two.
- `judge --eval` exits 1 when no cases are selected and 3 on a failed call. `doctor --live`
  reports a failed probe as failed. `build --check` flags generated files whose source is gone.
  With `--json`, human text goes to stderr, and an unexpected error still prints one JSON object.
- `scripts/check.py` reports a short mirror pin or a broken `config/pstack-lock.json` as a finding
  and still runs every other check. It requires a changelog section for the manifest version and
  compares all four version manifests.
- The `pstack-watch` workflow can open or update its issue on drift; before, the step stopped
  first.

### Changed

- CI runs the repo check, unit tests, and build check on Python 3.11 and the newest stable release.
  Release tags must be on `main`. Markdown lint runs with default rules on.
- `docs/plan.md`, the playbook catalog, and the check lists in CONTRIBUTING.md and AGENTS.md match
  what ships.

## [1.1.2] - 2026-11-06

### Fixed

- id-mode routes broker work to `backend-api` and app performance to `debug-triage`; skills v4.0.0
  retired `message-queues` and folded `performance-debugging` into `debug-triage`.
- Headless model-role runner templates set `IULIANDITA_MODS_NOTIFY=off`, so `claude -p`,
  `codex exec` and `opencode run` children no longer pop desktop notifications through the mods
  `notify` mod.

## [1.1.1] - 2026-11-03

### Added

- A `pstack-watch` workflow runs every six hours and opens an issue when upstream pstack or the mirror pin drifts from `config/pstack-lock.json`.

### Fixed

- The pstack mirror pin in `install.sh` moves from pstack 0.15.34 to 0.15.36, so Codex and OpenCode
  installs get the same pstack skills as Claude Code. `config/pstack-lock.json` records the new pin.

## [1.1.0] - 2026-10-29

### Added

- `install.sh --json` and `--json` on every `idstack` subcommand print one object with `ok` and
  `errors` plus command keys, documented in INSTALL.md.
- Vendored shared stack canon and checker under `.github/stack/`, run in the `lint` job, with a
  weekly `stack-sync` workflow that opens an issue when the canon in agents moves.
- `Environment` and `Exit codes` sections in every `idstack` subcommand `--help`.
- Wordmark and logo files in `assets/`.

### Changed

- Error messages name the next step to run.
- README opens with the wordmark, an agent setup prompt, and a `Part of the stack` section.
  CONTRIBUTING uses the shared headings and the version bump rule.
- CI jobs are named after their ids (`lint`, `install`, `zizmor`, `secrets`, `publish`), and the
  `install` job checks the `--json` output of `install.sh --check`.

### Breaking

- Usage errors in `idstack judge` exit 2 instead of 1: an unknown battery, an items file that is
  not a JSON array or cannot be read, and a missing items argument. Scripts that test for exit 1 on
  these should accept 2 and treat 1 as a runtime failure.
- `idstack guard install` and `uninstall` print a JSON object with `--json`. Previously they
  printed text, and `--dry-run` printed the bare config; with `--json` the config is under
  `config`. Without `--json` the output is unchanged.
- Every `--json` object now has top-level `ok` and `errors` keys, and the command's other keys
  stay where they were. A failed `plan-summary` predicate, a `judge` call error, a failed
  `build --check`, and a failed `doctor` check report `ok: false`; exit codes are unchanged.
- Error message text changed. Scripts that match the old wording should check the exit code.

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

[Unreleased]: https://github.com/iuliandita/idstack/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/iuliandita/idstack/compare/v1.1.5...v1.2.0
[1.1.5]: https://github.com/iuliandita/idstack/compare/v1.1.4...v1.1.5
[1.1.4]: https://github.com/iuliandita/idstack/compare/v1.1.3...v1.1.4
[1.1.3]: https://github.com/iuliandita/idstack/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/iuliandita/idstack/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/iuliandita/idstack/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/iuliandita/idstack/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/iuliandita/idstack/compare/v0.5.0...v1.0.0
[0.5.0]: https://github.com/iuliandita/idstack/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/iuliandita/idstack/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/iuliandita/idstack/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/iuliandita/idstack/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/iuliandita/idstack/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/iuliandita/idstack/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/iuliandita/idstack/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/iuliandita/idstack/releases/tag/v0.1.0
