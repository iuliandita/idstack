import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import tempfile
import tomllib
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
_loader = importlib.machinery.SourceFileLoader("idstack_cli_judge", str(ROOT / "bin/idstack"))
_spec = importlib.util.spec_from_loader("idstack_cli_judge", _loader)
idstack = importlib.util.module_from_spec(_spec)
_loader.exec_module(idstack)

ABOVE = {"battery": "t", "model": "m", "item_key": "x", "rule": "any-above", "threshold": 0.3, "questions": {"a": {}}}
BELOW = {**ABOVE, "rule": "any-below", "threshold": 0.7}


def opener(payload=None, error: Exception | None = None) -> mock.Mock:
    """Stand-in for the HTTP call: returns payload as the response body, or raises error."""
    resp = mock.MagicMock()
    resp.__enter__.return_value.read.return_value = json.dumps(payload).encode()
    return mock.Mock(return_value=resp, side_effect=error)


def run_main(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with (
        mock.patch("sys.argv", ["idstack", *argv]),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ):
        try:
            code = idstack.main()
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class JudgeAnswerTest(unittest.TestCase):
    def test_malformed_answers_are_unsettled(self):
        for battery in (ABOVE, BELOW):
            for value in (float("nan"), float("inf"), True, False, 5, -0.1, "0.1", None, [0.1]):
                with self.subTest(rule=battery["rule"], value=value):
                    self.assertEqual(idstack.jev_outcome(battery, {"a": {"noul": value}})[0], "unsettled")
        self.assertEqual(idstack.jev_outcome({**ABOVE, "questions": {}}, {})[0], "unsettled")
        self.assertEqual(idstack.jev_outcome(ABOVE, {"a": {"noul": 0.1}})[0], "clear")
        self.assertEqual(idstack.jev_outcome(BELOW, {"a": {"noul": 1}})[0], "clear")

    def test_non_dict_response_is_an_item_error(self):
        for payload in ([{"answers": {}}], "clear", 1, None):
            with self.subTest(payload=payload), mock.patch.object(idstack.JEV_OPENER, "open", opener(payload)):
                (result,) = idstack.judge_items(ABOVE, [("one", "item")], "dummy", None)
                self.assertEqual(result["outcome"], "unsettled")
                self.assertIn("not a JSON object", result["error"])


class JudgeTransportTest(unittest.TestCase):
    def test_url_must_be_https(self):
        for url in ("http://api.example.com/v1", "file:///etc/hostname", "https://", "api.example.com/v1", ""):
            with (
                self.subTest(url=url),
                mock.patch.object(idstack, "JEV_URL", url),
                mock.patch.object(idstack.JEV_OPENER, "open", opener({})) as sent,
            ):
                resp, err, _ = idstack.jev_ask(ABOVE, "item", "dummy")
                self.assertIsNone(resp)
                self.assertIn("https", err)
                sent.assert_not_called()
                code, out, _ = run_main_with_key("judge", "plan-reading", "--eval", "--json")
                self.assertEqual(code, 2)
                self.assertFalse(json.loads(out)["ok"])
                sent.assert_not_called()

    def test_redirects_are_not_followed(self):
        self.assertTrue(any(isinstance(h, idstack.NoRedirect) for h in idstack.JEV_OPENER.handlers))
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                self.assertIsNone(
                    idstack.NoRedirect().redirect_request(None, None, code, "moved", {}, "http://api.example.com/")
                )

    def test_command_is_redacted_before_it_is_sent(self):
        cases = [
            ("DB_PASSWORD=hunter2 make deploy", "DB_PASSWORD=<redacted> make deploy"),
            ("ENV=prod ./deploy.sh", "ENV=<redacted:production> ./deploy.sh"),
            ("A='x y' B=\"p q\" just up", "A=<redacted> B=<redacted> just up"),
            ("true && TOKEN=abc ./run.sh", "true && TOKEN=<redacted> ./run.sh"),
            ("./deploy.sh --api-token abc123 --force", "./deploy.sh --api-token <redacted> --force"),
            ("./deploy.sh --password=hunter2", "./deploy.sh --password=<redacted>"),
            ("./deploy.sh --client-secret 'a b' --dry-run", "./deploy.sh --client-secret <redacted> --dry-run"),
            ("./deploy.sh --password --force", "./deploy.sh --password --force"),
            ("./sync.sh https://user:pw@example.com/repo", "./sync.sh https://<redacted>@example.com/repo"),
            ("./call.sh -H 'Authorization: Bearer abc.def'", "./call.sh -H 'Authorization: Bearer <redacted>'"),
            ("./mk.sh --from-literal=password=abc", "./mk.sh --from-literal=password=<redacted>"),
            ('./run.sh -e "TOKEN=x" --privileged img', './run.sh -e "TOKEN=<redacted>" --privileged img'),
            ("env STAGE=live ./deploy.sh", "env STAGE=<redacted> ./deploy.sh"),
            ('bash -c "REGION=eu ./deploy.sh"', 'bash -c "REGION=<redacted> ./deploy.sh"'),
            # Arguments are what the judge reads: masking them could clear what the full text flags.
            ("dd if=/dev/zero of=/dev/sdb bs=1M", "dd if=/dev/zero of=/dev/sdb bs=1M"),
            ("./up.sh web --set image.tag=1.2", "./up.sh web --set image.tag=1.2"),
            ("./tool my-secret prod-db", "./tool my-secret prod-db"),
            ("make deploy", "make deploy"),
        ]
        for cmd, want in cases:
            with self.subTest(cmd=cmd):
                self.assertEqual(idstack.redact_command(cmd), want)
        with mock.patch.object(idstack.JEV_OPENER, "open", opener({"answers": {}})) as sent:
            idstack.jev_ask(ABOVE, {"cmd": "API_KEY=abc123 make deploy", "cwd_hint": "/srv/app"}, "dummy")
        wire = sent.call_args.args[0].data.decode()
        self.assertNotIn("abc123", wire)
        self.assertIn("API_KEY=<redacted> make deploy", wire)


def run_main_with_key(*argv: str) -> tuple[int, str, str]:
    with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "dummy"}):
        return run_main(*argv)


