import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin/idstack"
PLANS = ROOT / "fixtures/plans"
_loader = importlib.machinery.SourceFileLoader("idstack_plan_cli", str(BIN))
_spec = importlib.util.spec_from_loader("idstack_plan_cli", _loader)
idstack = importlib.util.module_from_spec(_spec)
_loader.exec_module(idstack)

DESTRUCTIVE = "delete, replace, or forget"
IAM = "IAM change"
NETWORK = "network change"
UNRECOGNIZED = "unrecognized action"


def rc(address, actions, before=None, after=None, unknown=None):
    change = {"actions": actions, "before": before, "after": after, "after_unknown": unknown or {}}
    return {"address": address, "type": address.split(".")[-2], "change": change}


def plan(*changes, **extra):
    return {"resource_changes": list(changes), **extra}


def config(*resources, calls=None):
    return {"root_module": {"resources": list(resources), "module_calls": calls or {}}}


def res(address, **expressions):
    return {"address": address, "expressions": expressions}


def predicate(p, scope=("*",), **kw):
    return idstack.summarize_plan(p, list(scope), True, **kw)["predicate"]


TAGS = rc("aws_instance.web", ["update"], {"tags": {}}, {"tags": {"v": "2"}})
QUEUE = rc("aws_sqs_queue.q", ["create"], None, {"name": "q"}, {"policy": True, "id": True})
MODULE_QUEUE = dict(QUEUE, address='module.app["eu"].aws_sqs_queue.q[0]')
SET = {"references": ["var.policy"]}
INSTANCE = rc(
    "aws_instance.web",
    ["create"],
    None,
    {"ami": "ami-1", "instance_type": "t3.micro", "associate_public_ip_address": None, "tags": {"app": "web"}},
    {"id": True, "public_ip": True, "public_dns": True, "vpc_security_group_ids": True, "iam_instance_profile": True},
)
INSTANCE_CONFIG = config(res("aws_instance.web", ami=SET, instance_type={"constant_value": "t3.micro"}, tags=SET))
DATABASE = rc(
    "aws_db_instance.orders",
    ["create"],
    None,
    {
        "engine": "postgres",
        "publicly_accessible": False,
        "iam_database_authentication_enabled": False,
        "storage_encrypted": True,
        "vpc_security_group_ids": None,
    },
    {"id": True, "arn": True, "endpoint": True},
)
POLICY = rc("aws_iam_role_policy.app", ["update"], {"policy": "a"}, {"policy": "b"})
RULE = rc("aws_security_group_rule.web", ["create"], None, {"from_port": 22, "cidr_blocks": ["0.0.0.0/0"]})


