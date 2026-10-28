import importlib.machinery
import importlib.util
import json
import os
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
    return {"address": address, "type": rtype,
            "change": {"actions": actions, "before": before, "after": after, "after_unknown": {}}}


PLAN = {"resource_changes": [
    rc("aws_instance.web", "aws_instance", ["update"], {"ami": "a"}, {"ami": "b"}),
    rc("aws_s3_bucket.logs", "aws_s3_bucket", ["create"], None, {"bucket": "logs"}),
    rc("aws_iam_role_policy.app", "aws_iam_role_policy", ["update"], {"policy": "x"}, {"policy": "y"}),
    rc("aws_security_group.web", "aws_security_group", ["no-op"], {}, {}),
    rc("aws_db_instance.main", "aws_db_instance", ["delete", "create"], {"engine": "pg"}, {"engine": "pg"}),
]}


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
            ("in scope passes", {"resource_changes": PLAN["resource_changes"][:2]}, ["aws_instance.*", "aws_s3_bucket.*"], True),
            ("out of scope fails", {"resource_changes": PLAN["resource_changes"][:2]}, ["aws_instance.*"], False),
            ("empty plan fails", {}, ["*"], False),
            ("iam fails", {"resource_changes": PLAN["resource_changes"][2:3]}, ["*"], False),
            ("errored fails", {"errored": True, "resource_changes": PLAN["resource_changes"][:1]}, ["*"], False),
        ]
        for name, plan, scope, ok in cases:
            with self.subTest(name):
                self.assertEqual(idstack.summarize_plan(plan, scope, True)["predicate"]["pass"], ok)


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
        }
        for cmd, match in cases.items():
            with self.subTest(cmd):
                self.assertEqual(bool(idstack.classify(cmd, self.rules)), match)

    def hook(self, harness, cmd, mode="ask", state=None):
        env = dict(os.environ, IDSTACK_GUARD_MODE=mode, IDSTACK_STATE_DIR=state or self.state,
                   IDSTACK_CONFIG_DIR=self.state)
        env.pop("TYPESAFE_API_KEY", None)
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
        r = subprocess.run([sys.executable, str(BIN), "guard", "hook", "--harness", harness],
                           input=payload, capture_output=True, text=True, env=env, check=True)
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

    def test_allow_once(self):
        env = dict(os.environ, IDSTACK_STATE_DIR=self.state, IDSTACK_CONFIG_DIR=self.state)
        r = subprocess.run([sys.executable, str(BIN), "guard", "allow-once", "kubectl", "delete", "pod", "x"],
                           env=env, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 1, "allow-once must refuse without a terminal")
        token = {idstack.cmd_hash("kubectl delete pod x"): time.time() + 60}
        (Path(self.state) / "guard-allow.json").write_text(json.dumps(token))
        self.assertIsNone(self.hook("codex", "kubectl  delete pod x"))
        self.assertEqual(self.hook("codex", "kubectl delete pod x")["hookSpecificOutput"]["permissionDecision"], "deny")


class JevRuleTest(unittest.TestCase):
    def test_outcomes(self):
        above = {"rule": "any-above", "threshold": 0.3, "questions": {"a": {}, "b": {}}}
        below = {"rule": "any-below", "threshold": 0.7, "questions": {"s": {}}}
        ans = lambda **kw: {k: {"type": "noul", "noul": v} for k, v in kw.items()}
        cases = [
            (above, ans(a=0.1, b=0.2), "clear"),
            (above, ans(a=0.1, b=0.9), "flag"),
            (above, ans(a=0.3, b=0.1), "unsettled"),
            (above, ans(a=0.1), "unsettled"),
            (above, None, "unsettled"),
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
                cases = [json.loads(x) for x in (ROOT / "fixtures/jev" / path.stem / "cases.jsonl").read_text().splitlines() if x]
                self.assertTrue(any(c["split"] == "holdout" for c in cases))
                self.assertEqual(len({c["id"] for c in cases}), len(cases))


class BuildTest(unittest.TestCase):
    def test_generated_files_current(self):
        r = subprocess.run([sys.executable, str(BIN), "build", "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
