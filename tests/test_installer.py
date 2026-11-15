import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ["bash", str(ROOT / "install.sh"), "--harness", "opencode", "--no-models", "--json"]
GIT = ["git", "-c", "user.name=test", "-c", "user.email=test"]
GUARD_ENTRY = '{"plugins": [{"package": "/somewhere/harness/opencode/guard"}]}\n'


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

    def install(self, env: dict[str, str], rc: int, *args: str, argv: list[str] | None = None) -> dict:
        r = subprocess.run(
            [*(argv or INSTALL), *args], capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL
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


if __name__ == "__main__":
    unittest.main()
