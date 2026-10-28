---
name: setup
description: >-
  Check and configure idstack on this machine: what is installed or missing,
  pstack model routing, the opt-in guard for state-mutating infra commands, and
  Jev. Use for /idstack:setup, "set up idstack", "idstack doctor", or turning the
  idstack guard on or off.
disable-model-invocation: true
---

# idstack setup

Report first, then change only what the operator picks. Every step here is local and reversible; none touches infrastructure.

1. Find the CLI: run `idstack --help`. Claude Code puts the plugin's `bin/` on the Bash PATH. On Codex and OpenCode, `install.sh` links `~/.local/bin/idstack`. If neither works, say so, give the install command from the idstack README, and stop.
2. Run `idstack doctor --json`. Report each `fail` and `warn` in one line with its fix. A missing domain skill is a warning: its playbook steps use the fallback in `id-mode`'s `references/skill-map.md`.
3. Ask whether to probe credentials: `idstack doctor --live` runs `kubectl auth can-i` against the current kube context. It is read-only, but it does contact the cluster, so run it only on a yes.
4. Model routing. pstack reads its per-role models from `~/.claude/rules/pstack-models.md` (Claude Code) and `~/.agents/pstack-models.md` (Codex, OpenCode). If doctor reports them missing or stale, offer `./install.sh --harness <claude|codex|opencode>` from the idstack clone; it writes the file for each selected harness (Claude Code's, or the shared Codex and OpenCode one) and keeps a hand-edited file unless `--force` is given. To change a role's model, put it in `~/.config/idstack/models.json` (same shape as the clone's `config/pstack-models.json`, only the keys to change) and rerun the installer; `python3 scripts/pstack_models.py --show` prints the merged result, and `--resolve <claude|codex|opencode>` shows what each role runs on from that harness with the CLIs this machine has.
5. Guard. Show `idstack guard status`. Explain the choice before asking:
   - `off` (default): nothing runs.
   - `log`: matching commands run and are logged to the idstack state directory.
   - `ask`: Claude Code asks before each matching command. Codex and OpenCode cannot ask, so they block it; the operator then runs `idstack guard allow-once '<command>'` in their own terminal.
   The guard also matches its own control commands (`allow-once`, `enable`, `disable`, `install`, `uninstall`), so with it on, the operator approves each of those too, and `allow-once` only works from an interactive terminal. The guard is a seatbelt, not a lock: scripts, aliases, quoting, and direct edits to its config files can get around it. The gates in `id-mode` still apply with the guard off.
   On a choice, run `idstack guard enable --mode <log|ask>` or `idstack guard disable`. For Codex, also run `idstack guard install --harness codex`, then tell the operator to trust the hook with `/hooks` in Codex. For OpenCode, run `idstack guard install --harness opencode`, then tell the operator to restart OpenCode. Test with `idstack guard test kubectl delete pod x`, which prints the match without running anything.
6. Jev. If `TYPESAFE_API_KEY` is set (check that it is set; never print it), offer `idstack guard enable --mode <current> --jev on`, which asks Jev about infra commands the rules do not match. It adds a call of up to 5 seconds to those commands and can only add asks, never remove them. Decision points in the playbooks use `idstack judge` either way.
7. End with what changed, what was left as is, and each remaining `fail` with its owner.
