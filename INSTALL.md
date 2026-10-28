# Install, update, and recovery

## Contents

- Requirements
- Install with the script
- What the script does on each harness
- pstack model files
- Install by hand
- Check, update, and channels
- Uninstall
- Recovery
- Environment and exit codes

## Requirements

- `bash`, `git`, and `python3` (standard library only).
- At least one harness: Claude Code 2.1.275 or later, Codex CLI with `codex plugin`, or OpenCode.
- Network access to GitHub.

## Install with the script

```sh
git clone https://github.com/iuliandita/idstack.git
cd idstack
./install.sh --check
./install.sh
```

| Option | Effect |
| --- | --- |
| `--harness LIST` | `claude`, `codex`, `opencode`, comma-separated. Default: every harness whose CLI is on PATH. |
| `--check` | Report what is installed and what is missing. Changes nothing. |
| `--dry-run` | Print the commands an install would run. Changes nothing. |
| `--source SRC` | Install idstack from `owner/repo`, a git URL, or a local checkout. Default: `iuliandita/idstack`. |
| `--force` | Back up and replace skill folders that share a name with a pstack skill, and pstack model files idstack did not write. |
| `--no-models` | Leave pstack's per-role model files alone. |
| `--uninstall` | Remove idstack and the model files it wrote. pstack stays. |

Running the script twice is safe. Each step checks the current state first and skips what is
already done.

## What the script does on each harness

**Claude Code.**

1. Adds the `cursor/plugins` marketplace if it is missing.
2. Installs `pstack@cursor-plugins` if it is missing.
3. Adds this repo as the `idstack` marketplace (or refreshes it) and installs or updates
   `idstack@idstack`.
4. Confirms with `claude plugin list --json` that both plugins are installed and enabled.

idstack declares pstack as a dependency, and its marketplace allows the cross-marketplace
dependency on `cursor-plugins`. Claude Code still needs the `cursor-plugins` marketplace added
before the install, which is why step 1 exists.

