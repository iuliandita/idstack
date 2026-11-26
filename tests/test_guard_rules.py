"""Guard rule coverage: one command each rule holds and one read-only command it lets through.

The strings below are test data for `classify`. Nothing here is executed.
"""

import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin/idstack"
_loader = importlib.machinery.SourceFileLoader("idstack_guard_rules_cli", str(BIN))
_spec = importlib.util.spec_from_loader("idstack_guard_rules_cli", _loader)
idstack = importlib.util.module_from_spec(_spec)
_loader.exec_module(idstack)

# rule, a command it holds, a command of the same tool that passes
RULES = [
    ("terraform refresh", "terraform refresh", "terraform validate"),
    ("terraform test", "tofu test", "terraform fmt -check"),
    ("terraform init, state migration", "terraform init -migrate-state", "terraform init -backend=false"),
    ("aws key deletion", "aws kms schedule-key-deletion --key-id k", "aws kms list-keys"),
    ("aws address release", "aws ec2 release-address --allocation-id a", "aws ec2 describe-addresses"),
    ("aws IAM grant", "aws iam attach-role-policy --role-name r --policy-arn p", "aws iam list-roles"),
    (
        "aws policy write",
        "aws s3api put-bucket-policy --bucket b --policy file://p.json",
        "aws s3api get-bucket-policy --bucket b",
    ),
    (
        "aws security group open",
        "aws ec2 authorize-security-group-ingress --group-id g --cidr 0.0.0.0/0 --port 22 --protocol tcp",
        "aws ec2 describe-security-groups",
    ),
    (
        "aws deploy",
        "aws cloudformation deploy --stack-name s --template-file t.yml",
        "aws cloudformation describe-stacks",
    ),
    (
        "aws deploy, service named deploy",
        "aws deploy create-deployment --application-name a",
        "aws deploy list-applications",
    ),
    (
        "aws function deploy",
        "aws lambda update-function-code --function-name f --zip-file fileb://f.zip",
        "aws lambda list-functions",
    ),
    (
        "aws remote command",
        "aws ssm send-command --instance-ids i --document-name d",
        "aws ssm describe-instance-information",
    ),
    (
        "aws public database",
        "aws rds modify-db-instance --db-instance-identifier d --publicly-accessible",
        "aws rds describe-db-instances",
    ),
    (
        "aws public ACL",
        "aws s3 cp site.html s3://bucket/ --acl=public-read",
        "aws s3 cp site.html s3://bucket/ --acl=private",
    ),
    (
        "aws public ACL, separate value",
        "aws s3api put-object --bucket b --key k --acl public-read",
        "aws s3 ls s3://bucket/",
    ),
    (
        "gcloud IAM grant",
        "gcloud projects add-iam-policy-binding p --member=user:a@example.com --role=roles/viewer",
        "gcloud projects get-iam-policy p",
    ),
    (
        "gcloud IAM grant removal",
        "gcloud compute instances remove-iam-policy-binding vm --member=user:a@example.com --role=roles/viewer",
        "gcloud compute instances list",
    ),
    (
        "gcloud service account key",
        "gcloud iam service-accounts keys create key.json --iam-account sa@example.com",
        "gcloud iam service-accounts keys list --iam-account sa@example.com",
    ),
    (
        "gcloud firewall open",
        "gcloud compute firewall-rules create allow-ssh --allow tcp:22",
        "gcloud compute firewall-rules list",
    ),
    ("gcloud deploy", "gcloud beta run deploy svc --image img", "gcloud run services list"),
    ("gcloud deploy, group named deploy", "gcloud deploy releases create r1", "gcloud deploy delivery-pipelines list"),
    ("gcloud remote command", "gcloud compute ssh vm --command uptime", "gcloud compute instances describe vm"),
    (
        "gcloud public service",
        "gcloud run services update svc --allow-unauthenticated",
        "gcloud run services describe svc",
    ),
    ("az delete with a suffix", "az storage blob delete-batch --source c", "az storage blob list -c c"),
    ("az role grant", "az role assignment create --assignee a --role Reader", "az role assignment list"),
    (
        "az firewall open",
        "az network nsg rule create -g rg --nsg-name n -n allow-ssh --priority 100",
        "az network nsg rule list -g rg",
    ),
    (
        "az server firewall open",
        "az sql server firewall-rule create -g rg -s srv -n all",
        "az sql server firewall-rule list -g rg -s srv",
    ),
    ("az deploy", "az deployment group create -g rg --template-file main.bicep", "az deployment group list -g rg"),
    ("az remote command", "az vm run-command invoke -g rg -n vm --command-id RunShellScript", "az vm list"),
    ("az public container", "az storage container create -n c --public-access blob", "az storage container list"),
    ("az delete", "az vm delete -g rg -n web", "az vm show -g rg -n web"),
    ("pulumi", "pulumi up --yes", "pulumi preview"),
    ("pulumi destroy", "pulumi -s prod destroy --yes", "pulumi stack ls"),
    ("helmfile", "helmfile -e prod apply", "helmfile -e prod diff"),
    ("eksctl", "eksctl delete cluster --name c", "eksctl get cluster"),
    ("gsutil", "gsutil -m rm -r gs://bucket/dir", "gsutil ls gs://bucket"),
    ("gsutil ACL", "gsutil iam ch allUsers:objectViewer gs://bucket", "gsutil iam get gs://bucket"),
    ("gsutil mirror with deletes", "gsutil -m rsync -r -d src gs://bucket", "gsutil -m rsync -r src gs://bucket"),
    ("vault delete", "vault kv delete secret/app", "vault kv get secret/app"),
    ("vault revoke", "vault lease revoke -prefix aws/creds", "vault read secret/data/app"),
    ("docker compose volumes", "docker compose -f stack.yml down -v", "docker compose ps"),
    ("docker compose volumes, long flag", "docker-compose down --volumes", "docker-compose down"),
    ("gh merge", "gh pr merge 12 --squash", "gh pr view 12"),
    ("gh workflow run", "gh workflow run release.yml", "gh run list"),
    ("gh rerun", "gh -R owner/repo run rerun 123", "gh run view 123"),
    ("glab merge", "glab mr merge 12", "glab mr view 12"),
    ("glab pipeline", "glab ci run", "glab ci list"),
    ("forge push limit", "gh pr merge 12", "git push origin feature"),
    ("remote rm", "ssh db1 'rm -rf /var/lib/app/cache'", "rm -rf build"),
    ("remote service", "ssh web1 sudo service nginx restart", "ssh web1 service nginx status"),
    ("remote kill", "ssh web1 kill -9 4242", "kill -9 4242"),
    ("remote dd", "ssh nas1 dd if=/dev/zero of=/dev/sdb", "dd if=/dev/zero of=test.img bs=1M count=1"),
    ("remote mkfs", "ssh nas1 mkfs.ext4 /dev/sdb1", "ssh nas1 lsblk"),
    ("remote zfs destroy", "ssh nas1 zfs destroy tank/old", "ssh nas1 zfs list"),
    ("remote lvremove", "ssh nas1 lvremove -y vg0/old", "ssh nas1 lvs"),
    ("remote docker rm", "ssh web1 docker rm -f web", "ssh web1 docker ps"),
    ("remote docker rm, run locally", "ssh web1 docker volume rm data", "docker rm -f web"),
    ("remote package removal", "ssh web1 sudo apt-get -y remove nginx", "ssh web1 sudo apt-get update"),
    ("remote package removal by flag", "ssh web1 sudo pacman -Rns nginx", "ssh web1 pacman -Q"),
    (
        "remote rm in a heredoc",
        "ssh db1 <<'EOF'\nrm -rf /var/lib/app/cache\nEOF",
        "ssh db1 <<'EOF'\nls /var/lib/app\nEOF",
    ),
    ("remote rm on a pipe", "echo 'rm -rf /srv/data' | ssh db1", "echo 'rm -rf build' | cat"),
    ("rsync delete to a remote", "rsync -a --delete src/ web1:/srv/site/", "rsync -a --delete src/ dst/"),
    (
        "rsync delete to a remote, longer flag",
        "rsync -a --delete-after src/ rsync://web1/site/",
        "rsync -a src/ web1:/srv/site/",
    ),
    (
        "rsync delete, pulled from a remote",
        "rsync -a --del src/ web1:",
        "rsync -az --delete web1:/var/backups/ ./backups/",
    ),
    ("guard settings named to the CLI", "tee -a guard.json", "idstack guard test 'rm ~/.config/idstack/guard.json'"),
    ("guard settings removed", "rm ~/.config/idstack/guard.json", "cat ~/.config/idstack/guard.json"),
    (
        "guard settings rewritten",
        'echo \'{"mode": "off"}\' > ~/.config/idstack/guard.json',
        "jq .mode ~/.config/idstack/guard.json",
    ),
    ("guard settings truncated", "> ~/.config/idstack/guard.json", "ls -la ~/.config/idstack"),
    (
        "guard settings edited in place",
        "sed -i 's/ask/off/' \"$HOME/.config/idstack/guard.json\"",
        "grep -rn guard.json bin/idstack",
    ),
    (
        "guard approvals written by a script",
        "python3 -c \"open('guard-allow.json', 'w').write('{}')\"",
        "python3 bin/idstack build --check",
    ),
    (
        "guard approvals appended",
        "cat token.json >> ~/.local/state/idstack/guard-allow.json",
        "ls ~/.local/state/idstack",
    ),
    ("guard state directory removed", "rm -rf ~/.local/state/idstack", "git commit -m 'docs: explain guard.json'"),
    (
        "guard settings copied over",
        'sudo cp /tmp/g.json "${XDG_CONFIG_HOME}/idstack/guard.json"',
        "cp /tmp/g.json notes.json",
    ),
    ("guard settings through tee", "echo '{}' | tee ~/.config/idstack/guard.json", "echo '{}' | tee notes.json"),
]


