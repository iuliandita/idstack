import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin/idstack"
MUTATING = "terraform apply"
CLAUDE_HOOKS = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/bin/idstack" guard hook --harness claude',
                        "timeout": 15,
                    }
                ],
            }
        ]
    }
}


def codex_hook_file() -> Path:
    return ROOT / json.loads((ROOT / ".codex-plugin/plugin.json").read_text())["hooks"]


def handlers(path: Path) -> list[dict]:
    groups = json.loads(path.read_text())["hooks"]["PreToolUse"]
    return [dict(h, matcher=g.get("matcher")) for g in groups for h in g["hooks"]]


class CodexHookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.codex = self.tmp / "codex"
        self.env = {
            **os.environ,
            "HOME": str(self.tmp),
            "XDG_CONFIG_HOME": str(self.tmp / "config"),
            "IDSTACK_CONFIG_DIR": str(self.tmp / "idstack-config"),
            "IDSTACK_STATE_DIR": str(self.tmp / "idstack-state"),
            "CODEX_HOME": str(self.codex),
            "TYPESAFE_API_KEY": "",
        }

    def cli(self, *argv: str, env: dict | None = None) -> dict:
        r = subprocess.run(
            [sys.executable, str(BIN), *argv, "--json"],
            capture_output=True,
            text=True,
            env=env or self.env,
            stdin=subprocess.DEVNULL,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def add_plugin(self, codex_hook: bool = True) -> None:
        dest = self.codex / "plugins/cache/idstack/idstack/9.9.9"
        shutil.copytree(ROOT / "hooks", dest / "hooks")
        shutil.copy(ROOT / "plugin.json", dest / "plugin.json")
        if codex_hook:
            shutil.copytree(ROOT / ".codex-plugin", dest / ".codex-plugin")

    def user_entries(self) -> list[dict]:
        path = self.codex / "hooks.json"
        if not path.is_file():
            return []
        return [h for h in handlers(path) if "idstack guard hook" in h["command"]]

    def test_plugin_gives_codex_its_own_named_hook(self):
        path = codex_hook_file()
        self.assertTrue(path.is_file(), path)
        self.assertNotEqual(path, ROOT / "hooks/hooks.json")
        (hook,) = handlers(path)
        self.assertEqual(hook["matcher"], "Bash")
        self.assertEqual(hook["type"], "command")
        self.assertIn("guard hook --harness codex", hook["command"])
        self.assertIn("PLUGIN_ROOT", hook["command"])
        self.assertTrue(hook.get("statusMessage", "").strip())
        self.assertEqual(json.loads((ROOT / "hooks/hooks.json").read_text()), CLAUDE_HOOKS)

    def test_codex_manifest_matches_the_root_manifest(self):
        root = json.loads((ROOT / "plugin.json").read_text())
        codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        for key in ("name", "version", "description"):
            with self.subTest(key):
                self.assertEqual(codex[key], root[key])
        self.assertEqual(codex["interface"], root["extensions"]["com.openai"]["interface"])

    def test_hook_commands_answer_for_their_harness(self):
        self.cli("guard", "enable", "--mode", "ask")
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": MUTATING}})
        env = {**self.env, "PLUGIN_ROOT": str(ROOT), "CLAUDE_PLUGIN_ROOT": str(ROOT)}
        for path, want in ((codex_hook_file(), "deny"), (ROOT / "hooks/hooks.json", "ask")):
            with self.subTest(path=path.name):
                (hook,) = handlers(path)
                r = subprocess.run(hook["command"], shell=True, capture_output=True, text=True, env=env, input=payload)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"], want)

    def test_install_leaves_one_guard_entry(self):
        user = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "other-hook"}]},
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "idstack guard hook --harness codex"}],
                    },
                ]
            }
        }
        disabled = '[plugins."idstack@idstack"]\nenabled = false\n'
        cases = [
            # name, plugin, plugin ships the codex hook, config.toml, user file before, changed, user entries after
            ("no plugin", False, False, None, None, True, 1),
            ("no plugin, entry present", False, False, None, user, False, 1),
            ("plugin hook", True, True, None, None, False, 0),
            ("plugin hook and user entry", True, True, None, user, True, 0),
            ("plugin without a codex hook", True, False, None, None, True, 1),
            ("plugin disabled", True, True, disabled, None, True, 1),
        ]
        for name, plugin, ships, config, before, changed, after in cases:
            with self.subTest(name):
                shutil.rmtree(self.codex, ignore_errors=True)
                self.codex.mkdir(parents=True)
                if plugin:
                    self.add_plugin(ships)
                if config:
                    (self.codex / "config.toml").write_text(config)
                if before:
                    (self.codex / "hooks.json").write_text(json.dumps(before))
                d = self.cli("guard", "install", "--harness", "codex")
                self.assertEqual(d["changed"], changed, d)
                self.assertEqual(bool(d["plugin_hook"]), plugin and ships and not config, d)
                entries = self.user_entries()
                self.assertEqual(len(entries), after)
                if before:
                    self.assertIn("other-hook", (self.codex / "hooks.json").read_text())
                elif after:
                    self.assertTrue(entries[0].get("statusMessage", "").strip())
                self.assertFalse(self.cli("guard", "install", "--harness", "codex")["changed"])

    def test_uninstall_removes_only_the_user_entry(self):
        self.codex.mkdir(parents=True)
        self.cli("guard", "install", "--harness", "codex")
        self.add_plugin()
        d = self.cli("guard", "uninstall", "--harness", "codex")
        self.assertTrue(d["changed"], d)
        self.assertTrue(d["plugin_hook"], d)
        self.assertEqual(self.user_entries(), [])
        self.assertTrue(Path(d["plugin_hook"]).is_file())

    def test_doctor_counts_the_plugin_hook(self):
        fake = self.tmp / "bin"
        fake.mkdir()
        (fake / "codex").write_text("#!/bin/sh\necho '{}'\n")
        (fake / "codex").chmod(0o755)
        env = {**self.env, "PATH": str(fake)}
        self.cli("guard", "enable", "--mode", "ask")
        cases = [
            ("nothing installed", False, False, "warn", "not installed for codex"),
            ("plugin hook", True, False, "ok", ""),
            ("plugin hook and user entry", True, True, "warn", "two guard hooks for codex"),
        ]
        for name, plugin, user, status, detail in cases:
            with self.subTest(name):
                shutil.rmtree(self.codex, ignore_errors=True)
                self.codex.mkdir(parents=True)
                if user:
                    self.cli("guard", "install", "--harness", "codex")
                if plugin:
                    self.add_plugin()
                r = subprocess.run(
                    [sys.executable, str(BIN), "doctor", "--json"],
                    capture_output=True,
                    text=True,
                    env=env,
                    stdin=subprocess.DEVNULL,
                )
                (guard,) = [c for c in json.loads(r.stdout)["checks"] if c["name"] == "guard"]
                self.assertEqual(guard["status"], status, guard)
                self.assertIn(detail, guard["detail"])


if __name__ == "__main__":
    unittest.main()
