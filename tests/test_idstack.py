import importlib.machinery
import importlib.util
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin/idstack"
_loader = importlib.machinery.SourceFileLoader("idstack_cli", str(BIN))
_spec = importlib.util.spec_from_loader("idstack_cli", _loader)
idstack = importlib.util.module_from_spec(_spec)
_loader.exec_module(idstack)


def rc(address, rtype, actions, before=None, after=None):
    return {
        "address": address,
        "type": rtype,
        "change": {"actions": actions, "before": before, "after": after, "after_unknown": {}},
    }


PLAN = {
    "resource_changes": [
        rc("aws_instance.web", "aws_instance", ["update"], {"ami": "a"}, {"ami": "b"}),
        rc("aws_s3_bucket.logs", "aws_s3_bucket", ["create"], None, {"bucket": "logs"}),
        rc("aws_iam_role_policy.app", "aws_iam_role_policy", ["update"], {"policy": "x"}, {"policy": "y"}),
        rc("aws_security_group.web", "aws_security_group", ["no-op"], {}, {}),
        rc("aws_db_instance.main", "aws_db_instance", ["delete", "create"], {"engine": "pg"}, {"engine": "pg"}),
    ]
}


class PlanSummaryTest(unittest.TestCase):
    def test_classifies_changes(self):
        r = idstack.summarize_plan(PLAN, [], False)
        self.assertEqual(r["counts"], {"update": 2, "create": 1, "no-op": 1, "replace": 1})
        self.assertEqual(r["destructive"], ["aws_db_instance.main"])
        self.assertIn("aws_s3_bucket.logs", r["stateful"])
        self.assertIn("aws_db_instance.main", r["stateful"])
        self.assertEqual(r["iam"], ["aws_iam_role_policy.app"])
        self.assertEqual(r["changes"][0]["diff"], {"ami": {"before": "a", "after": "b"}})

    def test_predicate(self):
        cases = [
            ("replace fails", PLAN, ["*"], False),
            (
                "in scope passes",
                {"resource_changes": PLAN["resource_changes"][:2]},
                ["aws_instance.*", "aws_s3_bucket.*"],
                True,
            ),
            ("out of scope fails", {"resource_changes": PLAN["resource_changes"][:2]}, ["aws_instance.*"], False),
            ("empty plan fails", {}, ["*"], False),
            ("iam fails", {"resource_changes": PLAN["resource_changes"][2:3]}, ["*"], False),
            (
                "import outside scope fails",
                {
                    "resource_changes": [
                        dict(
                            rc("aws_instance.prod", "aws_instance", ["no-op"], {}, {}),
                            change={"actions": ["no-op"], "importing": {"id": "i-1"}},
                        )
                    ]
                },
                ["aws_instance.dev"],
                False,
            ),
            (
                "public db fails",
                {
                    "resource_changes": [
                        rc(
                            "aws_db_instance.prod",
                            "aws_db_instance",
                            ["update"],
                            {"publicly_accessible": False},
                            {"publicly_accessible": True},
                        )
                    ]
                },
                ["*"],
                False,
            ),
            ("errored fails", {"errored": True, "resource_changes": PLAN["resource_changes"][:1]}, ["*"], False),
            (
                "create with instance profile fails",
                {
                    "resource_changes": [
                        rc(
                            "aws_instance.app",
                            "aws_instance",
                            ["create"],
                            None,
                            {"ami": "a", "iam_instance_profile": "admin"},
                        )
                    ]
                },
                ["*"],
                False,
            ),
            (
                "create with empty exposure attrs passes",
                {
                    "resource_changes": [
                        rc(
                            "aws_instance.app",
                            "aws_instance",
                            ["create"],
                            None,
                            {"ami": "a", "security_groups": [], "iam_instance_profile": None},
                        )
                    ]
                },
                ["*"],
                True,
            ),
            (
                "network rules change fails",
                {
                    "resource_changes": [
                        rc(
                            "azurerm_storage_account.sa",
                            "azurerm_storage_account",
                            ["update"],
                            {"network_rules": [{"default_action": "Deny"}]},
                            {"network_rules": [{"default_action": "Allow"}]},
                        )
                    ]
                },
                ["*"],
                False,
            ),
        ]
        for name, plan, scope, ok in cases:
            with self.subTest(name):
                self.assertEqual(idstack.summarize_plan(plan, scope, True)["predicate"]["pass"], ok)

    def test_redacts_sensitive_values(self):
        change = {
            "actions": ["update"],
            "before": {"password": "old", "name": "db"},
            "after": {"password": "new", "name": "db2"},
            "after_unknown": {},
            "before_sensitive": {"password": True},
            "after_sensitive": {"password": True},
        }
        self.assertNotIn("new", json.dumps(idstack.change_diff(change)))
        self.assertEqual(idstack.change_diff(change)["name"], {"before": "db", "after": "db2"})


