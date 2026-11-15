import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import check  # noqa: E402
import pstack_watch as pw  # noqa: E402

CATALOG = {
    "skills": ["poteto-mode", "principle-fix-root-causes"],
    "playbooks": ["bug-fix", "shipping"],
    "agents": ["poteto-agent"],
}
LOCK = {
    "upstream": {"version": "1.0.0", "commit": "a" * 40},
    "mirror": {"version": "1.0.0"},
    "catalog": CATALOG,
    "watched": {"skills/poteto-mode/playbooks/bug-fix.md": "sha1"},
}
PIN = "b" * 40
README_TEXT = "Tables as of pstack 1.0.0.\n\n| `bug-fix` | pstack | overlay |\n"
OVERLAY_TEXT = "Read the shared playbook first: pstack `poteto-mode/playbooks/shipping.md`\n"
WATCHED = [
    "skills/poteto-mode/SKILL.md",
    "skills/poteto-mode/playbooks/bug-fix.md",
    "skills/poteto-mode/playbooks/shipping.md",
    "skills/setup-pstack/SKILL.md",
]
FULL_LOCK = {
    "upstream": {"version": "1.0.0", "commit": "a" * 40},
    "mirror": {"ref": PIN, "version": "1.0.0"},
    "catalog": CATALOG,
    "watched": dict.fromkeys(WATCHED, "sha1"),
}


def snap(**over):
    base = {
        "version": "1.0.0",
        "commit": "a" * 40,
        "catalog": CATALOG,
        "blobs": {"skills/poteto-mode/playbooks/bug-fix.md": "sha1"},
    }
    return {**base, **over}


class ReadmeNames(unittest.TestCase):
    def test_only_pstack_rows_count(self):
        text = "| `poteto-mode` | pstack | x |\n| **id-mode** | **idstack** | y |\n| bug-fix | pstack | overlay |\n"
        self.assertEqual(pw.readme_names(text), {"poteto-mode", "bug-fix"})


class Compare(unittest.TestCase):
    def test_in_sync(self):
        diff = pw.compare(LOCK, snap(), "1.0.0", {"bug-fix", "fix-root-causes", "poteto-agent"})
        self.assertFalse(pw.drifted(diff))

    def test_each_drift_is_reported(self):
        gone = {**CATALOG, "playbooks": ["shipping"]}
        cases = {
            "version": (snap(version="1.1.0"), "1.0.0", set(), lambda d: d["version"] == ("1.0.0", "1.1.0")),
            "removed name": (snap(catalog=gone), "1.0.0", {"bug-fix"}, lambda d: d["missing"] == ["bug-fix"]),
            "changed file": (
                snap(blobs={"skills/poteto-mode/playbooks/bug-fix.md": "sha2"}),
                "1.0.0",
                set(),
                lambda d: d["changed"] == [("skills/poteto-mode/playbooks/bug-fix.md", "changed")],
            ),
            "new playbook": (
                snap(catalog={**CATALOG, "playbooks": ["bug-fix", "shipping", "eval"]}),
                "1.0.0",
                set(),
                lambda d: d["added"] == ["playbooks/eval"],
            ),
            "mirror ahead of pin": (snap(), "1.1.0", set(), lambda d: d["mirror"] == ("1.0.0", "1.1.0")),
        }
        for label, (s, mirror_head, names, expect) in cases.items():
            with self.subTest(label):
                diff = pw.compare(LOCK, s, mirror_head, names)
                self.assertTrue(pw.drifted(diff))
                self.assertTrue(expect(diff), diff)

    def test_resolve_finds_principles_and_agents(self):
        self.assertEqual(pw.resolve("fix-root-causes", CATALOG), "skills/principle-fix-root-causes/SKILL.md")
        self.assertEqual(pw.resolve("poteto-agent", CATALOG), "agents/poteto-agent.md")
        self.assertIsNone(pw.resolve("nope", CATALOG))


