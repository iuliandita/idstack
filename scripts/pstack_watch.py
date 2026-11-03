#!/usr/bin/env python3
"""Track upstream pstack against what idstack documents, overlays, and installs.

  pstack_watch.py --check          offline: the lock agrees with README, install.sh, and overlays
  pstack_watch.py --report [FILE]  network: compare upstream and the mirror with the lock; exit 1 on drift
  pstack_watch.py --update-lock    network: rewrite config/pstack-lock.json and the README version

Environment: GITHUB_TOKEN or GH_TOKEN raises the GitHub API rate limit.
Exit codes: 0 in sync, 1 drift or failed check, 2 usage error, 3 network or upstream failure.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "config/pstack-lock.json"
README = ROOT / "README.md"
INSTALLER = ROOT / "install.sh"
OVERLAYS = ROOT / "skills/id-mode/playbooks"
UPSTREAM = "cursor/plugins"
UPSTREAM_PATH = "pstack"
MIRROR = "backnotprop/pstack"
ALWAYS_WATCHED = ("skills/poteto-mode/SKILL.md", "skills/setup-pstack/SKILL.md")
VERSION_RE = re.compile(r"as of pstack (\d+\.\d+\.\d+)")
OVERLAY_RE = re.compile(r"Read the shared playbook first: pstack `poteto-mode/playbooks/([a-z-]+)\.md`")


def http(url: str, api: bool = False) -> str:
    headers = {"User-Agent": "idstack-pstack-watch"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if api:
        headers["Accept"] = "application/vnd.github+json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as resp:
            return resp.read().decode()
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"error: cannot fetch {url}: {exc}; check the network and retry", file=sys.stderr)
        raise SystemExit(3) from exc


def api(path: str):
    return json.loads(http(f"https://api.github.com/{path}", api=True))


def raw(repo: str, ref: str, path: str) -> str:
    return http(f"https://raw.githubusercontent.com/{repo}/{ref}/{path}")


def readme_names(text: str) -> set[str]:
    """Names in README table rows whose Source column is pstack."""
    names = set()
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[1] == "pstack":
            names.add(cells[0].strip("`"))
    return names


def overlay_targets() -> set[str]:
    return {m for p in OVERLAYS.glob("*.md") for m in OVERLAY_RE.findall(p.read_text())}


def resolve(name: str, catalog: dict) -> str | None:
    """Upstream path (under pstack/) a README or overlay name refers to, if it exists."""
    if name in catalog["playbooks"]:
        return f"skills/poteto-mode/playbooks/{name}.md"
    for skill in (name, f"principle-{name}"):
        if skill in catalog["skills"]:
            return f"skills/{skill}/SKILL.md"
    if name in catalog["agents"]:
        return f"agents/{name}.md"
    return None


def used_names() -> set[str]:
    return readme_names(README.read_text()) | overlay_targets()


def watched_paths(catalog: dict) -> list[str]:
    paths = set(ALWAYS_WATCHED)
    paths.update(p for p in (resolve(n, catalog) for n in used_names()) if p)
    return sorted(paths)


def installer_ref() -> str:
    match = re.search(r'^PSTACK_MIRROR_REF="([0-9a-f]{40})"$', INSTALLER.read_text(), re.M)
    if not match:
        raise SystemExit("error: install.sh: PSTACK_MIRROR_REF must be a full 40-character commit; fix install.sh")
    return match.group(1)


def snapshot() -> dict:
    head = api(f"repos/{UPSTREAM}/commits/main")["sha"]
    tree = api(f"repos/{UPSTREAM}/git/trees/{head}:{UPSTREAM_PATH}?recursive=1")
    if tree.get("truncated"):
        print("error: upstream tree listing was truncated; list pstack/ by directory instead", file=sys.stderr)
        raise SystemExit(3)
    blobs = {e["path"]: e["sha"] for e in tree["tree"] if e["type"] == "blob"}
    return {
        "commit": head,
        "version": json.loads(raw(UPSTREAM, head, f"{UPSTREAM_PATH}/plugin.json"))["version"],
        "blobs": blobs,
        "catalog": {
            "skills": sorted({p.split("/")[1] for p in blobs if p.startswith("skills/") and p.count("/") >= 2}),
            "playbooks": sorted(
                p.rsplit("/", 1)[1][:-3] for p in blobs if re.fullmatch(r"skills/poteto-mode/playbooks/[^/]+\.md", p)
            ),
            "agents": sorted(p[7:-3] for p in blobs if re.fullmatch(r"agents/[^/]+\.md", p)),
        },
    }


def mirror_version(ref: str) -> str:
    return json.loads(raw(MIRROR, ref, "plugin.json"))["version"]


def build_lock(snap: dict) -> dict:
    ref = installer_ref()
    return {
        "upstream": {"repo": UPSTREAM, "path": UPSTREAM_PATH, "version": snap["version"], "commit": snap["commit"]},
        "mirror": {"repo": MIRROR, "ref": ref, "version": mirror_version(ref)},
        "catalog": snap["catalog"],
        "watched": {p: snap["blobs"][p] for p in watched_paths(snap["catalog"])},
    }


def check_offline(lock: dict) -> list[str]:
    findings = []
    version = VERSION_RE.search(README.read_text())
    if not version or version.group(1) != lock["upstream"]["version"]:
        want = lock["upstream"]["version"]
        findings.append(f"README.md: 'as of pstack X' must say {want}; run scripts/pstack_watch.py --update-lock")
    if installer_ref() != lock["mirror"]["ref"]:
        findings.append("install.sh: PSTACK_MIRROR_REF differs from config/pstack-lock.json; run --update-lock")
    for name in sorted(used_names()):
        if resolve(name, lock["catalog"]) is None:
            findings.append(f"pstack {name} is named in README.md or an overlay but is not in the lock catalog")
    if sorted(lock["watched"]) != watched_paths(lock["catalog"]):
        findings.append("config/pstack-lock.json: watched files differ from what idstack uses; run --update-lock")
    return findings


def flatten(catalog: dict) -> set[str]:
    return {f"{kind}/{name}" for kind, items in catalog.items() for name in items}


def compare(lock: dict, snap: dict, mirror_head: str, names: set[str]) -> dict:
    """Differences between the lock and live upstream. Empty lists and None mean in sync."""
    old, new = flatten(lock["catalog"]), flatten(snap["catalog"])
    changed = []
    for path, sha in lock["watched"].items():
        now = snap["blobs"].get(path)
        if now != sha:
            changed.append((path, "removed" if now is None else "changed"))
    return {
        "version": None
        if snap["version"] == lock["upstream"]["version"]
        else (lock["upstream"]["version"], snap["version"]),
        "missing": sorted(n for n in names if resolve(n, snap["catalog"]) is None),
        "added": sorted(new - old),
        "dropped": sorted(old - new),
        "changed": changed,
        "mirror": None if mirror_head == lock["mirror"]["version"] else (lock["mirror"]["version"], mirror_head),
    }


def render(lock: dict, snap: dict, diff: dict) -> str:
    moved = snap["commit"] != lock["upstream"]["commit"]
    out = [f"idstack tracks pstack {lock['upstream']['version']} ({lock['upstream']['commit'][:7]}).", ""]
    if moved:
        out.insert(1, f"Upstream is now at {snap['version']} ({snap['commit'][:7]}).")
    if diff["version"]:
        out.append(f"- Version: {diff['version'][0]} -> {diff['version'][1]}.")
    for name in diff["missing"]:
        out.append(f"- BREAKING: `{name}` is named in README.md or an overlay and no longer exists upstream.")
    for path, how in diff["changed"]:
        out.append(f"- Watched file {how}: `{path}`.")
    if diff["added"]:
        out.append("- New upstream: " + ", ".join(f"`{n}`" for n in diff["added"]) + ".")
    if diff["dropped"]:
        out.append("- Gone upstream: " + ", ".join(f"`{n}`" for n in diff["dropped"]) + ".")
    if diff["mirror"]:
        out.append(
            f"- The mirror's latest is pstack {diff['mirror'][1]}; PSTACK_MIRROR_REF is on {diff['mirror'][0]}. "
            "Codex and OpenCode install the pinned one."
        )
    steps = []
    if moved:
        compare_url = f"https://github.com/{UPSTREAM}/compare/{lock['upstream']['commit']}...{snap['commit']}"
        out += ["", f"Upstream changes since the lock: {compare_url}"]
        steps.append(
            "Read the changes and update the README.md tables, the overlays in skills/id-mode/playbooks, and docs."
        )
    if diff["mirror"]:
        steps.append(
            "To move the mirror pin, run the sandbox install from CONTRIBUTING.md against the new commit, "
            "then edit PSTACK_MIRROR_REF."
        )
    steps += [
        "Run `python3 scripts/pstack_watch.py --update-lock`, then `python3 scripts/check.py`.",
        "Open a PR into `develop` and close this issue.",
    ]
    out += ["", "To reflect this:", ""] + [f"{i}. {s}" for i, s in enumerate(steps, 1)]
    return "\n".join(out) + "\n"


def drifted(diff: dict) -> bool:
    return any(diff[k] for k in diff)


def main(argv: list[str]) -> int:
    mode = argv[0] if argv else ""
    if mode == "--update-lock":
        snap = snapshot()
        LOCK.write_text(json.dumps(build_lock(snap), indent=2) + "\n")
        text = VERSION_RE.sub(f"as of pstack {snap['version']}", README.read_text())
        README.write_text(text)
        print(f"wrote {LOCK.relative_to(ROOT)} at pstack {snap['version']} ({snap['commit'][:7]})")
        return 0
    if not LOCK.exists():
        print("error: config/pstack-lock.json is missing; run scripts/pstack_watch.py --update-lock", file=sys.stderr)
        return 1
    lock = json.loads(LOCK.read_text())
    if mode == "--check":
        findings = check_offline(lock)
        for finding in findings:
            print(f"error: {finding}", file=sys.stderr)
        print("ok" if not findings else f"{len(findings)} problem(s)")
        return 1 if findings else 0
    if mode == "--report":
        snap = snapshot()
        diff = compare(lock, snap, mirror_version("main"), used_names())
        if not drifted(diff):
            print(f"in sync with pstack {snap['version']} ({snap['commit'][:7]})")
            return 0
        body = render(lock, snap, diff)
        if len(argv) > 1:
            Path(argv[1]).write_text(body)
        else:
            print(body, end="")
        return 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