class JudgeEvalTest(unittest.TestCase):
    def test_eval_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tune_only = Path(tmp) / "cases.jsonl"
            tune_only.write_text(json.dumps({"id": "a", "split": "tune", "item": {}, "expected": "flag"}) + "\n")
            broken = Path(tmp) / "broken.jsonl"
            broken.write_text(json.dumps({"id": "a", "split": "tune"}) + "\n")
            down = opener(error=urllib.error.URLError("down"))
            flagged = opener({"answers": {"holds_persistent_data": {"noul": 0.9}, "widens_iam": {"noul": 0.9}}})
            cases = [
                ("missing cases file", ["--cases", f"{tmp}/missing.jsonl"], flagged, 2),
                ("case without item", ["--cases", str(broken)], flagged, 2),
                ("zero cases selected", ["--cases", str(tune_only), "--split", "holdout"], flagged, 1),
                ("empty cases file", ["--cases", os.devnull], flagged, 1),
                ("every call fails", [], down, 3),
                ("no false negative", [], flagged, 0),
            ]
            for name, args, http, want in cases:
                with self.subTest(name), mock.patch.object(idstack.JEV_OPENER, "open", http):
                    code, out, _ = run_main_with_key("judge", "plan-reading", "--eval", "--json", *args)
                    self.assertEqual(code, want, out)
                    doc = json.loads(out)
                    self.assertEqual(doc["ok"], want == 0)
                    self.assertEqual(bool(doc["errors"]), want != 0)

    def test_plan_reading_items_are_change_records(self):
        plan = json.loads((ROOT / "fixtures/plans/create-only.plan.json").read_text())
        record = idstack.summarize_plan(plan, [], False)["changes"][0]
        lines = (ROOT / "fixtures/jev/plan-reading/cases.jsonl").read_text().splitlines()
        for case in map(json.loads, lines):
            with self.subTest(case["id"]):
                self.assertEqual(set(case["item"]), set(record))
                for key in ("importing", "stateful", "iam", "network", "in_scope"):
                    self.assertIsInstance(case["item"][key], bool)
                self.assertIsInstance(case["item"]["diff"], dict)


