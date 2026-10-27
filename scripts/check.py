#!/usr/bin/env python3
"""Repository checks for idstack. Run from anywhere: python3 scripts/check.py [--json]."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "idstack"
DEPENDENCY = {"name": "pstack", "marketplace": "cursor-plugins"}
TEXT_SUFFIXES = {".md", ".json", ".yml", ".yaml", ".py", ".sh", ".toml", ".txt", ""}


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, check=True, capture_output=True,
    ).stdout.decode()
    return [ROOT / p for p in out.split("\0") if p and (ROOT / p).is_file()]


def load_json(path: Path, findings: list[str]):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        findings.append(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
        return None


def check_ascii(files: list[Path], findings: list[str]) -> None:
    for path in files:
        if path.suffix not in TEXT_SUFFIXES:
            continue
        for lineno, line in enumerate(path.read_bytes().splitlines(), 1):
            if any(b > 127 for b in line):
                findings.append(f"{path.relative_to(ROOT)}:{lineno}: non-ASCII character")
                break


def check_json_files(files: list[Path], findings: list[str]) -> None:
    for path in files:
        if path.suffix == ".json":
            load_json(path, findings)


def check_manifests(findings: list[str]) -> None:
    plugin = load_json(ROOT / "plugin.json", findings)
    claude_plugin = load_json(ROOT / ".claude-plugin/plugin.json", findings)
    claude_market = load_json(ROOT / ".claude-plugin/marketplace.json", findings)
    codex_market = load_json(ROOT / ".agents/plugins/marketplace.json", findings)
    if None in (plugin, claude_plugin, claude_market, codex_market):
        return

    claude_entry = next((p for p in claude_market.get("plugins", []) if p.get("name") == NAME), None)
    codex_entry = next((p for p in codex_market.get("plugins", []) if p.get("name") == NAME), None)
    if claude_entry is None:
        findings.append(".claude-plugin/marketplace.json: no plugin entry named idstack")
    if codex_entry is None:
        findings.append(".agents/plugins/marketplace.json: no plugin entry named idstack")

    for label, doc in (("plugin.json", plugin), (".claude-plugin/plugin.json", claude_plugin)):
        if doc.get("name") != NAME:
            findings.append(f"{label}: name must be {NAME}")

    versions = {
        "plugin.json": plugin.get("version"),
        ".claude-plugin/plugin.json": claude_plugin.get("version"),
        ".claude-plugin/marketplace.json entry": (claude_entry or {}).get("version"),
    }
    if len(set(versions.values())) != 1 or None in versions.values():
        findings.append(f"manifest versions differ: {versions}")

    for label, deps in ((".claude-plugin/plugin.json", claude_plugin.get("dependencies", [])),
                        (".claude-plugin/marketplace.json entry", (claude_entry or {}).get("dependencies", []))):
        if DEPENDENCY not in deps:
            findings.append(f"{label}: missing dependency {DEPENDENCY}")
    if DEPENDENCY["marketplace"] not in claude_market.get("allowCrossMarketplaceDependenciesOn", []):
        findings.append(".claude-plugin/marketplace.json: allowCrossMarketplaceDependenciesOn must list cursor-plugins")

    version = plugin.get("version")
    changelog_path = ROOT / "CHANGELOG.md"
    if not changelog_path.exists():
        findings.append("CHANGELOG.md: missing")
        return
    changelog = changelog_path.read_text()
    if "## Unreleased" not in changelog and f"## [{version}]" not in changelog:
        findings.append(f"CHANGELOG.md: needs a '## Unreleased' or '## [{version}]' section")


def check_installer(findings: list[str]) -> None:
    text = (ROOT / "install.sh").read_text()
    if not re.search(r'^PSTACK_MIRROR_REF="[0-9a-f]{40}"$', text, re.M):
        findings.append("install.sh: PSTACK_MIRROR_REF must be a full 40-character commit")


def check_links(files: list[Path], findings: list[str]) -> None:
    link = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
    for path in files:
        if path.suffix != ".md":
            continue
        for target in link.findall(path.read_text()):
            if "://" in target or target.startswith("mailto:"):
                continue
            if not (path.parent / target).exists():
                findings.append(f"{path.relative_to(ROOT)}: broken link {target}")


def check_private_patterns(files: list[Path], findings: list[str]) -> None:
    patterns_file = ROOT / "private-patterns.txt"
    if not patterns_file.exists():
        return
    patterns = [p.strip() for p in patterns_file.read_text().splitlines() if p.strip() and not p.startswith("#")]
    for path in files:
        if path == patterns_file:
            continue
        try:
            text = path.read_text().lower()
        except (OSError, UnicodeDecodeError):
            continue
        for pattern in patterns:
            if pattern.lower() in text:
                findings.append(f"{path.relative_to(ROOT)}: matches a private pattern")
                break


def main() -> int:
    as_json = "--json" in sys.argv[1:]
    files = tracked_files()
    findings: list[str] = []
    check_ascii(files, findings)
    check_json_files(files, findings)
    check_manifests(findings)
    check_installer(findings)
    check_links(files, findings)
    check_private_patterns(files, findings)
    if as_json:
        print(json.dumps({"ok": not findings, "errors": findings}))
    else:
        for finding in findings:
            print(f"error: {finding}")
        print("ok" if not findings else f"{len(findings)} problem(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