class Repo(unittest.TestCase):
    """A throwaway README, install.sh, overlay directory, and lock path in place of the real ones."""

    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.readme = self.dir / "README.md"
        self.installer = self.dir / "install.sh"
        self.lock = self.dir / "pstack-lock.json"
        overlays = self.dir / "playbooks"
        overlays.mkdir()
        (overlays / "shipping.md").write_text(OVERLAY_TEXT)
        self.readme.write_text(README_TEXT)
        self.installer.write_text(f'PSTACK_MIRROR_REF="{PIN}"\n')
        self.lock.write_text(json.dumps(FULL_LOCK))
        for name, value in (
            ("README", self.readme),
            ("INSTALLER", self.installer),
            ("OVERLAYS", overlays),
            ("LOCK", self.lock),
        ):
            self.enterContext(mock.patch.object(pw, name, value))

    def run_main(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            return pw.main(list(argv)), err.getvalue()


class InstallerRef(Repo):
    def test_only_a_full_commit_is_a_pin(self):
        cases = {PIN: PIN, "b" * 39: None, "b" * 41: None, "B" * 40: None, "main": None}
        for value, want in cases.items():
            with self.subTest(value):
                self.installer.write_text(f'set -eu\nPSTACK_MIRROR_REF="{value}"\n')
                self.assertEqual(pw.installer_ref(), want)


class WatchedPaths(Repo):
    def test_readme_rows_overlays_and_the_fixed_files(self):
        self.assertEqual(pw.watched_paths(CATALOG), WATCHED)

    def test_names_upstream_lacks_are_left_out(self):
        self.readme.write_text(README_TEXT + "| `gone` | pstack | x |\n")
        self.assertEqual(pw.watched_paths(CATALOG), WATCHED)


class CheckOffline(Repo):
    def test_in_sync(self):
        self.assertEqual(pw.check_offline(FULL_LOCK), [])

    def test_each_finding(self):
        def readme(text):
            return lambda: self.readme.write_text(text)

        def pin(value):
            return lambda: self.installer.write_text(f'PSTACK_MIRROR_REF="{value}"\n')

        cases = {
            "readme version": (readme(README_TEXT.replace("1.0.0", "0.9.0")), FULL_LOCK, "README.md: 'as of pstack X'"),
            "readme phrase gone": (readme("| `bug-fix` | pstack | x |\n"), FULL_LOCK, "README.md: 'as of pstack X'"),
            "pin differs": (pin("c" * 40), FULL_LOCK, "PSTACK_MIRROR_REF differs"),
            "pin too short": (pin("b" * 39), FULL_LOCK, pw.PIN_FINDING),
            "pin too short, no lock": (pin("b" * 39), None, pw.PIN_FINDING),
            "unknown name": (readme(README_TEXT + "| `gone` | pstack | x |\n"), FULL_LOCK, "pstack gone is named"),
            "watched differ": (lambda: None, {**FULL_LOCK, "watched": {}}, "watched files differ"),
        }
        for label, (arrange, lock, want) in cases.items():
            with self.subTest(label):
                self.setUp()
                arrange()
                findings = pw.check_offline(lock)
                self.assertEqual(len(findings), 1, findings)
                self.assertIn(want, findings[0])


class ReadLock(Repo):
    def test_usable_lock(self):
        self.assertEqual(pw.read_lock(), (FULL_LOCK, None))

    def test_each_unusable_lock_is_a_problem(self):
        cases = {
            "missing": (None, "missing"),
            "unparsable": ("{", "invalid JSON"),
            "not an object": ("[]", "the top level"),
            "no mirror ref": (json.dumps({**FULL_LOCK, "mirror": {"version": "1.0.0"}}), "mirror.ref"),
            "no catalog": (json.dumps({k: v for k, v in FULL_LOCK.items() if k != "catalog"}), "catalog.skills"),
            "watched is a list": (json.dumps({**FULL_LOCK, "watched": []}), "watched"),
        }
        for label, (text, want) in cases.items():
            with self.subTest(label):
                if text is None:
                    self.lock.unlink()
                else:
                    self.lock.write_text(text)
                lock, problem = pw.read_lock()
                self.assertIsNone(lock)
                self.assertIn(want, problem)
                self.assertIn("--update-lock", problem)

    def test_report_exits_4_and_check_exits_1(self):
        self.lock.write_text("{")
        with mock.patch.object(pw, "http", side_effect=AssertionError("network")):
            self.assertEqual(self.run_main("--report")[0], pw.EXIT_NO_LOCK)
            self.assertEqual(self.run_main("--check")[0], 1)
            self.assertEqual(self.run_main("--bogus")[0], 2)


class BuildLock(Repo):
    def blobs(self):
        return dict.fromkeys(WATCHED, "sha9")

    def test_lock_from_a_snapshot(self):
        with mock.patch.object(pw, "mirror_version", return_value="1.0.1") as mirror:
            lock = pw.build_lock(snap(blobs=self.blobs()))
        mirror.assert_called_once_with(PIN)
        self.assertEqual(lock["mirror"], {"repo": pw.MIRROR, "ref": PIN, "version": "1.0.1"})
        self.assertEqual(lock["watched"], self.blobs())
        self.assertIsNone(pw.lock_gap(lock))

    def test_refuses_what_it_cannot_lock(self):
        blobs = self.blobs()
        del blobs["skills/setup-pstack/SKILL.md"]
        cases = {
            "watched file absent upstream": (PIN, blobs, "upstream has no skills/setup-pstack/SKILL.md"),
            "bad pin": ("b" * 39, self.blobs(), pw.PIN_FINDING),
        }
        for label, (pin, upstream, want) in cases.items():
            with self.subTest(label), mock.patch.object(pw, "mirror_version", return_value="1.0.0"):
                self.installer.write_text(f'PSTACK_MIRROR_REF="{pin}"\n')
                with self.assertRaisesRegex(pw.WatchError, want):
                    pw.build_lock(snap(blobs=upstream))


class UpdateLock(Repo):
    def update(self, blobs):
        with (
            mock.patch.object(pw, "snapshot", return_value=snap(version="1.2.0", blobs=blobs)),
            mock.patch.object(pw, "mirror_version", return_value="1.0.0"),
        ):
            return self.run_main("--update-lock")

    def test_writes_the_lock_and_the_readme_version(self):
        rc, _ = self.update(dict.fromkeys(WATCHED, "sha9"))
        self.assertEqual(rc, 0)
        self.assertIn("as of pstack 1.2.0", self.readme.read_text())
        self.assertEqual(json.loads(self.lock.read_text())["upstream"]["version"], "1.2.0")

    def test_failures_exit_1_and_write_nothing(self):
        cases = {
            "absent upstream": (README_TEXT, {}, "upstream has no"),
            "readme lacks the phrase": (
                "| `bug-fix` | pstack | x |\n",
                dict.fromkeys(WATCHED, "sha9"),
                "README.md: no",
            ),
        }
        for label, (readme, blobs, want) in cases.items():
            with self.subTest(label):
                self.readme.write_text(readme)
                rc, err = self.update(blobs)
                self.assertEqual(rc, 1)
                self.assertIn(want, err)
                self.assertEqual(self.readme.read_text(), readme)
                self.assertEqual(json.loads(self.lock.read_text()), FULL_LOCK)


class Render(unittest.TestCase):
    def test_every_kind_of_drift_is_a_line(self):
        s = snap(version="1.1.0", commit="c" * 40)
        diff = {
            "version": ("1.0.0", "1.1.0"),
            "missing": ["bug-fix"],
            "added": ["playbooks/eval"],
            "dropped": ["agents/old"],
            "changed": [("skills/poteto-mode/SKILL.md", "changed")],
            "mirror": ("1.0.0", "1.1.0"),
        }
        body = pw.render(LOCK, s, diff)
        for want in (
            "idstack tracks pstack 1.0.0 (aaaaaaa).",
            "Upstream is now at 1.1.0 (ccccccc).",
            "- Version: 1.0.0 -> 1.1.0.",
            "- BREAKING: `bug-fix`",
            "- Watched file changed: `skills/poteto-mode/SKILL.md`.",
            "- New upstream: `playbooks/eval`.",
            "- Gone upstream: `agents/old`.",
            "- The mirror's latest is pstack 1.1.0; PSTACK_MIRROR_REF is on 1.0.0.",
            f"compare/{'a' * 40}...{'c' * 40}",
            "then edit PSTACK_MIRROR_REF.",
            "4. Open a PR into `develop`",
        ):
            with self.subTest(want):
                self.assertIn(want, body)

    def test_mirror_only_drift_has_no_upstream_lines(self):
        empty = {"version": None, "missing": [], "added": [], "dropped": [], "changed": []}
        body = pw.render(LOCK, snap(), {**empty, "mirror": ("1.0.0", "1.1.0")})
        self.assertNotIn("Upstream is now at", body)
        self.assertNotIn("compare/", body)
        self.assertIn("3. Open a PR into `develop`", body)


class UpstreamStrings(unittest.TestCase):
    def snapshot(self, version, path="agents/poteto-agent.md"):
        tree = {"tree": [{"path": path, "sha": "s", "type": "blob"}]}
        with (
            mock.patch.object(pw, "api", side_effect=[{"sha": "a" * 40}, tree]),
            mock.patch.object(pw, "raw", return_value=json.dumps({"version": version})),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            return pw.snapshot()

    def test_plain_version_and_names_pass(self):
        self.assertEqual(self.snapshot("1.2.3")["catalog"]["agents"], ["poteto-agent"])

    def test_anything_else_is_an_upstream_failure(self):
        cases = {
            "markdown in version": ("1.2.3 [x](http://example.com)", "agents/poteto-agent.md"),
            "newline in version": ("1.2.3\n@someone", "agents/poteto-agent.md"),
            "version not a string": (None, "agents/poteto-agent.md"),
            "markup in a name": ("1.2.3", "agents/a`b @c.md"),
        }
        for label, (version, path) in cases.items():
            with self.subTest(label), self.assertRaises(SystemExit) as caught:
                self.snapshot(version, path)
            self.assertEqual(caught.exception.code, 3)


class RepoCheck(Repo):
    def test_a_39_hex_pin_is_one_finding_not_a_crash(self):
        self.installer.write_text(f'PSTACK_MIRROR_REF="{"b" * 39}"\n')
        findings: list[str] = []
        check.check_pstack(findings)
        self.assertEqual(findings, [pw.PIN_FINDING])

    def test_a_broken_lock_is_a_finding_beside_the_pin(self):
        self.installer.write_text(f'PSTACK_MIRROR_REF="{"b" * 39}"\n')
        self.lock.write_text('{"upstream": {}}')
        findings: list[str] = []
        check.check_pstack(findings)
        self.assertEqual(len(findings), 2, findings)
        self.assertIn("upstream.version is missing or malformed", findings[0])

    def test_changelog_needs_the_manifest_version(self):
        cases = {
            "released section": ("## [Unreleased]\n\n## [1.2.0] - 2026-01-01\n", "1.2.0", 0),
            "unreleased only": ("## [Unreleased]\n\n## [1.1.0] - 2026-01-01\n", "1.2.0", 1),
            "version only in prose": ("## [Unreleased]\n\nsee [1.2.0]\n", "1.2.0", 1),
            "prefix of another version": ("## [1.2.01]\n", "1.2.0", 1),
        }
        for label, (text, version, count) in cases.items():
            with self.subTest(label), mock.patch.object(check, "ROOT", self.dir):
                (self.dir / "CHANGELOG.md").write_text(text)
                findings: list[str] = []
                check.check_changelog(version, findings)
                self.assertEqual(len(findings), count, findings)

    def test_ascii_check_covers_js_and_jsonc(self):
        for name in ("server.js", "config.jsonc"):
            with self.subTest(name), mock.patch.object(check, "ROOT", self.dir):
                path = self.dir / name
                path.write_text("// caf\u00e9\n", encoding="utf-8")
                findings: list[str] = []
                check.check_ascii([path], findings)
                self.assertEqual(findings, [f"{name}:1: non-ASCII character"])

    def test_unknown_argument_is_a_usage_error(self):
        for argv in (["--bogus"], ["--json", "--bogus"]):
            with self.subTest(argv):
                done = subprocess.run(
                    [sys.executable, str(SCRIPTS / "check.py"), *argv], capture_output=True, text=True
                )
                self.assertEqual(done.returncode, 2)
                self.assertIn("unknown argument --bogus", done.stderr)
                if "--json" in argv:
                    self.assertFalse(json.loads(done.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
