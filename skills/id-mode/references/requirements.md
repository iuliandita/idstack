# Requirements

idstack layers on pstack. Check it before any work. If it is missing, stop, name it, and give the install command. Do not improvise pstack's playbooks or principles from memory.

| Need | Installed when | Reach its files |
| --- | --- | --- |
| pstack | `setup-pstack` (Claude Code: `pstack:setup-pstack`) is in your skill list, or `~/.agents/skills/poteto-mode/SKILL.md` exists | Most pstack skills are slash-only and hidden. They sit beside `setup-pstack`: `<setup-pstack dir>/../poteto-mode/SKILL.md`, `../poteto-mode/playbooks/<name>.md`, `../principle-<name>/SKILL.md`. On Codex and OpenCode they are in `~/.agents/skills/`. |
| idstack subagents | Claude Code lists `idstack:id-agent`, `idstack:plan-reader`, `idstack:change-verifier` as subagent types | Elsewhere, use the default subagent with the brief rule in the router's Subagents section. |
| Domain skills | Listed in your skill list | Optional. See [skill-map.md](skill-map.md) for each one's fallback. |
| idstack CLI | `idstack --help` runs. Claude Code puts the plugin's `bin/` on the Bash PATH; `install.sh` links `~/.local/bin/idstack` for Codex and OpenCode | Optional. Without it, use the `jq` predicates in [gates.md](gates.md) and skip Jev. `idstack doctor` reports what else is missing. |
| Jev | The **jevify** or **typesafe-ai** skill is listed and `TYPESAFE_API_KEY` is set (check it is set, never print it) | Optional. Run decision points with `idstack judge <battery>`; it exits 4 without a key. Without it, the decision point uses its deterministic checks and the reply says Jev was not used. |

Install pstack:

- Claude Code: `/plugin marketplace add cursor/plugins`, then `/plugin install pstack@cursor-plugins` (installing idstack pulls it in as a dependency).
- Codex and OpenCode: `./install.sh` from an idstack clone installs the pinned pstack mirror into `~/.agents/skills`.