**Codex and OpenCode: pstack.** Upstream pstack ships no Codex or OpenCode packaging, so the
script uses the [backnotprop/pstack](https://github.com/backnotprop/pstack) mirror, pinned to the
commit in `PSTACK_MIRROR_REF` at the top of `install.sh`.

1. Fetches that commit with git and lists its skill folders.
2. Stops if any of those names already exists in `~/.agents/skills` and was not installed by this
   script. Rerun with `--force` to back the existing folders up and replace them.
3. Copies the skills into `~/.agents/skills`, which both Codex and OpenCode read, and records the
   commit and skill names in `~/.agents/skills/.pstack-install.json`.

If `~/.agents/skills/poteto-mode` already exists and the script did not install it, the script
leaves it alone and reports it as installed outside the script.

**Codex: idstack.** Adds this repo as the `idstack` marketplace and runs
`codex plugin add idstack@idstack`. Codex plugins cannot ship subagents, so the script links
`harness/codex/agents/*.toml` into `~/.codex/agents` and records them in
`~/.codex/agents/.idstack-install.json`.

**OpenCode: idstack.** OpenCode has no plugin marketplace for skills. The script clones idstack to
`~/.local/share/idstack/src` (or uses the local checkout given with `--source`) and links each
folder under `skills/` into `~/.config/opencode/skills`. It writes the list of links to
`~/.config/opencode/skills/.idstack-install.json`. It never replaces a folder that is not one of its
links. It links the subagents in `harness/opencode/agents` into `~/.config/opencode/agents` the
same way.

**Every harness: the CLI.** The script links `~/.local/bin/idstack` to `bin/idstack` in the clone
(the `--source` checkout, or `~/.local/share/idstack/src`). Claude Code also puts the plugin's own
`bin/` on the Bash PATH. The CLI needs Python 3.11 or later and nothing else.

**The guard is not installed.** It is opt-in: run `/idstack:setup`, or by hand:

```sh
idstack guard enable --mode ask            # or --mode log; Claude Code picks this up through the plugin hook
idstack guard install --harness codex      # then trust the hook with /hooks in Codex
idstack guard test kubectl delete pod x    # prints the match, runs nothing
```

Codex cannot ask, so in `ask` mode it blocks a matching command. After you approve
it, run `idstack guard allow-once '<command>'` in your own terminal, quoting the exact text the agent
used (any difference, even in spaces, needs a new approval), and let the agent rerun it.

## pstack model files

pstack picks a model and effort for each subagent role from a settings file. Without one it uses
its own defaults, which run judgment roles on Opus at `xhigh` and code roles on the session model.
The script writes both settings files from [config/pstack-models.json](config/pstack-models.json):

| File | Read by |
| --- | --- |
| `~/.claude/rules/pstack-models.md` | Claude Code, loaded into every session |
| `~/.agents/pstack-models.md` | Codex and OpenCode, read when pstack picks a model |

Roles route across providers. A value such as `gpt-6.1-terra medium via codex else sonnet medium`
runs on Codex by the first route available: T3 Code's `delegate_task` when the session runs under
T3, otherwise the `codex` CLI headless (`codex exec`, `claude -p`, or `opencode run`, read-only
unless the role edits files), otherwise Sonnet with the harness's own subagent tool. Values
without `via` always run natively. The exact commands live in the `t3` section of the JSON and are
copied into each file.

A Codex session calling `claude -p` or `opencode run` needs network access in its sandbox; the
default `workspace-write` sandbox blocks it, so those roles fall through to the native model there
unless you allow network access.

| Role group | From Claude Code | From Codex |
| --- | --- | --- |
| Routine code, swarm workers | Terra via Codex, else Sonnet | Terra |
| Bug fixes, performance | Sol via Codex, else Opus | Sol |
| Exploration (`how`, `why` investigators) | DeepSeek Flash via OpenCode, else Haiku | DeepSeek Flash via OpenCode, else Luna |
| Judgment and prose | Opus | Opus via Claude, else Sol |
| Hardest tasks, synthesizers | Opus | Sol |
| Review panels (arena, architect, interrogate) | Opus plus Sol via Codex | Sol plus Opus via Claude |

Effort starts at `medium` and goes to `high` only for hard roles; fast mode and the priority tier
are off. Before writing, the script checks every role is present and every value parses. It checks
Claude Code models against the names its subagents accept, Codex models and efforts against
`codex debug models` (only when Codex is signed in; signed out it lists an older bundled catalog),
OpenCode models against `opencode models`, and T3 Claude models and DeepSeek Flash efforts against
the lists in the JSON. A CLI that is missing or signed out is skipped with a warning.

Each file carries a `managed by idstack` line. The script replaces only files with that line. If
you ran `/setup-pstack` yourself, it leaves your file alone and reports it; `--force` backs it up
to `.idstack-backups/` next to the file and replaces it. Delete the marker line to keep your own
edits, or change the JSON and rerun `./install.sh`. To run the step on its own:

```sh
python3 scripts/pstack_models.py --check
python3 scripts/pstack_models.py --target claude
```

## Install by hand

Claude Code:

```text
/plugin marketplace add cursor/plugins
/plugin marketplace add iuliandita/idstack
/plugin install idstack@idstack
```

Codex:

```sh
npx skills add https://github.com/backnotprop/pstack/tree/<commit> -g -a codex --skill '*' -y
codex plugin marketplace add iuliandita/idstack
codex plugin add idstack@idstack
```

Use the commit from `PSTACK_MIRROR_REF` in `install.sh`. The `skills` CLI does not check for name
collisions the way the script does.

OpenCode: install pstack the same way with `-a opencode`, then link the folders under this repo's
`skills/` into `~/.config/opencode/skills`.

## Check, update, and channels

- `./install.sh --check` exits 0 when everything is installed and 1 when something is missing.
- `git pull` in your clone, then `./install.sh`, updates idstack on every harness. The pstack mirror
  is reinstalled when the pinned commit changes.
- Claude Code leaves auto-update off for third-party marketplaces. Turn it on in `/plugin`, on the
  marketplaces tab, or update by hand with `claude plugin update idstack@idstack`.
- Channels: the `develop` branch is the nightly channel, and `/plugin marketplace add
  iuliandita/idstack` tracks it. Prereleases (`v0.x.y`) are tagged from `develop`. Stable releases
  (`v1.0.0` and later) are tagged from `main`; pin one with `iuliandita/idstack#main` or a tag.

## Uninstall

```sh
./install.sh --uninstall
```

This removes idstack, its subagent links, the CLI link, the Codex guard hook if it installed one, and the model files it wrote, and leaves pstack in place. Guard settings in
`~/.config/idstack` and logs in `~/.local/state/idstack` stay; delete them by hand if you want. To remove pstack too:

- Claude Code: `claude plugin uninstall pstack@cursor-plugins`.
- Codex and OpenCode: delete the folders listed in `~/.agents/skills/.pstack-install.json`, then
  the file itself.

## Recovery

- **A collision stopped the install.** The error lists the names. Rename or move your own skills,
  or rerun with `--force`, which moves them to `~/.agents/.idstack-backups/<timestamp>/` first.
- **Restore a backup.** Move the folder from `~/.agents/.idstack-backups/<timestamp>/` back into
  `~/.agents/skills/`. Delete the pstack folder of the same name first.
- **Claude Code says the pstack dependency was not found.** Add the marketplace with
  `/plugin marketplace add cursor/plugins` and install again.
- **A partial install.** Run `./install.sh --check` to see what is missing, then `./install.sh` again.

## Environment and exit codes

| Variable | Default | Used for |
| --- | --- | --- |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | Read by the `claude` CLI. |
| `CODEX_HOME` | `~/.codex` | Read by the `codex` CLI. |
| `AGENTS_SKILLS_DIR` | `~/.agents/skills` | Where pstack goes for Codex and OpenCode. |
| `OPENCODE_SKILLS_DIR` | `~/.config/opencode/skills` | Where idstack skills are linked for OpenCode. |
| `IDSTACK_CACHE_DIR` | `~/.local/share/idstack` | The idstack clone OpenCode links and the CLI link point into. |
| `IDSTACK_BIN_DIR` | `~/.local/bin` | Where the `idstack` CLI is linked. |
| `OPENCODE_AGENTS_DIR` | `~/.config/opencode/agents` | Where idstack subagents are linked for OpenCode. |

The CLI itself reads `IDSTACK_CONFIG_DIR` (default `~/.config/idstack`), `IDSTACK_STATE_DIR`
(default `~/.local/state/idstack`), and `IDSTACK_GUARD_MODE` (`off`, `log`, or `ask`, overriding
the config file).

Pointing all of the installer's variables at a temporary directory gives an isolated install that touches nothing else,
which is how CI tests the script.

| Exit code | Meaning |
| --- | --- |
| 0 | Done, or (with `--check`) everything is installed. |
| 1 | A step failed, or (with `--check`) something is missing. |
| 2 | Usage error. |
| 3 | A required tool is missing. |