class RuleTableTest(unittest.TestCase):
    rules = idstack.load_rules()

    def test_each_rule_holds_its_command(self):
        for name, held, _ in RULES:
            with self.subTest(name, cmd=held):
                self.assertTrue(idstack.classify(held, self.rules))

    def test_each_rule_passes_a_read(self):
        for name, _, passed in RULES:
            with self.subTest(name, cmd=passed):
                self.assertEqual(idstack.classify(passed, self.rules), [])

    def test_guard_files_in_a_configured_directory(self):
        with (
            mock.patch.object(idstack, "CONFIG_DIR", Path("/srv/guard/etc")),
            mock.patch.object(idstack, "STATE_DIR", Path("/srv/guard/state")),
        ):
            for cmd in ("rm -rf /srv/guard/etc", "touch /srv/guard/state/guard.log", "chmod 600 /srv/guard/etc/x"):
                with self.subTest(cmd):
                    self.assertEqual([h["verb"] for h in idstack.classify(cmd, self.rules)], ["files"])
            self.assertEqual(idstack.classify("ls /srv/guard/etc; rm -rf /srv/guardian", self.rules), [])

    def test_rule_file_shape(self):
        keys = {
            *("tools", "verbs", "any_verb_regex", "requires", "value_flags", "safe_flags", "safe_modules", "reason"),
            *("danger_flags", "remote_only", "remote_flags", "remote_target", "with_flags", "skip_words", "launcher"),
        }
        for rule in self.rules:
            with self.subTest(rule["tools"]):
                self.assertFalse(set(rule) - keys)
                self.assertTrue(rule["reason"])
                self.assertTrue("verbs" in rule or "any_verb_regex" in rule)


