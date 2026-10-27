# Install, update, and recovery

## Contents

- Requirements
- Install with the script
- What the script does on each harness
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
| `--force` | Codex and OpenCode: back up and replace existing skill folders that share a name with a pstack skill. |
| `--uninstall` | Remove idstack. pstack stays. |

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
`codex plugin add idstack@idstack`.

**OpenCode: idstack.** OpenCode has no plugin marketplace for skills. The script clones idstack to
`~/.local/share/idstack/src` (or uses the local checkout given with `--source`) and links each
folder under `skills/` into `~/.config/opencode/skills`. It writes the list of links to
`~/.config/opencode/skills/.idstack-install.json`. It never replaces a folder that is not one of its
links.

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

This removes idstack from each harness and leaves pstack in place. To remove pstack too:

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
| `IDSTACK_CACHE_DIR` | `~/.local/share/idstack` | The idstack clone OpenCode links point into. |

Pointing all five at a temporary directory gives an isolated install that touches nothing else,
which is how CI tests the script.

| Exit code | Meaning |
| --- | --- |
| 0 | Done, or (with `--check`) everything is installed. |
| 1 | A step failed, or (with `--check`) something is missing. |
| 2 | Usage error. |
| 3 | A required tool is missing. |