class PredicateTest(unittest.TestCase):
    def test_reasons(self):
        """Each row: plan, scope, flags, and the reasons the predicate must give (none means it passes)."""
        eks = {"endpoint_public_access": False, "public_access_cidrs": ["203.0.113.0/24"]}
        cases = [
            ("update in scope passes", plan(TAGS), ["aws_instance.*"], {}, []),
            ("no scope fails", plan(TAGS), [], {}, ["no scope"]),
            ("delete", plan(rc("aws_instance.web", ["delete"], {"ami": "a"}, None)), ["*"], {}, [DESTRUCTIVE]),
            (
                "replace",
                plan(rc("aws_instance.web", ["delete", "create"], {"ami": "a"}, {"ami": "b"})),
                ["*"],
                {},
                [DESTRUCTIVE],
            ),
            (
                "replace, create first",
                plan(rc("aws_instance.web", ["create", "delete"], {"ami": "a"}, {"ami": "b"})),
                ["*"],
                {},
                [DESTRUCTIVE],
            ),
            ("forget", plan(rc("aws_instance.web", ["forget"], {"ami": "a"}, None)), ["*"], {}, [DESTRUCTIVE]),
            (
                "create then forget",
                plan(rc("aws_instance.web", ["create", "forget"], {"ami": "a"}, {"ami": "b"})),
                ["*"],
                {},
                [DESTRUCTIVE],
            ),
            (
                "delete in an odd list",
                plan(rc("aws_instance.web", ["delete", "update"], {"ami": "a"}, {"ami": "b"})),
                ["*"],
                {},
                [DESTRUCTIVE, UNRECOGNIZED],
            ),
            ("unknown action", plan(rc("aws_instance.web", ["frobnicate"], {}, {})), ["*"], {}, [UNRECOGNIZED]),
            ("iam", plan(POLICY), ["*"], {}, [IAM]),
            ("iam allowed", plan(POLICY), ["*"], {"allow_iam": True}, []),
            ("iam with only network allowed", plan(POLICY), ["*"], {"allow_network": True}, [IAM]),
            ("network", plan(RULE), ["*"], {}, [NETWORK]),
            ("network allowed", plan(RULE), ["*"], {"allow_network": True}, []),
            ("network with only iam allowed", plan(RULE), ["*"], {"allow_iam": True}, [NETWORK]),
            ("both", plan(POLICY, RULE), ["*"], {}, [IAM, NETWORK]),
            ("both, iam allowed", plan(POLICY, RULE), ["*"], {"allow_iam": True}, [NETWORK]),
            ("both, network allowed", plan(POLICY, RULE), ["*"], {"allow_network": True}, [IAM]),
            ("both allowed", plan(POLICY, RULE), ["*"], {"allow_iam": True, "allow_network": True}, []),
            ("computed policy, no configuration", plan(QUEUE), ["*"], {}, [IAM]),
            (
                "computed policy, configuration sets it",
                plan(QUEUE, configuration=config(res("aws_sqs_queue.q", name=SET, policy=SET))),
                ["*"],
                {},
                [IAM],
            ),
            (
                "computed policy, configuration lacks the resource",
                plan(QUEUE, configuration=config(res("aws_sqs_queue.other", name=SET))),
                ["*"],
                {},
                [IAM],
            ),
            (
                "computed policy, configuration is not an object",
                plan(QUEUE, configuration=[]),
                ["*"],
                {},
                [IAM],
            ),
            (
                "computed policy the configuration does not set passes",
                plan(QUEUE, configuration=config(res("aws_sqs_queue.q", name=SET))),
                ["*"],
                {},
                [],
            ),
            (
                "module resource under for_each with a computed policy",
                plan(
                    MODULE_QUEUE,
                    configuration=config(
                        calls={"app": {"module": config(res("aws_sqs_queue.q", name=SET, policy=SET))["root_module"]}}
                    ),
                ),
                ["module.app*"],
                {},
                [IAM],
            ),
            (
                "module resource, module call missing from the configuration",
                plan(MODULE_QUEUE, configuration=config(res("aws_sqs_queue.q", name=SET))),
                ["module.app*"],
                {},
                [IAM],
            ),
            (
                "module resource, computed policy not set passes",
                plan(
                    MODULE_QUEUE,
                    configuration=config(
                        calls={"app": {"module": config(res("aws_sqs_queue.q", name=SET))["root_module"]}}
                    ),
                ),
                ["module.app*"],
                {},
                [],
            ),
            (
                "unknown attribute in a block the configuration does not list",
                plan(
                    rc(
                        "aws_instance.web",
                        ["create"],
                        None,
                        {"ami": "a", "rule": [{}]},
                        {"rule": [{"cidr_blocks": True}]},
                    ),
                    configuration=config(res("aws_instance.web", ami=SET)),
                ),
                ["*"],
                {},
                [NETWORK],
            ),
            (
                "unknown attribute set inside a configured block",
                plan(
                    rc(
                        "aws_instance.web",
                        ["create"],
                        None,
                        {"ami": "a", "rule": [{}]},
                        {"rule": [{"cidr_blocks": True}]},
                    ),
                    configuration=config(res("aws_instance.web", ami=SET, rule=[{"cidr_blocks": SET}])),
                ),
                ["*"],
                {},
                [NETWORK],
            ),
            (
                "computed attribute inside a configured block passes",
                plan(
                    rc(
                        "aws_instance.web",
                        ["create"],
                        None,
                        {"ami": "a", "disk": [{"size": 8}]},
                        {"disk": [{"role": True}]},
                    ),
                    configuration=config(res("aws_instance.web", ami=SET, disk=[{"size": SET}])),
                ),
                ["*"],
                {},
                [],
            ),
            (
                "public access block switched off on create",
                plan(rc("aws_s3_account_setting.x", ["create"], None, {"restrict_public_buckets": False})),
                ["*"],
                {},
                [NETWORK],
            ),
            (
                "nested public flag turned on",
                plan(
                    rc(
                        "aws_eks_cluster.main",
                        ["update"],
                        {"vpc_config": [eks]},
                        {"vpc_config": [dict(eks, endpoint_public_access=True)]},
                    )
                ),
                ["*"],
                {},
                [NETWORK],
            ),
            (
                "nested world-open range",
                plan(
                    rc(
                        "aws_eks_cluster.main",
                        ["update"],
                        {"vpc_config": [eks]},
                        {"vpc_config": [dict(eks, public_access_cidrs=["0.0.0.0/0"])]},
                    )
                ),
                ["*"],
                {},
                [NETWORK],
            ),
            (
                "nested iam attribute on create",
                plan(
                    rc("aws_instance.web", ["create"], None, {"ami": "a", "spec": [{"service_account_name": "admin"}]})
                ),
                ["*"],
                {},
                [IAM],
            ),
            (
                "list fully known in after_unknown passes",
                plan(
                    rc(
                        "aws_instance.web",
                        ["update"],
                        {"instance_type": "a", "vpc_security_group_ids": ["sg-1"]},
                        {"instance_type": "b", "vpc_security_group_ids": ["sg-1"]},
                        {"vpc_security_group_ids": [False]},
                    )
                ),
                ["*"],
                {},
                [],
            ),
            (
                "unknown leaf inside a list on update",
                plan(
                    rc(
                        "aws_instance.web",
                        ["update"],
                        {"vpc_security_group_ids": ["sg-1"]},
                        {"vpc_security_group_ids": ["sg-1"]},
                        {"vpc_security_group_ids": [False, True]},
                    )
                ),
                ["*"],
                {},
                [NETWORK],
            ),
            ("benign instance create passes", plan(INSTANCE, configuration=INSTANCE_CONFIG), ["*"], {}, []),
            ("benign database create passes", plan(DATABASE), ["*"], {}, []),
        ]
        for name, p, scope, flags, want in cases:
            with self.subTest(name):
                got = predicate(p, scope, **flags)
                self.assertEqual(got["pass"], not want, got["reasons"])
                self.assertEqual(len(got["reasons"]), len(want), got["reasons"])
                for reason, part in zip(got["reasons"], want, strict=True):
                    self.assertIn(part, reason)

    def test_malformed_change_is_unrecognized(self):
        good = TAGS["change"]
        cases = {
            "no change key": None,
            "empty change": {},
            "change is a list": [],
            "actions missing": {"before": {}, "after": {}},
            "actions empty": dict(good, actions=[]),
            "actions is a string": dict(good, actions="update"),
            "actions holds a number": dict(good, actions=[1]),
            "before is a string": dict(good, before="x"),
            "after is a list": dict(good, after=[]),
            "after_unknown is a list": dict(good, after_unknown=[True]),
        }
        for name, change in cases.items():
            with self.subTest(name):
                entry = {"address": "aws_db_instance.x", "type": "aws_db_instance"}
                if change is not None:
                    entry["change"] = change
                r = idstack.summarize_plan(plan(entry), ["*"], True)
                self.assertEqual(r["counts"], {"unrecognized": 1})
                self.assertFalse(r["predicate"]["pass"])
                self.assertIn(UNRECOGNIZED, r["predicate"]["reasons"][0])

    def test_scope_matches_addresses_literally(self):
        cases = [
            ("aws_instance.web[0]", "aws_instance.web[0]", True),
            ("aws_instance.web[0]", "aws_instance.web0", False),
            ("aws_instance.web[01]", "aws_instance.web[0]", False),
            ('module.app["eu"].aws_instance.web', 'module.app["eu"].aws_instance.web', True),
            ('module.app["eu"].*', 'module.app["eu"].aws_instance.web', True),
            ('module.app["eu"].*', 'module.app["us"].aws_instance.web', False),
            ("aws_instance.web[*]", "aws_instance.web[3]", True),
            ("aws_instance.web?", "aws_instance.web1", True),
            ("aws_instance.web", "aws_instance.web2", False),
            ("aws_instance.*", "module.x.aws_instance.web", False),
        ]
        for pattern, address, inside in cases:
            with self.subTest(pattern=pattern, address=address):
                r = idstack.summarize_plan(plan(dict(TAGS, address=address)), [pattern], True)
                self.assertEqual(r["out_of_scope"], [] if inside else [address])
                self.assertEqual(r["predicate"]["pass"], inside)

    def test_type_lists(self):
        cases = {
            "network": [
                "aws_eip",
                "aws_eip_association",
                "azurerm_public_ip",
                "aws_lambda_function_url",
                "aws_cloudfront_distribution",
                "kubernetes_service",
                "kubernetes_service_v1",
            ],
            "stateful": [
                "aws_redshift_cluster",
                "aws_neptune_cluster",
                "aws_opensearch_domain",
                "aws_msk_cluster",
                "aws_ecr_repository",
                "google_bigquery_dataset",
                "google_spanner_instance",
                "azurerm_key_vault",
                "kubernetes_namespace",
                "kubernetes_stateful_set",
            ],
        }
        for key, types in cases.items():
            for rtype in types:
                with self.subTest(rtype):
                    r = idstack.summarize_plan(plan(rc(f"{rtype}.x", ["create"], None, {"name": "x"})), ["*"], False)
                    self.assertEqual(r[key], [f"{rtype}.x"])
        r = idstack.summarize_plan(
            plan(rc("kubernetes_service_account.x", ["create"], None, {"name": "x"})), ["*"], False
        )
        self.assertEqual(r["network"], [])

    def test_pod_spec_policies_are_not_iam(self):
        spec = [
            {"restart_policy": "Always", "dns_policy": "ClusterFirst", "container": [{"image_pull_policy": "Always"}]}
        ]
        r = idstack.summarize_plan(
            plan(rc("kubernetes_deployment.app", ["create"], None, {"spec": spec})), ["*"], False
        )
        self.assertEqual(r["iam"], [])
        top = rc("aws_instance.web", ["create"], None, {"restart_policy": "Always"})
        self.assertEqual(idstack.summarize_plan(plan(top), ["*"], False)["iam"], ["aws_instance.web"])

    def test_fixtures(self):
        both = {"allow_iam": True, "allow_network": True}
        cases = [
            ("create-only", ["*"], {}, []),
            ("replace-db", ["*"], {}, [DESTRUCTIVE]),
            ("iam-widen", ["*"], {}, [IAM, NETWORK]),
            ("iam-widen", ["*"], both, []),
            ("out-of-scope", ["module.web.*"], {}, ["outside the scope"]),
            ("out-of-scope", ["module.web.*", "module.billing.*"], {}, []),
        ]
        for name, scope, flags, want in cases:
            with self.subTest(name, scope=scope, flags=flags):
                got = predicate(json.loads((PLANS / f"{name}.plan.json").read_text()), scope, **flags)
                self.assertEqual(len(got["reasons"]), len(want), got["reasons"])
                for reason, part in zip(got["reasons"], want, strict=True):
                    self.assertIn(part, reason)