# command, held with no trusted hosts, held with devbox and buildbox trusted
TRUSTED = [
    ("rm behind ssh", "ssh devbox 'rm -rf /srv/x'", True, False),
    ("user and case ignored", "ssh -o BatchMode=yes ID@DEVBOX 'sudo -n kill 12; systemctl restart x'", True, False),
    ("shell payload", "ssh buildbox 'bash -c \"rm -rf /x\"'", True, False),
    ("heredoc", "ssh devbox <<'EOF'\nrm -rf /x\nEOF", True, False),
    ("pipe into ssh", "echo 'rm -rf /x' | ssh devbox", True, False),
    ("rsync delete to the host", "rsync -a --delete src/ devbox:/srv/", True, False),
    ("other host", "ssh prod 'rm -rf /srv/x'", True, True),
    ("trusted host first, other second", "ssh devbox ssh prod rm -rf x", True, True),
    ("other host first, trusted second", "ssh prod ssh devbox rm -rf x", True, True),
    ("rsync delete to another host", "rsync -a --delete src/ prod:/srv/", True, True),
    ("remote flag names no host", "ssh devbox systemctl -H prod stop x", True, True),
    ("infra tool behind the host", "ssh devbox 'terraform apply'", True, True),
    ("infra tool piped to the host", "echo 'kubectl delete ns x' | ssh devbox", True, True),
    ("plain ssh options", "ssh -o BatchMode=yes -p 2222 devbox rm x", True, False),
    ("options after the host", "ssh devbox -v -- rm x", True, False),
    ("HostName override", "ssh -o HostName=prod devbox rm x", True, True),
    ("HostName override, attached", "ssh -oHostName=prod devbox rm x", True, True),
    ("ProxyJump override", "ssh -o 'ProxyJump prod' devbox rm x", True, True),
    ("jump host", "ssh -J prod devbox rm x", True, True),
    ("other config file", "ssh -F cfg devbox rm x", True, True),
    ("override after the host", "ssh devbox -o ProxyCommand=x rm x", True, True),
    ("rsync over plain ssh", "rsync -e 'ssh -p 2222' -a --delete s/ devbox:/d/", True, False),
    ("rsync over a jump host", "rsync -e 'ssh -J prod' -a --delete s/ devbox:/d/", True, True),
    ("rsync over another program", "rsync -e ./wrap -a --delete s/ devbox:/d/", True, True),
    ("host-name lookalike", "ssh devbox.example.com 'rm -rf /x'", True, True),
]