class CliContractTest(unittest.TestCase):
    def test_any_exception_keeps_one_json_object(self):
        with mock.patch.object(idstack, "cmd_build", side_effect=RuntimeError("boom")):
            code, out, err = run_main("build", "--json")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out), {"ok": False, "errors": ["internal error: RuntimeError: boom"]})
        self.assertNotIn("Traceback", err)

    def test_json_keeps_human_text_on_stderr(self):
        code, out, err = run_main("judge", "plan-reading", "--example", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["battery"], "plan-reading")
        self.assertIn("items for plan-reading", err)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            idstack.emit({"ok": True, "errors": [], "kept": 1}, True, "text", ok=False, errors=["real"])
        self.assertEqual(json.loads(out.getvalue()), {"ok": False, "errors": ["real"], "kept": 1})

    def test_doctor_live_reports_a_failed_probe(self):
        cases = [
            ((0, "prod\n"), (0, "yes\n"), "warn"),
            ((0, "dev\n"), (1, "no\n"), "ok"),
            ((0, "dev\n"), (1, "no - no RBAC policy matched\n"), "ok"),
            ((0, "dev\n"), (1, ""), "fail"),
            ((0, "dev\n"), (127, "timed out"), "fail"),
            ((1, ""), (0, "yes\n"), "fail"),
        ]
        for context, can_i, want in cases:

            def run_quiet(cmd, timeout=20, context=context, can_i=can_i):
                if cmd[0] != "kubectl":
                    return 0, ""
                return context if "current-context" in cmd else can_i

            out = io.StringIO()
            with (
                self.subTest(context=context, can_i=can_i),
                mock.patch.object(idstack, "run_quiet", run_quiet),
                mock.patch.object(idstack.shutil, "which", lambda name: "/bin/kubectl" if name == "kubectl" else None),
                contextlib.redirect_stdout(out),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                idstack.cmd_doctor(argparse.Namespace(live=True, json=True))
                (probe,) = [c for c in json.loads(out.getvalue())["checks"] if c["name"] == "kube context write access"]
                self.assertEqual(probe["status"], want, probe)


class BuildTest(unittest.TestCase):
    BODY = 'Match \\d+ in C:\\temp, keep """triple quotes""" and a trailing backslash \\\n'

    def build(self, check: bool) -> tuple[int, dict]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = idstack.cmd_build(argparse.Namespace(check=check, json=True))
        return code, json.loads(out.getvalue())

    def test_escaping_and_orphaned_files(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(idstack, "ROOT", Path(tmp)):
            root = Path(tmp)
            (root / "agents").mkdir()
            (root / "skills/demo").mkdir(parents=True)
            (root / "skills/demo/SKILL.md").write_text("demo\n")
            agent = "---\nname: {0}\ndescription: d\ntools: Read, Edit\n---\n" + self.BODY
            (root / "agents/old.md").write_text(agent.format("old"))
            self.assertEqual(self.build(check=False)[0], 0)
            toml = tomllib.loads((root / "harness/codex/agents/old.toml").read_text())
            self.assertEqual(toml["developer_instructions"], self.BODY)
            self.assertEqual(self.build(check=True)[0], 0)

            hand_written = root / "harness/opencode/agents/notes.md"
            hand_written.write_text("kept by hand\n")
            (root / "agents/old.md").rename(root / "agents/new.md")
            (root / "agents/new.md").write_text(agent.format("new"))
            (root / "skills/demo/SKILL.md").unlink()
            orphans = [
                "harness/codex/agents/old.toml",
                "harness/opencode/agents/old.md",
                "skills/demo/agents/openai.yaml",
            ]
            code, doc = self.build(check=True)
            self.assertEqual(code, 1)
            self.assertFalse(doc["ok"])
            for path in orphans:
                self.assertIn(path, doc["stale"])
            self.assertTrue((root / orphans[0]).exists(), "--check must not change files")

            code, doc = self.build(check=False)
            self.assertEqual((code, doc["removed"]), (0, orphans))
            self.assertFalse(any((root / p).exists() for p in orphans))
            self.assertTrue(hand_written.exists())
            self.assertEqual(self.build(check=True)[0], 0)


if __name__ == "__main__":
    unittest.main()