class DiffTest(unittest.TestCase):
    def test_truncation_is_marked_and_risky_keys_come_first(self):
        after = {f"attr_{i:02}": i for i in range(30)} | {"zz_policy": "p", "zz_public": True}
        for name, change, body in (
            ("create", {"actions": ["create"], "before": None, "after": after}, lambda d: d),
            ("delete", {"actions": ["delete"], "before": after, "after": None}, lambda d: d["deleted"]),
        ):
            with self.subTest(name):
                diff = idstack.change_diff(change)
                self.assertEqual(diff["(truncated)"], "12 more changed attribute(s) not shown")
                self.assertEqual(list(body(diff))[:2], ["zz_policy", "zz_public"])
                self.assertEqual(len(body(diff)) - (name == "create"), 20)

    def test_small_diffs_carry_no_marker(self):
        cases = [
            ("create with nothing known", {"actions": ["create"], "before": None, "after": {}}, {}),
            (
                "create with only unknowns",
                {"actions": ["create"], "before": None, "after": {}, "after_unknown": {"id": True}},
                {"id": "(known after apply)"},
            ),
            ("delete", {"actions": ["delete"], "before": {"a": 1}, "after": None}, {"deleted": {"a": 1}}),
            (
                "known list is not a change",
                {
                    "actions": ["update"],
                    "before": {"a": [1], "b": 1},
                    "after": {"a": [1], "b": 2},
                    "after_unknown": {"a": [False]},
                },
                {"b": {"before": 1, "after": 2}},
            ),
        ]
        for name, change, want in cases:
            with self.subTest(name):
                self.assertEqual(idstack.change_diff(change), want)

    def test_text_without_changes(self):
        self.assertEqual(
            idstack.plan_summary_text(idstack.summarize_plan({}, [], False)).splitlines()[0], "counts: none"
        )


class CliTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def run_cli(self, *args, stdin=None):
        return subprocess.run(
            [sys.executable, str(BIN), "plan-summary", *args], input=stdin, capture_output=True, text=True
        )

    def test_bad_input_exits_2_with_one_object(self):
        good = str(PLANS / "create-only.plan.json")
        comments = self.tmp / "comments.txt"
        comments.write_text("# nothing\n\n   # indented\n")
        cases = [
            ("no scope", [good, "--predicate"], None),
            ("empty scope", [good, "--predicate", "--scope", ""], None),
            ("scope file with comments only", [good, "--predicate", "--scope-file", str(comments)], None),
            ("missing scope file", [good, "--predicate", "--scope-file", str(self.tmp / "none.txt")], None),
            ("scope file is a directory", [good, "--scope-file", str(self.tmp)], None),
            ("list on stdin", ["-"], "[]"),
            ("string on stdin", ["-", "--scope", "*", "--predicate"], '"plan"'),
            ("null resource_changes", ["-"], '{"resource_changes": null}'),
            ("resource_changes is an object", ["-"], '{"resource_changes": {}}'),
            ("entry is not an object", ["-"], '{"resource_changes": [1]}'),
            ("entry without an address", ["-"], '{"resource_changes": [{"type": "t", "change": {}}]}'),
            ("address is a list", ["-"], '{"resource_changes": [{"address": [], "type": "t"}]}'),
            ("not json", ["-"], "{"),
            ("nested too deeply", ["-"], "[" * 100000),
        ]
        for name, args, stdin in cases:
            with self.subTest(name):
                r = self.run_cli(*args, "--json", stdin=stdin)
                self.assertEqual(r.returncode, 2, r.stderr)
                out = json.loads(r.stdout)
                self.assertEqual(list(out), ["ok", "errors"])
                self.assertFalse(out["ok"])
                self.assertEqual(len(out["errors"]), 1)
                self.assertNotIn("Traceback", r.stderr)
                plain = self.run_cli(*args, stdin=stdin)
                self.assertEqual((plain.returncode, plain.stdout), (2, ""))
                self.assertTrue(plain.stderr.startswith("error: "), plain.stderr)

    def test_scope_file_and_stdin(self):
        scope = self.tmp / "scope.txt"
        scope.write_text("# web tier\n  # indented comment\n\n  module.web.*  \n")
        text = (PLANS / "out-of-scope.plan.json").read_text()
        cases = [
            ("scope file leaves one change outside", ["--scope-file", str(scope)], 1, ["module.web.*"]),
            (
                "scope file plus --scope covers both",
                ["--scope-file", str(scope), "--scope", "module.billing.*"],
                0,
                ["module.billing.*", "module.web.*"],
            ),
        ]
        for name, args, code, want in cases:
            with self.subTest(name):
                r = self.run_cli("-", *args, "--predicate", "--json", stdin=text)
                self.assertEqual(r.returncode, code, r.stderr)
                out = json.loads(r.stdout)
                self.assertEqual(out["predicate"]["scope"], want)
                self.assertEqual(out["ok"], code == 0)

    def test_summary_without_predicate_needs_no_scope(self):
        r = self.run_cli(str(PLANS / "replace-db.plan.json"), "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["destructive"], ["aws_db_instance.orders"])


if __name__ == "__main__":
    unittest.main()
