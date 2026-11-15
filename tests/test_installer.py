import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ["bash", str(ROOT / "install.sh"), "--harness", "opencode", "--no-models", "--json"]
GIT = ["git", "-c", "user.name=test", "-c", "user.email=test"]
GUARD_ENTRY = '{"plugins": [{"package": "/somewhere/harness/opencode/guard"}]}\n'
PIN = re.search(r'^PSTACK_MIRROR_REF="([0-9a-f]{40})"$', (ROOT / "install.sh").read_text(), re.M).group(1)
MODELS = [sys.executable, "-I", str(ROOT / "scripts/pstack_models.py"), "--target", "agents"]
# Stands in for the network: "fetch" drops a fixture mirror into the work tree git was pointed at.
GIT_SHIM = """#!/bin/sh
case "$3" in
  fetch) [ -z "$SHIM_FAIL" ] && cp -R "$SHIM_MIRROR/skills" "$2/skills" ;;
  init|checkout) ;;
  *) exec "$SHIM_GIT" "$@" ;;
esac
"""


def old_bash() -> str | None:
    """Path of a bash older than 4.4, when the host has one."""
    for exe in {shutil.which("bash"), "/bin/bash"}:
        if not exe or not Path(exe).exists():
            continue
        probe = subprocess.run(
            [exe, "-c", 'echo "${BASH_VERSINFO[0]} ${BASH_VERSINFO[1]}"'], capture_output=True, text=True
        )
        if probe.returncode == 0 and tuple(map(int, probe.stdout.split())) < (4, 4):
            return exe
    return None


@unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "bash and git needed")
class InstallerTest(unittest.TestCase):
    def sandbox(self) -> tuple[Path, dict[str, str]]:
        """A throwaway root with every installer path pointed into it, and pstack marked as present."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        r = Path(tmp.name).resolve()
        env = {
            **os.environ,
            "HOME": str(r / "home"),
            "XDG_CONFIG_HOME": str(r / "config"),
            "XDG_DATA_HOME": str(r / "data"),
            "XDG_STATE_HOME": str(r / "state"),
            "CLAUDE_CONFIG_DIR": str(r / "claude"),
            "CODEX_HOME": str(r / "codex"),
            "AGENTS_SKILLS_DIR": str(r / "agents/skills"),
            "OPENCODE_SKILLS_DIR": str(r / "opencode/skills"),
            "OPENCODE_AGENTS_DIR": str(r / "opencode/agents"),
            "IDSTACK_CACHE_DIR": str(r / "cache"),
            "IDSTACK_BIN_DIR": str(r / "bin"),
            "IDSTACK_CONFIG_DIR": str(r / "idstack-config"),
            "IDSTACK_STATE_DIR": str(r / "idstack-state"),
        }
        (r / "home").mkdir()
        # The mirror is on the network; a pstack the script did not install is left alone.
        (r / "agents/skills/poteto-mode").mkdir(parents=True)
        (r / "agents/skills/poteto-mode/SKILL.md").write_text("stub\n")
        return r, env

    def install(
        self, env: dict[str, str], rc: int, *args: str, argv: list[str] | None = None, cwd: Path | None = None
    ) -> dict:
        r = subprocess.run(
            [*(argv or INSTALL), *args], capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL, cwd=cwd
        )
        self.assertEqual(r.returncode, rc, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual(d["ok"], rc == 0, d)
        self.assertEqual(bool(d["errors"]), rc != 0, d)
        self.assertEqual(d["exit_code"], rc, d)
        return d

    def git(self, env: dict[str, str], repo: Path, *args: str) -> str:
        return subprocess.run(
            [*GIT, "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env
        ).stdout.strip()

    def shim(self, r: Path, env: dict[str, str], name: str, text: str) -> None:
        """Put an executable called `name` first on PATH."""
        exe = r / "shim" / name
        exe.parent.mkdir(exist_ok=True)
        exe.write_text(text)
        exe.chmod(0o755)
        if not env["PATH"].startswith(str(exe.parent)):
            env["PATH"] = f"{exe.parent}{os.pathsep}{env['PATH']}"

    def mirror(self, r: Path, env: dict[str, str]) -> Path:
        """A local pstack mirror the git shim serves, in place of the pinned commit on the network."""
        skills = r / "mirror/skills"
        for name in ("poteto-mode", "arena"):
            (skills / name).mkdir(parents=True)
            (skills / name / "SKILL.md").write_text(f"{name} from the mirror\n")
        env.update(SHIM_MIRROR=str(r / "mirror"), SHIM_GIT=shutil.which("git"))
        self.shim(r, env, "git", GIT_SHIM)
        return r / "agents/skills"

    def test_interrupted_pstack_copy_is_redone(self):
        r, env = self.sandbox()
        skills = self.mirror(r, env)
        manifest = skills / ".pstack-install.json"
        # What a run killed between two renames leaves: names but no commit, one skill half-written.
        manifest.write_text(json.dumps({"source": "x", "skills": ["poteto-mode", "retired"]}))
        (skills / "retired").mkdir()
        (skills / ".pstack-stage.dead").mkdir()
        local = ["--source", str(ROOT)]

        d = self.install(env, 1, *local, "--check")
        self.assertIn("incomplete", [c["state"] for c in d["components"]])
        self.install(env, 0, *local)
        self.assertEqual(json.loads(manifest.read_text())["commit"], PIN)
        self.assertEqual(json.loads(manifest.read_text())["skills"], ["arena", "poteto-mode"])
        self.assertEqual((skills / "poteto-mode/SKILL.md").read_text(), "poteto-mode from the mirror\n")
        self.assertEqual(sorted(p.name for p in skills.iterdir()), [".pstack-install.json", "arena", "poteto-mode"])

        with self.subTest("a deleted skill folder is reported and restored"):
            shutil.rmtree(skills / "arena")
            d = self.install(env, 1, *local, "--check")
            self.assertIn("broken (1 missing)", [c["state"] for c in d["components"]])
            self.install(env, 0, *local)
            self.assertTrue((skills / "arena/SKILL.md").is_file())

    def test_pstack_copy_failures(self):
        with self.subTest("a manifest name that is not a folder name is refused before any delete"):
            r, env = self.sandbox()
            skills = self.mirror(r, env)
            (r / "agents/victim").mkdir()
            (r / "agents/victim/keep").write_text("mine\n")
            for bad in ("../victim", "/etc", ".", "a/b"):
                (skills / ".pstack-install.json").write_text(json.dumps({"commit": "old", "skills": [bad]}))
                d = self.install(env, 1, "--source", str(ROOT))
                self.assertIn(f"'{bad}'", d["errors"][0])
            self.assertEqual((r / "agents/victim/keep").read_text(), "mine\n")
            self.assertEqual((skills / "poteto-mode/SKILL.md").read_text(), "stub\n", "nothing was copied")

        with self.subTest("a failed fetch is an error with exit 1, and leaves the skills dir alone"):
            r, env = self.sandbox()
            skills = self.mirror(r, env)
            shutil.rmtree(skills / "poteto-mode")
            d = self.install({**env, "SHIM_FAIL": "1"}, 1, "--source", str(ROOT))
            self.assertIn("could not fetch", d["errors"][0])
            self.assertEqual(list(skills.iterdir()), [])

    def test_source_is_local_only_as_a_path(self):
        r, env = self.sandbox()
        (r / "cwd/iuliandita/idstack").mkdir(parents=True)
        (r / "cwd/checkout").mkdir()
        # (case, --source, exit code, the source the run reports)
        cases = [
            ("the default is a repo even when a folder has its name", None, 0, "iuliandita/idstack"),
            ("owner/repo beside a folder of that name", "iuliandita/idstack", 0, "iuliandita/idstack"),
            ("a path", "./checkout", 0, str(r / "cwd/checkout")),
            ("a mistyped path is not a repo", "./chekout", 2, None),
            ("a bare folder name", "checkout", 2, None),
            ("an option", "--upload-pack=x", 2, None),
        ]
        for case, source, rc, want in cases:
            with self.subTest(case):
                args = ["--source", source] if source else []
                d = self.install(env, rc, *args, "--dry-run", cwd=r / "cwd")
                if want:
                    self.assertEqual(d["source"], want)
        self.assertFalse((r / "cache").exists(), "--dry-run must not clone")

    def test_links_follow_the_source(self):
        r, env = self.sandbox()
        src, skills = r / "src", r / "opencode/skills"
        for path in ("skills/a/SKILL.md", "skills/b/SKILL.md", "harness/opencode/agents/x.md", "bin/idstack"):
            (src / path).parent.mkdir(parents=True, exist_ok=True)
            (src / path).write_text("#!/bin/sh\n")
        (src / "bin/idstack").chmod(0o755)
        local = ["--source", str(src)]
        self.install(env, 0, *local)
        self.install(env, 0, *local, "--check")

        (src / "skills/c").mkdir()
        (src / "harness/opencode/agents/y.md").write_text("new\n")
        d = self.install(env, 1, *local, "--check")
        self.assertEqual([c["state"] for c in d["components"]].count("outdated"), 2, d["components"])

        shutil.rmtree(src / "skills/b")
        self.install(env, 0, *local)
        self.assertEqual(sorted(p.name for p in skills.iterdir()), [".idstack-install.json", "a", "c"])
        self.assertEqual(json.loads((skills / ".idstack-install.json").read_text())["skills"], ["a", "c"])
        self.install(env, 0, *local, "--check")

        with self.subTest("a CLI link that is not idstack's"):
            (r / "bin/idstack").unlink()
            (r / "bin/idstack").write_text("mine\n")
            d = self.install(env, 1, *local, "--check")
            self.assertIn("foreign", [c["state"] for c in d["components"]])

    def test_single_harness_uninstall(self):
        r, env = self.sandbox()
        local = ["--source", str(ROOT)]
        self.install(env, 0, *local)
        # What a Codex install leaves behind, without the Codex CLI.
        agents = r / "codex/agents"
        agents.mkdir(parents=True)
        (agents / "plan-reader.toml").symlink_to(ROOT / "harness/codex/agents/plan-reader.toml")
        (agents / ".idstack-install.json").write_text(
            json.dumps({"source": str(ROOT / "harness/codex/agents"), "files": ["plan-reader.toml"]})
        )
        # No harness CLI on PATH: only what the script needs.
        tools = r / "tools"
        tools.mkdir()
        for name in ("bash", "git", "python3", "rm", "readlink", "basename", "dirname", "grep", "cat", "head"):
            if not shutil.which(name):
                self.skipTest(f"{name} is not on PATH")
            (tools / name).symlink_to(shutil.which(name))
        env["PATH"] = str(tools)

        with self.subTest("the CLI link stays while another harness has idstack"):
            self.install(env, 0, *local, "--uninstall")
            self.assertTrue((r / "bin/idstack").is_symlink())
            self.assertFalse((r / "opencode/skills/.idstack-install.json").exists())

        with self.subTest("a harness whose CLI is gone still loses its links"):
            argv = [a if a != "opencode" else "codex" for a in INSTALL]
            d = self.install(env, 0, *local, "--uninstall", argv=argv)
            self.assertIn("codex is not on PATH", d["warnings"][0])
            self.assertEqual(list(agents.iterdir()), [])
            self.assertFalse((r / "bin/idstack").is_symlink(), "nothing uses the CLI link any more")

    def test_failing_harness_cli(self):
        r, env = self.sandbox()
        self.shim(r, env, "claude", "#!/bin/sh\necho broken >&2\nexit 7\n")
        argv = [a if a != "opencode" else "claude" for a in INSTALL]
        local = ["--source", str(ROOT)]
        d = self.install(env, 1, *local, "--check", argv=argv)
        self.assertEqual([c["state"] for c in d["components"][:2]], ["unknown", "unknown"])
        d = self.install(env, 1, *local, argv=argv)
        self.assertIn("command failed: claude plugin", d["errors"][0])

    def test_one_mode_flag(self):
        r, env = self.sandbox()
        (r / "bin").mkdir()
        (r / "bin/idstack").symlink_to(ROOT / "bin/idstack")
        for flags in (
            ["--dry-run", "--uninstall"],
            ["--check", "--uninstall"],
            ["--uninstall", "--check"],
            ["--check", "--dry-run"],
        ):
            with self.subTest(flags=flags):
                d = self.install(env, 2, "--source", str(ROOT), *flags)
                self.assertTrue(all(f in d["errors"][0] for f in flags), d)
                self.assertTrue((r / "bin/idstack").is_symlink(), "a usage error must not uninstall")
        with self.subTest(flags="repeated"):
            self.install(env, 0, "--source", str(ROOT), "--dry-run", "--dry-run")

    def test_ref_is_checked_out_on_every_run(self):
        r, env = self.sandbox()
        origin, cache = r / "origin", r / "cache/src"
        try:
            subprocess.run(["git", "clone", "-q", str(ROOT), str(origin)], check=True, capture_output=True, env=env)
        except subprocess.CalledProcessError as e:
            self.skipTest(f"cannot clone the worktree: {e.stderr.decode().strip()}")
        self.git(env, origin, "checkout", "-q", "-b", "installer-test")
        self.git(env, origin, "tag", "installer-test-pin")
        pinned = self.git(env, origin, "rev-parse", "HEAD")
        source = ["--source", origin.as_uri()]

        with self.subTest("tag pin survives a second run"):
            self.install(env, 0, *source, "--ref", "installer-test-pin")
            self.git(env, origin, "commit", "-q", "--allow-empty", "-m", "later")
            self.install(env, 0, *source, "--ref", "installer-test-pin")
            self.assertEqual(self.git(env, cache, "rev-parse", "HEAD"), pinned)
            self.assertEqual(self.git(env, cache, "branch", "--show-current"), "", "a tag is a detached checkout")
            self.assertTrue((r / "bin/idstack").resolve().is_file())

        with self.subTest("branch fast-forwards"):
            self.install(env, 0, *source, "--ref", "installer-test")
            self.git(env, origin, "commit", "-q", "--allow-empty", "-m", "newest")
            self.install(env, 0, *source, "--ref", "installer-test")
            self.assertEqual(self.git(env, cache, "rev-parse", "HEAD"), self.git(env, origin, "rev-parse", "HEAD"))
            self.assertEqual(self.git(env, cache, "branch", "--show-current"), "installer-test")

        with self.subTest("unknown ref is reported"):
            d = self.install(env, 1, *source, "--ref", "no-such-ref")
            self.assertIn("no-such-ref", d["errors"][0])

    def test_uninstall_guard_hook(self):
        # (case, config file, its text, break the CLI link, exit code, link survives)
        cases = [
            ("no hook in opencode.jsonc", "opencode.jsonc", "// mine\n{}\n", False, 0, False),
            ("hook in opencode.jsonc cannot be removed", "opencode.jsonc", "// mine\n" + GUARD_ENTRY, False, 1, True),
            ("hook in opencode.json", "opencode.json", GUARD_ENTRY, False, 0, False),
            ("dangling link, no hook", "opencode.jsonc", "{}\n", True, 0, False),
            ("dangling link, hook removed by this checkout", "opencode.json", GUARD_ENTRY, True, 0, False),
            ("dangling link, hook cannot be removed", "opencode.jsonc", GUARD_ENTRY, True, 1, False),
        ]
        for case, name, text, dangling, rc, kept in cases:
            with self.subTest(case):
                r, env = self.sandbox()
                self.install(env, 0, "--source", str(ROOT))
                link, config = r / "bin/idstack", r / "config/opencode" / name
                config.parent.mkdir(parents=True)
                config.write_text(text)
                if dangling:
                    link.unlink()
                    link.symlink_to(r / "gone/bin/idstack")
                d = self.install(env, rc, "--source", str(ROOT), "--uninstall")
                self.assertEqual(link.is_symlink(), kept)
                self.assertFalse((r / "opencode/skills/.idstack-install.json").exists(), "the rest still runs")
                self.assertFalse((r / "opencode/agents/.idstack-install.json").exists(), "the rest still runs")
                if rc:
                    self.assertIn(str(config), d["errors"][0])
                    self.assertEqual(config.read_text(), text)
                else:
                    self.assertNotIn("harness/opencode/guard", config.read_text())

    def test_old_python_exits_3(self):
        r, env = self.sandbox()
        shim = r / "shim/python3"
        shim.parent.mkdir()
        shim.write_text("#!/bin/sh\nexit 1\n")  # what `sys.exit(version_info < (3, 11))` does on an old Python
        shim.chmod(0o755)
        env["PATH"] = f"{shim.parent}{os.pathsep}{env['PATH']}"
        d = self.install(env, 3, "--source", str(ROOT))
        self.assertIn("3.11", d["errors"][0])
        self.assertFalse((r / "bin").exists())

    def test_old_bash_exits_3(self):
        bash = old_bash()
        if not bash:
            self.skipTest("no bash older than 4.4 on this host")
        _, env = self.sandbox()
        for flag in ("--help", "--check"):
            with self.subTest(flag=flag):
                d = self.install(env, 3, flag, argv=[bash, *INSTALL[1:]])
                self.assertIn("bash 4.4", d["errors"][0])


class ModelFilesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.r = Path(tmp.name).resolve()
        # An empty PATH: no provider CLI, so no model catalog is fetched.
        self.env = {
            "PATH": str(self.r),
            "HOME": str(self.r / "home"),
            "IDSTACK_CONFIG_DIR": str(self.r / "config"),
            "AGENTS_SKILLS_DIR": str(self.r / "agents/skills"),
        }
        self.file = self.r / "agents/pstack-models.md"
        (self.r / "config").mkdir()

    def models(self, rc: int, *args: str) -> str:
        r = subprocess.run([*MODELS, *args], capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, rc, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        return r.stderr

    def test_bad_overrides_are_errors_not_tracebacks(self):
        role = "bug-fix"
        cases = [
            ([1], "JSON object"),
            ({"roles": "x"}, "roles must be an object"),
            ({"roles": {role: 5}}, f"roles.{role} must be a string"),
            ({"roles": {"new": 5}}, "roles.new must be a string"),
            ({"t3": {"codex": 1}}, "t3.codex must be an object"),
            ({"notes": [1]}, "notes must be a list of strings"),
            ({"roles": {role: "opus high via claude"}}, "claudeAgent"),
        ]
        for override, want in cases:
            with self.subTest(override=override):
                (self.r / "config/models.json").write_text(json.dumps(override))
                self.assertIn(want, self.models(3))
        with self.subTest("--resolve skips an option it cannot parse"):
            (self.r / "config/models.json").write_text(json.dumps({"roles": {role: "nonsense"}}))
            self.models(0, "--resolve", "claude")

    def test_a_file_without_the_marker_is_the_users(self):
        self.models(0)
        managed = self.file.read_text()
        self.file.write_text("mine\n")
        self.models(0)
        self.models(0, "--check")
        self.assertEqual(self.file.read_text(), "mine\n")
        self.models(0, "--uninstall")
        self.assertEqual(self.file.read_text(), "mine\n")
        self.models(0, "--force")
        self.assertEqual(self.file.read_text(), managed)
        self.assertEqual(len(list((self.r / "agents/.idstack-backups").glob("*Z/pstack-models.md"))), 1)

        with self.subTest("a broken models.json does not stop an uninstall"):
            (self.r / "config/models.json").write_text("{")
            self.models(3, "--check")
            self.models(0, "--uninstall")
            self.assertFalse(self.file.exists())


if __name__ == "__main__":
    unittest.main()
