#!/usr/bin/env python3
"""Entry point of the idstack guard hook: runs `bin/idstack` with the arguments it was given.

When the CLI cannot be loaded (Python older than 3.11, a damaged checkout) a plain call would exit
with a traceback and the harness would run the command unchecked. This file then answers for the
CLI: it holds the command when the guard is in ask mode or its settings cannot be read, and stays
silent otherwise, so a plugin user who never enabled the guard is not prompted.

Standard library only, and only syntax that every Python 3 accepts.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "bin", "idstack")
MODES = ("off", "log", "ask")


def guard_mode():
    """The guard mode as `guard_config` in the CLI reads it, with `json` alone."""
    home = os.path.expanduser("~")
    base = os.environ.get("IDSTACK_CONFIG_DIR") or os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.join(home, ".config")), "idstack"
    )
    path = os.path.join(base, "guard.json")
    mode = "off"
    if os.path.isfile(path):
        try:
            with open(path) as fh:
                mode = json.load(fh).get("mode", "off")
        except Exception:
            mode = "ask"
    if mode not in MODES:
        mode = "ask"
    env = os.environ.get("IDSTACK_GUARD_MODE")
    if env:
        env = env if env in MODES else "ask"
        mode = max(mode, env, key=MODES.index)
    return mode


def hold(harness, error):
    msg = (
        "idstack guard could not start (%s: %s); the command was held. The operator can fix python3 "
        "(3.11 or later) and the idstack checkout, or turn the guard off." % (type(error).__name__, error)
    )
    if harness in ("claude", "codex"):
        decision = "ask" if harness == "claude" else "deny"
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": msg,
            }
        }
    else:
        out = {"decision": "deny", "reason": msg}
    print(json.dumps(out))


def harness_of(argv):
    for i, arg in enumerate(argv):
        if arg == "--harness" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--harness="):
            return arg.split("=", 1)[1]
    return "claude"


def main():
    argv = sys.argv[1:]
    try:
        from importlib.machinery import SourceFileLoader
        from importlib.util import module_from_spec, spec_from_loader

        sys.dont_write_bytecode = True  # leave the checkout as it was
        loader = SourceFileLoader("idstack_cli", CLI)
        cli = module_from_spec(spec_from_loader("idstack_cli", loader))
        loader.exec_module(cli)
    except Exception as error:
        if guard_mode() == "ask":
            hold(harness_of(argv), error)
        return 0
    sys.argv = [CLI] + argv
    return cli.main()


if __name__ == "__main__":
    sys.exit(main())
