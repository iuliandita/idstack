#!/usr/bin/env python3
"""Write pstack's per-role model files from config/pstack-models.json.

Usage: pstack_models.py [--target claude|agents ...] [--check|--dry-run|--uninstall] [--force]

claude -> $CLAUDE_CONFIG_DIR/rules/pstack-models.md (default ~/.claude)
agents -> <parent of $AGENTS_SKILLS_DIR>/pstack-models.md (default ~/.agents), read by Codex and OpenCode

Exit codes: 0 ok, 1 failure or (with --check) not current, 2 usage, 3 invalid config.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "pstack-models.json"
MARKER = "# managed by idstack: edit config/pstack-models.json in idstack, or delete this line to take the file over."
EFFORTS = ("low", "medium", "high", "xhigh", "max")
CLAUDE_MODELS = ("opus", "sonnet", "haiku", "fable")
# The role labels pstack's setup-pstack writes, in its order.
ROLES = (
    "feature, refactoring", "bug-fix", "perf-issue", "hillclimb", "judgment and prose",
    "hardest tasks", "how explorer", "how explainer", "why investigators", "why synthesizer",
    "reflect tooling", "reflect judgment, divergent, synthesizer", "arena runners",
    "arena cross-judge pool", "swarm workers", "architect runners", "interrogate reviewers",
)


def target_path(target: str) -> Path:
    home = Path.home()
    if target == "claude":
        return Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude")) / "rules" / "pstack-models.md"
    skills = Path(os.environ.get("AGENTS_SKILLS_DIR", home / ".agents" / "skills"))
    return skills.parent / "pstack-models.md"


def codex_models() -> dict[str, set[str]] | None:
    if not shutil.which("codex"):
        return None
    try:
        out = subprocess.run(["codex", "debug", "models"], check=True, capture_output=True, text=True, timeout=60).stdout
        models = json.loads(out)["models"]
    except (subprocess.SubprocessError, OSError, ValueError, KeyError):
        return None
    return {m["slug"]: {e["effort"] for e in m.get("supported_reasoning_levels", [])} for m in models}


def validate(target: str, roles: dict[str, str]) -> list[str]:
    errors = []
    if set(roles) != set(ROLES):
        missing, extra = set(ROLES) - set(roles), set(roles) - set(ROLES)
        errors += [f"{target}: missing role {r!r}" for r in sorted(missing)]
        errors += [f"{target}: unknown role {r!r}" for r in sorted(extra)]
    known = codex_models() if target == "agents" else None
    if target == "agents" and known is None:
        print(f"warning: codex is not available; {target} model names were not checked against its catalog", file=sys.stderr)
    for role, value in roles.items():
        for entry in (v.strip() for v in value.split(",")):
            if entry in ("inherit-parent", "auto"):
                continue
            parts = entry.split()
            if len(parts) != 2 or parts[1] not in EFFORTS:
                errors.append(f"{target}: {role}: {entry!r} is not '<model> <effort>'")
                continue
            model, effort = parts
            if target == "claude" and model not in CLAUDE_MODELS:
                errors.append(f"{target}: {role}: unknown Claude Code model {model!r}")
            elif known is not None and model not in known:
                errors.append(f"{target}: {role}: codex does not list model {model!r}")
            elif known is not None and effort not in known[model]:
                errors.append(f"{target}: {role}: {model} does not support effort {effort!r}")
    return errors


def render(spec: dict) -> str:
    lines = [
        "# pstack model configuration. One line per role. Delete a line to fall back to the skill default.",
        "# `inherit-parent` or `auto` as a value: the role runs on the parent chat model (omit the subagent `model`).",
        MARKER,
        *(f"# {note}" for note in spec.get("notes", [])),
        f"# budget: {spec['budget']}",
        *(f"{role}: {spec['roles'][role]}" for role in ROLES),
    ]
    return "\n".join(lines) + "\n"


def backup(path: Path) -> Path:
    dest = path.parent / ".idstack-backups" / time.strftime("%Y%m%d-%H%M%S") / path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(path, dest)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description="Write pstack's per-role model files.")
    ap.add_argument("--target", action="append", choices=("claude", "agents"))
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--uninstall", action="store_true")
    ap.add_argument("--force", action="store_true", help="back up and replace a file idstack did not write")
    args = ap.parse_args()
    targets = args.target or ["claude", "agents"]

    config = json.loads(CONFIG.read_text())
    if not args.uninstall:
        errors = [e for t in targets for e in validate(t, config[t]["roles"])]
        if errors:
            for e in errors:
                print(f"error: {e}", file=sys.stderr)
            return 3

    rc = 0
    for target in targets:
        path = target_path(target)
        current = path.read_text() if path.exists() else None
        managed = current is not None and MARKER in current
        label = f"pstack models ({target})"
        if args.uninstall:
            if managed:
                path.unlink()
                print(f"  removed {path}")
            continue
        wanted = render(config[target])
        if args.check:
            state = "ok" if current == wanted else "absent" if current is None else "outdated" if managed else "not managed by idstack"
            print(f"  {label:<28} {state} ({path})")
            rc |= state != "ok"
            continue
        if current == wanted:
            print(f"  {label}: current")
            continue
        if current is not None and not managed and not args.force:
            print(f"error: {path} was not written by idstack; rerun with --force to back it up and replace it", file=sys.stderr)
            rc = 1
            continue
        if args.dry_run:
            print(f"would write {path}")
            continue
        if current is not None and not managed:
            print(f"  backed up {path} to {backup(path)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(wanted)
        print(f"  wrote {path}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