class GuardTest(unittest.TestCase):
    rules = idstack.load_rules()

    def test_classify(self):
        cases = {
            "terraform plan -out p": False,
            "terraform apply p": True,
            "tofu state rm aws_instance.x": True,
            "kubectl -n demo get pods": False,
            "kubectl --context prod -n demo delete pod x": True,
            "kubectl rollout status deploy/x": False,
            "kubectl rollout restart deploy/x": True,
            "helm template x .": False,
            "helm -n demo upgrade x .": True,
            "argocd app diff x": False,
            "argocd app sync x": True,
            "ansible-playbook site.yml --check --diff": False,
            "ansible-playbook site.yml": True,
            "ansible all -m ping": False,
            "ansible all -m shell -a uptime": True,
            "systemctl restart nginx": False,
            "ssh -i key -p 22 host sudo systemctl restart nginx": True,
            "ssh host 'kubectl delete ns x'": True,
            "bash -c 'tofu destroy -auto-approve'": True,
            "bash -lc 'kubectl delete namespace prod'": True,
            "sh -ec 'kubectl get pods'": False,
            "terragrunt run --all apply": True,
            "terragrunt --working-dir infra apply": True,
            "terragrunt run --all plan": False,
            "env FOO=1 timeout 30 helm uninstall x": True,
            "echo ok && kubectl apply -f x.yaml": True,
            "echo ok\nkubectl apply -f x.yaml": True,
            "aws s3 ls": False,
            "aws --profile p ec2 terminate-instances --instance-ids i-1": True,
            "gcloud compute instances delete vm-1": True,
            "qm list": False,
            "qm destroy 100": True,
            "git push origin main": False,
            "grep -r 'kubectl delete' docs": False,
            "idstack guard status": False,
            "idstack guard allow-once kubectl delete pod x": True,
            "python3 bin/idstack guard disable": True,
            "python3 -u bin/idstack guard disable": True,
            "idstack guard --mode log enable": True,
            "idstack --json guard --ttl 600 allow-once kubectl get pods": True,
            "uv run idstack guard uninstall --harness codex": True,
            "script -q -c 'idstack guard disable' /dev/null": True,
            "idstack guard test kubectl get pods": False,
            "aws s3 rm s3://example-bucket/idstack --recursive": True,
            "sudo -u root aws s3 rm s3://example-bucket --recursive": True,
            "if true; then aws s3 rm s3://example-bucket --recursive; fi": True,
            "aws s3 \\\n  rm s3://example-bucket --recursive": True,
            "kubectl --request-timeout 30s delete namespace prod": True,
            "aws s3 sync ./empty s3://example-bucket --delete": True,
            "aws s3 sync s3://example-bucket ./local": False,
            "systemctl --host example.com restart nginx": True,
        }
        for cmd, match in cases.items():
            with self.subTest(cmd):
                self.assertEqual(bool(idstack.classify(cmd, self.rules)), match)

    def hook(self, harness, cmd, mode="ask", state=None):
        env = dict(
            os.environ, IDSTACK_GUARD_MODE=mode, IDSTACK_STATE_DIR=state or self.state, IDSTACK_CONFIG_DIR=self.state
        )
        env.pop("TYPESAFE_API_KEY", None)
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
        r = subprocess.run(
            [sys.executable, str(BIN), "guard", "hook", "--harness", harness],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        return json.loads(r.stdout) if r.stdout.strip() else None

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_hook_decisions(self):
        self.assertIsNone(self.hook("claude", "kubectl delete pod x", mode="off"))
        self.assertIsNone(self.hook("claude", "kubectl get pods"))
        out = self.hook("claude", "kubectl delete pod x")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask")
        out = self.hook("codex", "kubectl delete pod x")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.hook("opencode", "kubectl delete pod x")["decision"], "deny")
        self.assertIsNone(self.hook("claude", "kubectl delete pod x", mode="log"))
        log = [json.loads(x) for x in (Path(self.state) / "guard.log").read_text().splitlines()]
        self.assertEqual([e["decision"] for e in log], ["ask", "deny", "deny", "logged"])

    def test_hook_fails_closed(self):
        blocked = Path(self.state) / "not-a-dir"
        blocked.write_text("")
        out = self.hook("claude", "kubectl delete pod x", state=str(blocked))
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask", "unwritable state must still ask")
        (Path(self.state) / "guard.json").write_text("{trunc")
        out = self.hook("claude", "kubectl delete pod x", mode="")
        self.assertEqual(
            out["hookSpecificOutput"]["permissionDecision"], "ask", "corrupt config must not turn the guard off"
        )

    def test_allow_once(self):
        env = dict(os.environ, IDSTACK_STATE_DIR=self.state, IDSTACK_CONFIG_DIR=self.state)
        r = subprocess.run(
            [sys.executable, str(BIN), "guard", "allow-once", "kubectl", "delete", "pod", "x"],
            env=env,
            capture_output=True,
            stdin=subprocess.DEVNULL,
        )
        self.assertEqual(r.returncode, 1, "allow-once must refuse without a terminal")
        token = {idstack.cmd_hash("kubectl delete pod x"): time.time() + 60}
        (Path(self.state) / "guard-allow.json").write_text(json.dumps(token))
        self.assertEqual(
            self.hook("codex", "kubectl  delete pod x")["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertIsNone(self.hook("codex", "kubectl delete pod x"))
        self.assertEqual(self.hook("codex", "kubectl delete pod x")["hookSpecificOutput"]["permissionDecision"], "deny")


class JevRuleTest(unittest.TestCase):
    def test_outcomes(self):
        above = {"rule": "any-above", "threshold": 0.3, "questions": {"a": {}, "b": {}}}
        below = {"rule": "any-below", "threshold": 0.7, "questions": {"s": {}}}

        def ans(**kw):
            return {k: {"type": "noul", "noul": v} for k, v in kw.items()}

        cases = [
            (above, ans(a=0.1, b=0.2), "clear"),
            (above, ans(a=0.1, b=0.9), "flag"),
            (above, ans(a=0.3, b=0.1), "unsettled"),
            (above, ans(a=0.1), "unsettled"),
            (above, None, "unsettled"),
            (above, {"a": None, "b": {"noul": 0.1}}, "unsettled"),
            (below, ans(s=0.9), "clear"),
            (below, ans(s=0.5), "flag"),
        ]
        for battery, answers, want in cases:
            with self.subTest(battery=battery["rule"], answers=answers):
                self.assertEqual(idstack.jev_outcome(battery, answers)[0], want)

    def test_batteries_and_cases_load(self):
        for path in sorted((ROOT / "src/questions").glob("*.json")):
            with self.subTest(path.stem):
                b = json.loads(path.read_text())
                self.assertEqual(b["battery"], path.stem)
                self.assertIn(b["rule"], ("any-above", "any-below", "rank"))
                cases = [
                    json.loads(x)
                    for x in (ROOT / "fixtures/jev" / path.stem / "cases.jsonl").read_text().splitlines()
                    if x
                ]
                self.assertTrue(any(c["split"] == "holdout" for c in cases))
                self.assertEqual(len({c["id"] for c in cases}), len(cases))


class UsageErrorTest(unittest.TestCase):
    def test_judge_usage_errors_exit_2_with_error_prefix(self):
        for args in (["nope"], ["plan-reading"]):
            with self.subTest(args=args):
                r = subprocess.run(
                    [sys.executable, str(BIN), "judge", *args],
                    capture_output=True,
                    text=True,
                    env={**os.environ, "TYPESAFE_API_KEY": "x"},
                )
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertTrue(r.stderr.startswith("error: "), r.stderr)
                self.assertEqual(r.stdout, "")


class JsonContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        t = self.tmp
        self.env = {
            **os.environ,
            "HOME": t,
            "XDG_CONFIG_HOME": f"{t}/config",
            "XDG_STATE_HOME": f"{t}/state",
            "IDSTACK_CONFIG_DIR": f"{t}/idstack-config",
            "IDSTACK_STATE_DIR": f"{t}/idstack-state",
            "CLAUDE_CONFIG_DIR": f"{t}/claude",
            "CODEX_HOME": f"{t}/codex",
            "AGENTS_SKILLS_DIR": f"{t}/agents/skills",
            "OPENCODE_SKILLS_DIR": f"{t}/opencode/skills",
            "OPENCODE_AGENTS_DIR": f"{t}/opencode/agents",
            "IDSTACK_CACHE_DIR": f"{t}/cache",
            "IDSTACK_BIN_DIR": f"{t}/bin",
            "TYPESAFE_API_KEY": "",
        }

    def run_json(self, argv, rc, extra, env=None):
        r = subprocess.run(argv, capture_output=True, text=True, env=env or self.env, stdin=subprocess.DEVNULL)
        if rc is None:  # doctor depends on which harnesses the host has
            rc = r.returncode
            self.assertIn(rc, (0, 1), r.stderr)
        self.assertEqual(r.returncode, rc, r.stderr)
        d = json.loads(r.stdout)
        self.assertIsInstance(d["ok"], bool)
        self.assertIsInstance(d["errors"], list)
        self.assertEqual(d["ok"], rc == 0, d)
        self.assertEqual(bool(d["errors"]), rc != 0, d)
        for key in extra:
            self.assertIn(key, d)
        return d

    def test_cli_commands(self):
        plan = str(ROOT / "fixtures/plans/create-only.plan.json")
        cases = [
            (["check"], 0, []),
            (["build", "--check"], 0, ["check", "stale"]),
            (["plan-summary", plan], 0, ["counts", "changes"]),
            (["plan-summary", plan, "--scope", "zzz", "--predicate"], 1, ["predicate"]),
            (["plan-summary", f"{self.tmp}/missing.json"], 2, []),
            (["judge", "plan-reading", "--example"], 0, ["battery", "items"]),
            (["judge", "plan-reading"], 4, ["used", "reason"]),
            (["judge", "nope"], 2, []),
            (["guard", "test", "terraform apply"], 0, ["match", "hits"]),
            (["guard", "enable"], 0, ["mode", "jev"]),
            (["guard", "status"], 0, ["config", "recent"]),
            (["guard", "install", "--harness", "opencode", "--dry-run"], 0, ["path", "changed", "config"]),
            (["guard", "install", "--harness", "claude"], 2, []),
            (["guard", "allow-once", "x"], 1, []),
            (["guard", "nonsense"], 2, []),
        ]
        for argv, rc, extra in cases:
            with self.subTest(argv=argv):
                self.run_json([sys.executable, str(BIN), *argv, "--json"], rc, extra)

    def test_doctor(self):
        bare = {**self.env, "PATH": self.tmp}  # no harness CLIs, so the slow probes do not run
        self.run_json([sys.executable, str(BIN), "doctor", "--json"], None, ["checks"], env=bare)

    @unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "bash and git needed")
    def test_install_script(self):
        base = ["bash", str(ROOT / "install.sh"), "--harness", "opencode", "--no-models", "--source", str(ROOT)]
        missing = self.run_json([*base, "--check", "--json"], 1, ["mode", "components", "harnesses"])
        self.assertEqual(missing["mode"], "check")
        self.assertTrue(all({"name", "state", "detail"} <= set(c) for c in missing["components"]))
        dry = self.run_json([*base, "--dry-run", "--json"], 0, ["commands", "dry_run"])
        self.assertTrue(dry["dry_run"] and dry["commands"])
        self.assertFalse(Path(self.env["OPENCODE_SKILLS_DIR"]).exists(), "--dry-run must not write")
        self.run_json(["bash", str(ROOT / "install.sh"), "--bogus", "--json"], 2, ["mode"])


NODE_DRIVER = """
const { default: plugin } = await import(process.argv[1]);
let hook;
await plugin.setup({ location: { directory: process.cwd() }, tool: { hook: async (_, cb) => { hook = cb; } } });
const out = [];
for (const command of JSON.parse(process.argv[2])) {
  try { await hook({ tool: "bash", input: { command } }); out.push("pass"); } catch { out.push("block"); }
}
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node"), "node not installed")
class OpencodePluginTest(unittest.TestCase):
    def test_blocks_matches_and_unreadable_shapes(self):
        commands = ["kubectl delete pod x", ["kubectl", "delete", "pod", "x"], {"x": 1}, "kubectl get pods", ""]
        with tempfile.TemporaryDirectory() as state:
            env = dict(os.environ, IDSTACK_GUARD_MODE="ask", IDSTACK_STATE_DIR=state, IDSTACK_CONFIG_DIR=state)
            env.pop("TYPESAFE_API_KEY", None)
            r = subprocess.run(
                [
                    "node",
                    "--input-type=module",
                    "-e",
                    NODE_DRIVER,
                    str(ROOT / "harness/opencode/guard/server.js"),
                    json.dumps(commands),
                ],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
        self.assertEqual(json.loads(r.stdout), ["block", "block", "block", "pass", "pass"])


class GuardInstallTest(unittest.TestCase):
    def run_guard(self, cfg, *args):
        env = dict(os.environ, XDG_CONFIG_HOME=cfg)
        return subprocess.run(
            [sys.executable, str(BIN), "guard", *args, "--harness", "opencode"],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    def test_opencode_install_keeps_other_plugins(self):
        with tempfile.TemporaryDirectory() as cfg:
            path = Path(cfg) / "opencode/opencode.json"
            self.run_guard(cfg, "uninstall")
            self.assertFalse(path.exists(), "uninstall must not create a config")
            path.parent.mkdir()
            path.write_text(json.dumps({"plugins": [{"package": "/x/other"}]}))
            self.run_guard(cfg, "install")
            self.assertIn("already", self.run_guard(cfg, "install"))
            plugins = json.loads(path.read_text())["plugins"]
            self.assertEqual(plugins, [{"package": "/x/other"}, {"package": str(ROOT / "harness/opencode/guard")}])
            self.run_guard(cfg, "uninstall")
            self.assertEqual(json.loads(path.read_text())["plugins"], [{"package": "/x/other"}])


class OpencodePermissionTest(unittest.TestCase):
    def test_skill_effect(self):
        v1 = {"permission": {"skill": {"*": "deny", "id-*": "allow", "id-secret": "ask"}}}
        v2 = {
            "permissions": [
                {"action": "skill", "resource": "*", "effect": "deny"},
                {"action": "skill", "resource": "id-mode", "effect": "allow"},
            ]
        }
        cases = [
            ({}, "id-mode", "allow"),
            (v1, "id-mode", "allow"),
            (v1, "id-secret", "ask"),
            (v1, "poteto-mode", "deny"),
            (v2, "id-mode", "allow"),
            (v2, "setup", "deny"),
            ({"permission": {"skill": "deny"}}, "id-mode", "deny"),
        ]
        for doc, skill, want in cases:
            with self.subTest(skill=skill, doc=doc):
                self.assertEqual(idstack.opencode_skill_effect(doc, skill), want)


_mloader = importlib.machinery.SourceFileLoader("pstack_models", str(ROOT / "scripts/pstack_models.py"))
_mspec = importlib.util.spec_from_loader("pstack_models", _mloader)
pstack_models = importlib.util.module_from_spec(_mspec)
_mloader.exec_module(pstack_models)
SHIPPED_ROLES = json.loads((ROOT / "config/pstack-models.json").read_text())["roles"]


class ModelRoutingTest(unittest.TestCase):
    PROVIDERS = ("claudeAgent", "codex", "opencode")

    def test_every_install_combination_resolves(self):
        for n in (1, 2, 3):
            for have in itertools.combinations(self.PROVIDERS, n):
                for harness in have:
                    for role, value in SHIPPED_ROLES.items():
                        with self.subTest(have=have, harness=harness, role=role):
                            picks = pstack_models.resolve(value, harness, set(have))
                            self.assertNotIn("parent", picks)
                            self.assertTrue(all(p.rsplit(" via ", 1)[1] in have for p in picks))
                            if n == 1:
                                self.assertTrue(all(p.endswith(f"via {harness}") for p in picks))
                            if len(picks) == 2 and n > 1:
                                self.assertNotEqual(picks[0], picks[1], "a panel needs two different models")

    def test_parent_values_resolve_to_parent(self):
        for value in ("inherit-parent", "auto"):
            self.assertEqual(pstack_models.resolve(value, "codex", {"codex"}), ["parent"])

    def test_full_install_keeps_home_models(self):
        everything = set(self.PROVIDERS)
        cases = [
            ("claudeAgent", "hardest tasks", "claude-opus-5-5 high via claudeAgent"),
            ("codex", "hardest tasks", "gpt-6.1-sol high via codex"),
            ("opencode", "hardest tasks", "gpt-6.1-sol high via codex"),
            ("claudeAgent", "bug-fix", "gpt-6.1-sol high via codex"),
            ("opencode", "judgment and prose", "claude-opus-5-5 medium via claudeAgent"),
            ("codex", "how explorer", "opencode-go/deepseek-v4.1-flash high via opencode"),
            ("claudeAgent", "reflect tooling", "claude-haiku-5-5 medium via claudeAgent"),
        ]
        for harness, role, want in cases:
            with self.subTest(harness=harness, role=role):
                self.assertEqual(pstack_models.resolve(SHIPPED_ROLES[role], harness, everything)[0], want)


class ModelOverrideTest(unittest.TestCase):
    def show(self, cfg, override):
        (Path(cfg) / "models.json").write_text(json.dumps(override))
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/pstack_models.py"), "--show"],
            env=dict(os.environ, IDSTACK_CONFIG_DIR=cfg),
            capture_output=True,
            text=True,
        )

    def test_override_merges_over_defaults(self):
        with tempfile.TemporaryDirectory() as cfg:
            r = self.show(cfg, {"roles": {"hardest tasks": "claude-sonnet-5-5 high via claudeAgent"}})
            roles = json.loads(r.stdout)["roles"]
            self.assertEqual(roles["hardest tasks"], "claude-sonnet-5-5 high via claudeAgent")
            self.assertEqual(len(roles), 17, "unchanged roles keep their defaults")
            for bad in ({"rolse": {}}, {"claude": {"roles": {}}}):
                with self.subTest(bad=bad):
                    self.assertEqual(self.show(cfg, bad).returncode, 3, "a wrong or old-shape key must fail")


class BuildTest(unittest.TestCase):
    def test_generated_files_current(self):
        r = subprocess.run([sys.executable, str(BIN), "build", "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