class TrustedHostTest(unittest.TestCase):
    cfg = {"trusted_hosts": ["buildbox", "devbox"]}

    def test_remote_only_rules_skip_trusted_hosts(self):
        for name, cmd, plain, trusted in TRUSTED:
            with self.subTest(name, cmd=cmd):
                self.assertEqual(idstack.guard_decide(cmd, {})["match"], plain)
                self.assertEqual(idstack.guard_decide(cmd, self.cfg)["match"], trusted)

    def test_config_list_is_normalized(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        cases = [
            ('{"trusted_hosts": ["DEVBOX", "me@buildbox", ""]}', ["buildbox", "devbox"]),
            ('{"trusted_hosts": "devbox"}', []),
            ('{"trusted_hosts": ["devbox", 7]}', []),
        ]
        for text, want in cases:
            with self.subTest(text):
                (tmp / "guard.json").write_text(text)
                with mock.patch.object(idstack, "CONFIG_DIR", tmp):
                    self.assertEqual(idstack.guard_config()["trusted_hosts"], want)

    def test_trust_and_untrust(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        env = {**os.environ, "IDSTACK_CONFIG_DIR": str(tmp)}

        def cli(*argv: str) -> dict:
            r = subprocess.run(
                [sys.executable, str(BIN), "guard", *argv, "--json"], capture_output=True, text=True, env=env
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads(r.stdout)

        self.assertEqual(cli("trust", "devbox", "me@buildbox")["trusted_hosts"], ["buildbox", "devbox"])
        self.assertEqual(cli("untrust", "DEVBOX")["trusted_hosts"], ["buildbox"])
        self.assertEqual(cli("status")["config"]["trusted_hosts"], ["buildbox"])
        self.assertTrue(idstack.classify("idstack guard trust prod", idstack.load_rules()))
        r = subprocess.run([sys.executable, str(BIN), "guard", "trust", "--json"], capture_output=True, env=env)
        self.assertEqual(r.returncode, 2)


class CodexEntryTest(unittest.TestCase):
    """The entry `guard install --harness codex` writes runs the hook shim of the same checkout."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.env = {
            **os.environ,
            "HOME": str(self.tmp),
            "XDG_CONFIG_HOME": str(self.tmp / "config"),
            "IDSTACK_CONFIG_DIR": str(self.tmp / "idstack-config"),
            "IDSTACK_STATE_DIR": str(self.tmp / "idstack-state"),
            "CODEX_HOME": str(self.tmp / "codex"),
            "TYPESAFE_API_KEY": "",
        }
        self.env.pop("IDSTACK_GUARD_MODE", None)

    def cli(self, *argv: str) -> dict:
        r = subprocess.run(
            [sys.executable, str(BIN), *argv, "--json"],
            capture_output=True,
            text=True,
            env=self.env,
            stdin=subprocess.DEVNULL,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_entry_runs_the_shim_and_keeps_the_marker(self):
        self.cli("guard", "enable", "--mode", "ask")
        self.assertTrue(self.cli("guard", "install", "--harness", "codex")["changed"])
        text = (self.tmp / "codex/hooks.json").read_text()
        (group,) = json.loads(text)["hooks"]["PreToolUse"]
        command = group["hooks"][0]["command"]
        self.assertIn(str(ROOT / "hooks/guard_hook.py"), command)
        self.assertIn("idstack guard hook", command, "install.sh and guard_in_config look for this text")
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "terraform apply"}})
        r = subprocess.run(command, shell=True, capture_output=True, text=True, env=self.env, input=payload)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertFalse(self.cli("guard", "install", "--harness", "codex")["changed"])
        self.assertTrue(self.cli("guard", "uninstall", "--harness", "codex")["changed"])
        self.assertNotIn("idstack guard hook", (self.tmp / "codex/hooks.json").read_text())


if __name__ == "__main__":
    unittest.main()
