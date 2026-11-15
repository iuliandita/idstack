"""Guard parser and hook: what must be held and what must pass.

The strings below are test data for `classify`. Nothing here is executed.
"""

import ast
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin/idstack"
SHIM = ROOT / "hooks/guard_hook.py"
_loader = importlib.machinery.SourceFileLoader("idstack_guard_cli", str(BIN))
_spec = importlib.util.spec_from_loader("idstack_guard_cli", _loader)
idstack = importlib.util.module_from_spec(_spec)
_loader.exec_module(idstack)

DELETE = "kubectl delete ns prod"

MUST_HOLD = {
    "heredoc: cat piped to a shell": f"cat <<EOF | bash\n{DELETE}\nEOF",
    "heredoc: cat piped to a shell in a subshell": f"cat <<'EOF' | (cd /tmp && sh)\n{DELETE}\nEOF",
    "heredoc: cat piped to ssh": "cat <<'EOF' | ssh web1\nsudo systemctl restart nginx\nEOF",
    "heredoc: unquoted cat body with a command substitution": f"cat > notes.txt <<EOF\npods: $({DELETE})\nEOF",
    "heredoc: unquoted cat body with backticks": f"cat > notes.txt <<EOF\npods: `{DELETE}`\nEOF",
    "heredoc: fed to a shell": f"bash <<EOF\n{DELETE}\nEOF",
    "heredoc: fed to a shell behind sudo, tab-stripped": f"sudo bash <<-'EOF'\n\t{DELETE}\n\tEOF",
    "heredoc: fed to ssh": f"ssh db1 <<'EOF'\n{DELETE}\nEOF",
    "heredoc: fed to a launcher the guard does not know": f"docker exec -i box sh <<'EOF'\n{DELETE}\nEOF",
    "here-string: fed to a shell": f"bash <<< '{DELETE}'",
    "pipe: echo into a shell": f"echo '{DELETE}' | bash",
    "pipe: echo into a shell behind sudo": f"echo '{DELETE}' | sudo sh -s",
    "pipe: echo into ssh": "echo 'systemctl restart nginx' | ssh web1",
    "pipe: echo into a remote shell": "echo 'systemctl restart nginx' | ssh web1 sudo bash",
    "comment: apostrophe after a shell payload": f'bash -c "{DELETE}" # it\'s fine',
    "comment: apostrophe after an ssh payload": 'ssh web1 "sudo systemctl restart nginx" # don\'t forget web2',
    "comment: a quoted # on the first of two lines": f'echo "# cleanup\n" ; {DELETE} # don\'t wait',
    "comment: unparsable and names a rule tool": "echo ok # don't run kubectl here",
    "comment: a safe flag inside a comment": "ansible-playbook site.yml # --check",
    "unparsable text that names a rule tool": f"{DELETE}; echo 'unterminated",
    "launcher: xargs": f"kubectl get ns -o name | xargs {DELETE.removesuffix(' ns prod')}",
    "launcher: xargs with a value flag": "ls *.yml | xargs -n 1 ansible-playbook",
    "launcher: uv run": "uv run ansible-playbook site.yml",
    "launcher: uv run with a packager verb later on": "uv run ansible-playbook site.yml --tags install",
    "launcher: aws-vault exec": "aws-vault exec prod -- ansible-playbook site.yml",
    "launcher: aws-vault exec with a verb rule": "aws-vault exec prod -- terraform destroy -auto-approve",
    "launcher: find -exec": "find . -name '*.yaml' -exec kubectl delete -f {} \\;",
    "launcher: flock": "flock /tmp/tf.lock terraform apply",
    "launcher: setsid": "setsid ansible-playbook site.yml",
    "launcher: systemd-run": "systemd-run --user terraform apply -auto-approve",
    "launcher: direnv exec": "direnv exec . tofu apply",
    "launcher: docker run": "docker run --rm hashicorp/terraform apply -auto-approve",
    "launcher: container named like the tool": "docker exec terraform terraform apply",
    "launcher: su -c": f"su - deploy -c '{DELETE}'",
    "launcher: sudo su --command=": f"sudo su --command='{DELETE}' deploy",
    "launcher: watch with a quoted command": f"watch -n 5 '{DELETE}'",
    "launcher: backticks": f"echo `{DELETE}`",
    "launcher: command substitution in a string": f'echo "result: $({DELETE})"',
    "launcher: process substitution": f"diff <({DELETE}) /dev/null",
    "launcher: function body": f"f() {{ {DELETE}; }}; f",
    "launcher: leading redirection": f">/dev/null {DELETE}",
    "launcher: redirection between words": f"2>&1 >out.log {DELETE}",
    "payload: eval": 'eval "terraform destroy -auto-approve"',
    "payload: fish -c": f"fish -c '{DELETE}'",
    "payload: -c then --": f"bash -c -- '{DELETE}'",
    "payload: -c after an option with a value": f"bash -eo pipefail -c '{DELETE}'",
    "payload: -c with no command": "bash -c",
    "payload: su -c with no command": "su deploy -c",
    "payload: xargs sh -c": f"ls | xargs sh -c '{DELETE}'",
    "payload: shell behind a launcher": f"docker run --rm box sh -c '{DELETE}'",
    "payload: ANSI-C quoting": f"bash -c $'{DELETE}'",
    "verb after an unknown flag: argocd": "argocd --kube-context prod app sync x",
    "verb after two unknown flags: argocd": "argocd --port-forward-namespace argocd --grpc-web app delete prod-api",
    "verb after an unknown flag: kubectl": "kubectl -l app=x delete pods",
    "verb after an unknown flag: helm": "helm -f values.yaml upgrade x .",
    "nesting at the limit still reads the command": "ssh a ssh b ssh c ssh d reboot",
    "nesting past the limit": "ssh a ssh b ssh c ssh d ssh e uptime",
    "ansible: the last -m wins": "ansible all -m ping -m shell -a reboot",
    "ansible: -m joined to its value": "ansible all -m ping -mshell -a reboot",
    "array literal does not hide the next command": f"hosts=(a b); {DELETE}",
    "case branch inside a quoted substitution": f'echo "$(case $x in a) {DELETE};; esac)"',
    "case branch": f"case $x in\n  a|b) {DELETE};;\nesac",
    "pipe: echo into a subshell that ends in a shell": f"echo '{DELETE}' | (cd /tmp && sh)",
    "wrapper: watch behind sudo": "sudo watch -n 5 kubectl delete pod x",
    "stdin arguments: verb on a pipe": "echo delete ns prod | xargs kubectl",
    "stdin arguments: verb from printf": "printf '%s\\n' delete ns prod | xargs kubectl",
    "stdin arguments: verb in a heredoc": "xargs kubectl <<'EOF'\ndelete ns prod\nEOF",
    "stdin arguments: verb in a here-string": "xargs kubectl <<< 'delete ns prod'",
    "stdin arguments: read from a file": "xargs -a verbs.txt kubectl",
    "stdin arguments: a pipe the guard cannot read": "cat verbs.txt | xargs kubectl",
    "stdin arguments: no input the guard can see": "xargs -n 1 kubectl",
    "stdin arguments: placeholder in the verb position": "echo delete | xargs -I{} kubectl {} ns prod",
    "stdin arguments: placeholder with unreadable input": "cat verbs.txt | xargs -I % kubectl % ns prod",
    "stdin arguments: second word of a verb": "cat verbs.txt | xargs kubectl rollout",
    "stdin arguments: after a flag that takes a value": "cat verbs.txt | xargs kubectl -n",
    "stdin arguments: a rule that reads every argument": "cat keys.txt | xargs aws s3",
    "stdin arguments: shell payload that takes them": "cat verbs.txt | xargs sh -c 'kubectl \"$@\"' _",
    "stdin arguments: parallel": "echo delete ns prod | parallel kubectl",
    "stdin arguments: parallel with its own list": "parallel -j 2 kubectl {} ns prod ::: delete",
    "utility runs a command: sed e": f"sed -n '1e {DELETE}' notes.txt",
    "utility runs a command: sed s///e": f"sed 's/x/{DELETE}/e' notes.txt",
    "utility runs a command: sed e on piped text": f"echo '{DELETE}' | sed e",
    "utility runs a command: sed script on stdin": f"sed -f /dev/stdin notes.txt <<'EOF'\n1e {DELETE}\nEOF",
    "utility runs a command: awk system": f"awk 'BEGIN {{ system(\"{DELETE}\") }}'",
    "utility runs a command: awk pipe": f"awk 'BEGIN {{ print | \"{DELETE}\" }}'",
    "utility runs a command: awk getline": f"gawk 'BEGIN {{ \"{DELETE}\" | getline x }}'",
    "utility runs a command: awk on piped text": f"echo '{DELETE}' | awk '{{ system($0) }}'",
    "utility runs a command: awk program on stdin": f"awk -f /dev/stdin <<'EOF'\nBEGIN {{ system(\"{DELETE}\") }}\nEOF",
    "utility runs a command: tar --to-command": f"tar -xf a.tar --to-command='{DELETE}'",
    "utility runs a command: tar checkpoint action": (
        f"tar -cf /dev/null . --checkpoint=1 --checkpoint-action=exec='{DELETE}'"
    ),
    "utility runs a command: tar -I": "tar -I 'ansible-playbook site.yml' -xf a.tar",
    "utility runs a command: tar, abbreviated option": f"tar -xf a.tar --to-c '{DELETE}'",
    "utility runs a command: rsync -e": "rsync -av -e 'kubectl exec -i web-0 --' src/ web-0:/srv/",
    "utility runs a command: rsync -e in a bundle": f"rsync -ave 'sh -c \"{DELETE}\"' src/ h:dst/",
    "utility runs a command: rsync --rsh": f"rsync -a --rsh='sh -c \"{DELETE}\"' src/ h:dst/",
    "utility runs a command: fd -x": "fd -e yml . -x ansible-playbook",
    "utility runs a command: fd -x with a shell": f"fd . -x sh -c '{DELETE}'",
    "utility runs a command: rg --pre": "rg --pre ansible-playbook todo .",
    "utility runs a command: man -P": f"man -P '{DELETE}' ls",
    "utility runs a command: sort": f"sort --compress-program='{DELETE}' big.txt",
    "utility runs a command: scp -o": f"scp -o ProxyCommand='{DELETE}' f h:/tmp/",
    "utility runs a command: scp -S": "scp -S ansible-playbook f h:/tmp/",
    "utility runs a command: wget": f"wget --use-askpass='{DELETE}' https://example.com/x",
    "utility runs a command: bat": f"bat --pager='{DELETE}' notes.txt",
    "shell reads stdin through an operand: -": f"echo '{DELETE}' | bash -",
    "shell reads stdin through an operand: /dev/stdin": f"echo '{DELETE}' | bash /dev/stdin",
    "shell reads stdin through an operand: /dev/fd/0": f"echo '{DELETE}' | sh -e /dev/fd/0",
    "shell reads stdin through an operand: /proc/self/fd/0": f"echo '{DELETE}' | sudo bash /proc/self/fd/0",
    "shell reads stdin through an operand: source": f"echo '{DELETE}' | source /dev/stdin",
    "shell reads stdin through an operand: dot": f"echo '{DELETE}' | . /dev/stdin",
}

MUST_PASS = {
    "heredoc: prose for a file names a delete": f"cat > body.md <<'EOF'\nThis stops `{DELETE}` early.\nIt's done.\nEOF",
    "heredoc: commit message in a substitution": (
        f"git commit -m \"$(cat <<'EOF'\nfix(guard): hold {DELETE} behind xargs\n\nit's held now\nEOF\n)\""
    ),
    "heredoc: PR body on stdin": f"gh pr create --title x --body-file - <<'EOF'\nholds {DELETE}; that's all\nEOF",
    "heredoc: unquoted with an apostrophe": "cat <<EOF > notes.txt\nit's fine, $USER\nEOF",
    "heredoc: unquoted, names a delete in plain prose": f"cat <<EOF > notes.txt\nnever run {DELETE} here\nEOF",
    "heredoc: fed to tee behind sudo": f"sudo tee /etc/motd <<'EOF'\ndo not {DELETE}\nEOF",
    "heredoc: python with an apostrophe": "python3 - <<'EOF'\nprint(\"it's\")  # isn't shell\nEOF",
    "here-string: fed to grep": f"grep -c delete <<< '{DELETE}'",
    "comment: apostrophe after echo": "echo done # it's fine",
    "comment: apostrophe after grep": "grep -c foo log.txt # don't count blanks",
    "comment: names a rule tool without a verb": "ls -la # kubectl get output goes here",
    "jq filter and an apostrophe": "kubectl get pods -o json | jq -r '.items[] | .metadata.name' # that's all",
    "jq filter with a quoted apostrophe": 'jq -r ".[] | select(.note == \\"it\'s\\")" notes.json',
    "echo of a destructive command": "echo terraform destroy",
    "printf of a destructive command": f"printf '%s\\n' {DELETE}",
    "grep for a quoted delete": 'grep -rn "kubectl delete" docs',
    "commit message naming a destroy": 'git commit -m "docs: explain terraform destroy"',
    "tool name as an argument: ls": "ls ansible",
    "tool name as an argument: cd": "cd infra/ansible && ls",
    "tool name as an argument: git": "git add ansible && git diff --stat ansible",
    "tool name as an argument: find": "find . -name ansible -type d",
    "tool name as an argument: which": "which ansible ansible-playbook",
    "tool name as an argument: command -v": "command -v ansible",
    "tool name as an argument: pip": "pip install ansible",
    "tool name as an argument: uv pip": "uv pip install --upgrade ansible",
    "tool name as an argument: apt": "sudo apt-get -y install ansible",
    "tool name as an argument: brew": "brew install ansible",
    "tool name as an argument: namespace": "kubectl -n ansible get pods",
    "tool name as an argument: flag value": "terraform -chdir=infra/ansible plan",
    "tool name as an argument: bucket path": "aws s3 ls s3://example-bucket/ansible",
    "tool name as an argument: volume": "docker run -v ./ansible:/ansible box ls",
    "tool name as an argument: loop words": "for d in terraform ansible; do ls $d; done",
    "tool name as an argument: array": "dirs=(ansible terraform); ls",
    "tool name as an argument: case patterns": "case $x in terraform) echo t;; ansible) echo a;; esac",
    "case inside a substitution": 'x=$(case "$env" in prod) echo a;; *) echo b;; esac); echo "$x"',
    "wrapper: watch of a read": "watch -n 5 kubectl get pods",
    "tool name as an argument: xargs grep": "ls | xargs grep -l ansible",
    "remote: last reboot": "ssh h last reboot",
    "remote: read-only pipeline": "ssh h 'uptime; who -b; last reboot | head -3'",
    "pipe: read-only output into a remote file": "kubectl get pods | ssh h 'cat > /tmp/pods.txt'",
    "pipe: a shell that names no rule tool": "curl -fsSL https://example.com/install.sh | sh",
    "pipe: grep for a shell name": "kubectl get pods | grep sh",
    "shell script with its own -c flag": "bash scripts/build.sh -c",
    "shell payload that only reads": "bash -lc 'kubectl get pods -A | wc -l'",
    "process substitution that only reads": "diff <(kubectl get cm a -o yaml) <(kubectl get cm b -o yaml)",
    "substitution that only reads": 'echo "region: $(terraform output -raw region)"',
    "arithmetic and parameter expansion": 'echo $((1 + 2)) "${x:-none}" ${#items[@]}',
    "redirections": "terraform plan -out=tfplan 2>&1 | tail -40 >plan.txt",
    "verb word as a flag value": "kubectl get pods --sort-by delete",
    "verb word after the subcommand": "kubectl get delete",
    "ansible: the last -m is a safe module": "ansible all -m shell -m ping",
    "python one-liner naming a tool": "python3 -c \"import subprocess; print('kubectl delete')\"",
    "guard test of a quoted command": f"idstack guard test '{DELETE}'",
    "stdin arguments: grep": "kubectl get pods -o name | xargs grep -c web",
    "stdin arguments: wc": "git ls-files | xargs wc -l",
    "stdin arguments: find into ls": "find . -name '*.tf' | xargs ls -la",
    "stdin arguments: -0 into grep naming a tool": "find . -name '*.yml' -print0 | xargs -0 grep -l ansible",
    "stdin arguments: a readable read": "echo get pods | xargs kubectl",
    "stdin arguments: a readable read in a here-string": "xargs kubectl get <<< 'pods'",
    "stdin arguments: a readable read through a placeholder": "echo pods | xargs -I{} kubectl get {} -o wide",
    "stdin arguments: appended to a read": "kubectl get pods -o name | xargs kubectl describe",
    "stdin arguments: appended to a read with flags": "kubectl get pods -o name | xargs -n1 kubectl logs --tail=5",
    "stdin arguments: appended to a formatter": "git ls-files '*.tf' | xargs terraform fmt -check",
    "stdin arguments: placeholder after a read": "kubectl get ns -o name | xargs -I{} kubectl get {} -o yaml",
    "stdin arguments: parallel of a plain command": "ls *.gz | parallel -j 4 gunzip -k",
    "utility: sed print": "sed -n '1,20p' file",
    "utility: sed print of a rule tool's file": "sed -n '1,20p' terraform/main.tf",
    "utility: sed substitute in place": "sed -i -e 's/old/new/g' terraform.tfvars",
    "utility: sed after a rule tool": "kubectl get pods | sed 's/^/  /'",
    "utility: awk print": "awk '{print $1}'",
    "utility: awk after a rule tool": "kubectl get pods | awk '/Running|Pending/ {print $1}'",
    "utility: awk with a separator": "kubectl get pods | awk -F'|' 'NR > 1 || $2 == \"|\" {print $2}'",
    "utility: tar list": "tar -tf x.tar",
    "utility: tar create naming a tool": "tar -czf roles.tgz ansible",
    "utility: tar with a compressor": "tar -I 'zstd -T0' -cf roles.tar.zst ansible",
    "utility: tar through a pipe": "tar -cf - src | ssh h 'tar -xf - -C /srv'",
    "utility: rsync local": "rsync -a src/ dst/",
    "utility: rsync over ssh naming a tool": "rsync -az -e 'ssh -p 2222' ansible/ h:/srv/ansible/",
    "utility: rsync with a remote sudo": "rsync -a --rsync-path='sudo rsync' ansible/ h:/srv/ansible/",
    "utility: fd": "fd -e tf . terraform",
    "utility: rg": "rg -n 'kubectl delete' docs",
    "utility: scp with an option": "scp -o StrictHostKeyChecking=no ansible.cfg h:/tmp/",
    "utility: wget with an rc command": "wget -e robots=off https://example.com/ansible.tgz",
    "utility: sort": "kubectl get pods | sort -k 2",
    "shell reads a script from stdin that names no rule tool": "curl -fsSL https://example.com/install.sh | bash -",
    "shell runs a script file while fed": "kubectl get pods | bash scripts/count.sh",
}


class ClassifyTest(unittest.TestCase):
    rules = idstack.load_rules()

    def test_must_hold(self):
        for name, cmd in MUST_HOLD.items():
            with self.subTest(name, cmd=cmd):
                self.assertTrue(idstack.classify(cmd, self.rules))

    def test_must_pass(self):
        for name, cmd in MUST_PASS.items():
            with self.subTest(name, cmd=cmd):
                self.assertEqual(idstack.classify(cmd, self.rules), [])

    def test_hit_reasons_for_unreadable_text(self):
        cases = [
            ("ssh a ssh b ssh c ssh d ssh e uptime", "nested"),
            ("echo 'kubectl", "unparsed"),
            ("bash -c", "-c"),
            (f"echo '{DELETE}' | bash", "stdin"),
        ]
        for cmd, verb in cases:
            with self.subTest(cmd):
                self.assertIn(verb, [h["verb"] for h in idstack.classify(cmd, self.rules)])

    def test_unparsable_text_without_a_rule_tool_passes(self):
        self.assertEqual(idstack.classify("echo 'unterminated", self.rules), [])


def payload(harness: str, command, cwd: str) -> dict:
    """The PreToolUse payload each harness (or its adapter) sends for a shell call."""
    if harness == "opencode":
        return {"tool_name": "bash", "tool_input": {"command": command}, "cwd": cwd}
    base = {"session_id": "s", "hook_event_name": "PreToolUse", "cwd": cwd}
    return {**base, "tool_name": "Bash", "tool_input": {"command": command}}


def decision(out: dict | None) -> str | None:
    if out is None:
        return None
    return out["decision"] if "decision" in out else out["hookSpecificOutput"]["permissionDecision"]


def reason(out: dict) -> str:
    return out["reason"] if "reason" in out else out["hookSpecificOutput"]["permissionDecisionReason"]


class HookCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.state = self.tmp / "state"
        self.config = self.tmp / "config"
        self.config.mkdir()
        self.work = self.tmp / "work"
        self.work.mkdir()
        self.env = {**os.environ, "IDSTACK_STATE_DIR": str(self.state), "IDSTACK_CONFIG_DIR": str(self.config)}
        for name in ("TYPESAFE_API_KEY", "IDSTACK_GUARD_MODE"):
            self.env.pop(name, None)

    def set_mode(self, mode: str) -> None:
        (self.config / "guard.json").write_text(json.dumps({"mode": mode, "jev": False}))

    def run_hook(self, harness: str, stdin: str, entry: Path = BIN, env: dict | None = None) -> dict | None:
        r = subprocess.run(
            [sys.executable, str(entry), "guard", "hook", "--harness", harness],
            input=stdin,
            capture_output=True,
            text=True,
            env={**self.env, **(env or {})},
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else None

    def log(self) -> list[dict]:
        return [json.loads(x) for x in (self.state / "guard.log").read_text().splitlines()]


class HookTest(HookCase):
    HOLD = {"claude": "ask", "codex": "deny", "opencode": "deny"}

    def test_each_harness_holds_in_its_own_shape(self):
        self.set_mode("ask")
        cases = [
            ("a matched command", DELETE),
            ("a command list", ["bash", "-lc", DELETE]),
            ("a parse failure that names a rule tool", f"{DELETE}; echo 'unterminated"),
            ("a heredoc fed to a shell", f"bash <<EOF\n{DELETE}\nEOF"),
        ]
        for harness, want in self.HOLD.items():
            for name, command in cases:
                with self.subTest(harness=harness, case=name):
                    out = self.run_hook(harness, json.dumps(payload(harness, command, str(self.work))))
                    self.assertEqual(decision(out), want)
                    self.assertIn(str(self.work.resolve()), reason(out), "the hold names the directory")
                    self.assertEqual("hookSpecificOutput" in out, harness != "opencode")

    def test_payload_without_a_readable_command(self):
        cwd = str(self.work)
        shapes = {
            "no command": json.dumps({"tool_name": "Bash", "tool_input": {}, "cwd": cwd}),
            "command is an object": json.dumps(payload("claude", {"x": 1}, cwd)),
            "command is a number": json.dumps(payload("claude", 7, cwd)),
            "command list with a non-string": json.dumps(payload("claude", ["ls", 1], cwd)),
            "payload is a list": "[]",
            "payload is not JSON": "{trunc",
            "no payload": "",
        }
        for mode, harnesses in (("ask", self.HOLD), ("log", ["claude"]), ("off", ["claude"])):
            self.set_mode(mode)
            for harness in harnesses:
                for name, stdin in shapes.items():
                    with self.subTest(mode=mode, harness=harness, shape=name):
                        want = self.HOLD[harness] if mode == "ask" else None
                        self.assertEqual(decision(self.run_hook(harness, stdin)), want)
        self.assertIn("unreadable", {e["reason"].split()[1].rstrip(":") for e in self.log()})
        self.assertEqual({e["decision"] for e in self.log() if e["mode"] == "log"}, {"logged"})

    def test_commands_that_pass(self):
        self.set_mode("ask")
        commands = ["", "   ", "kubectl get pods", "git commit -m 'explain terraform destroy'", "echo it's"]
        for harness in self.HOLD:
            for command in commands:
                with self.subTest(harness=harness, command=command):
                    self.assertIsNone(self.run_hook(harness, json.dumps(payload(harness, command, str(self.work)))))
        self.assertFalse((self.state / "guard.log").exists())

    def test_environment_only_tightens_the_mode(self):
        cases = [
            # mode in guard.json (None: no file), IDSTACK_GUARD_MODE, effective mode
            (None, "", "off"),
            (None, "log", "log"),
            (None, "ask", "ask"),
            (None, "bogus", "ask"),
            ("log", "off", "log"),
            ("log", "ask", "ask"),
            ("ask", "off", "ask"),
            ("ask", "log", "ask"),
            ("off", "off", "off"),
            ("bogus", "off", "ask"),
        ]
        stdin = json.dumps(payload("claude", DELETE, str(self.work)))
        for configured, env, want in cases:
            with self.subTest(configured=configured, env=env):
                (self.config / "guard.json").unlink(missing_ok=True)
                if configured:
                    self.set_mode(configured)
                with (
                    mock.patch.object(idstack, "CONFIG_DIR", self.config),
                    mock.patch.dict(os.environ, {"IDSTACK_GUARD_MODE": env}),
                ):
                    self.assertEqual(idstack.guard_config()["mode"], want)
                out = self.run_hook("claude", stdin, env={"IDSTACK_GUARD_MODE": env})
                self.assertEqual(decision(out), "ask" if want == "ask" else None)

    def test_state_is_private(self):
        self.set_mode("ask")
        self.state.mkdir(mode=0o755)
        (self.state / "guard.log").write_text("")
        (self.state / "guard.log").chmod(0o644)
        self.run_hook("codex", json.dumps(payload("codex", DELETE, str(self.work))))
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.state / "guard.log").stat().st_mode & 0o777, 0o600)
        shutil.rmtree(self.state)
        self.run_hook("codex", json.dumps(payload("codex", DELETE, str(self.work))))
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.state / "guard.log").stat().st_mode & 0o777, 0o600)


class ShimTest(HookCase):
    """hooks/guard_hook.py answers for a CLI that cannot be loaded."""

    def broken(self, source: str) -> Path:
        root = Path(tempfile.mkdtemp(dir=self.tmp))
        (root / "hooks").mkdir()
        (root / "bin").mkdir()
        shutil.copy(SHIM, root / "hooks/guard_hook.py")
        (root / "bin/idstack").write_text(source)
        return root / "hooks/guard_hook.py"

    def test_holds_only_in_ask_mode_or_on_an_unreadable_config(self):
        stdin = json.dumps(payload("claude", "ls", str(self.work)))
        failures = {
            "missing module": "import tomllib_is_not_here\n",
            "syntax error": "def (:\n",
            "error at import": "raise RuntimeError('boom')\n",
        }
        configs = [
            # guard.json text (None: no file), IDSTACK_GUARD_MODE, held
            (None, "", False),
            ('{"mode": "off"}', "", False),
            ('{"mode": "log"}', "", False),
            ('{"mode": "ask"}', "", True),
            ("{trunc", "", True),
            ("[]", "", True),
            ('{"mode": "bogus"}', "", True),
            (None, "ask", True),
            ('{"mode": "ask"}', "off", True),
            ('{"mode": "off"}', "log", False),
        ]
        for name, source in failures.items():
            shim = self.broken(source)
            for text, env, held in configs:
                with self.subTest(failure=name, config=text, env=env):
                    (self.config / "guard.json").unlink(missing_ok=True)
                    if text is not None:
                        (self.config / "guard.json").write_text(text)
                    out = self.run_hook("claude", stdin, entry=shim, env={"IDSTACK_GUARD_MODE": env})
                    self.assertEqual(decision(out), "ask" if held else None)
        self.set_mode("ask")
        for harness, want in HookTest.HOLD.items():
            with self.subTest(harness=harness):
                out = self.run_hook(harness, stdin, entry=shim)
                self.assertEqual(decision(out), want)
                self.assertIn("could not start", reason(out))
                self.assertEqual("hookSpecificOutput" in out, harness != "opencode")

    def test_runs_the_cli_when_it_loads(self):
        self.set_mode("ask")
        for harness, want in HookTest.HOLD.items():
            with self.subTest(harness=harness):
                stdin = json.dumps(payload(harness, DELETE, str(self.work)))
                self.assertEqual(decision(self.run_hook(harness, stdin, entry=SHIM)), want)
                stdin = json.dumps(payload(harness, "kubectl get pods", str(self.work)))
                self.assertIsNone(self.run_hook(harness, stdin, entry=SHIM))
        r = subprocess.run([sys.executable, str(SHIM), "guard", "nonsense"], capture_output=True, env=self.env)
        self.assertEqual(r.returncode, 2, "usage errors keep their exit code")

    def test_shim_parses_as_old_python(self):
        ast.parse(SHIM.read_text(), feature_version=(3, 7))


class AllowOnceTest(HookCase):
    def cli(self, *argv: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(BIN), "guard", *argv],
            capture_output=True,
            text=True,
            env=self.env,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
        )

    def hook(self, harness: str, command: str, cwd: Path) -> str | None:
        return decision(self.run_hook(harness, json.dumps(payload(harness, command, str(cwd)))))

    def grant(self, command: str, cwd: Path) -> None:
        token = {idstack.cmd_hash(command, str(cwd)): time.time() + 60}
        self.state.mkdir(exist_ok=True)
        (self.state / "guard-allow.json").write_text(json.dumps(token))

    def test_token_binds_command_and_directory(self):
        self.set_mode("ask")
        other = self.tmp / "other"
        other.mkdir()
        link = self.tmp / "link"
        link.symlink_to(self.work)
        for harness in ("codex", "opencode"):
            with self.subTest(harness=harness):
                self.grant(DELETE, self.work)
                self.assertEqual(self.hook(harness, DELETE, other), "deny", "another directory")
                self.assertEqual(self.hook(harness, DELETE + " ", self.work), "deny", "another command")
                self.assertIsNone(self.hook(harness, DELETE, link), "the same directory through a link")
                self.assertEqual(self.hook(harness, DELETE, self.work), "deny", "a token works once")
        self.grant(DELETE, self.work)
        self.assertEqual(self.hook("claude", DELETE, self.work), "ask", "Claude Code asks instead")
        decisions = [e["decision"] for e in self.log()]
        self.assertEqual(decisions.count("allowed-once"), 2)
        self.assertEqual({e["cwd"] for e in self.log()}, {str(self.work.resolve()), str(other.resolve())})

    def test_hook_without_a_payload_directory_uses_its_own(self):
        self.set_mode("ask")
        self.grant(DELETE, self.work)
        stdin = json.dumps({"tool_name": "bash", "tool_input": {"command": DELETE}})
        r = subprocess.run(
            [sys.executable, str(BIN), "guard", "hook", "--harness", "opencode"],
            input=stdin,
            capture_output=True,
            text=True,
            env=self.env,
            cwd=self.work,
        )
        self.assertEqual(r.stdout.strip(), "", "allowed in the directory the hook runs in")

    def test_expired_token_is_refused(self):
        self.set_mode("ask")
        self.state.mkdir()
        expired = {idstack.cmd_hash(DELETE, str(self.work)): time.time() - 1}
        (self.state / "guard-allow.json").write_text(json.dumps(expired))
        self.assertEqual(self.hook("codex", DELETE, self.work), "deny")

    @unittest.skipUnless(sys.platform != "win32", "needs a pseudo-terminal")
    def test_allow_once_from_a_terminal_binds_cwd(self):
        import pty

        self.set_mode("ask")
        other = self.tmp / "other"
        other.mkdir()
        cases = [
            # directory allow-once runs in, --cwd, directory the token is good for
            (self.work, None, self.work),
            (other, str(self.work), self.work),
        ]
        for run_in, flag, good in cases:
            with self.subTest(flag=flag):
                master, slave = pty.openpty()
                argv = ["guard", "allow-once", "--ttl", "60", *(["--cwd", flag] if flag else []), DELETE]
                r = subprocess.run(
                    [sys.executable, str(BIN), *argv], stdin=slave, stdout=slave, stderr=slave, env=self.env, cwd=run_in
                )
                os.close(slave)
                shown = os.read(master, 4096).decode()
                os.close(master)
                self.assertEqual(r.returncode, 0, shown)
                self.assertIn(str(good.resolve()), shown, "allow-once prints the directory it bound")
                wrong = other if good == self.work else self.work
                self.assertEqual(self.hook("codex", DELETE, wrong), "deny")
                self.assertIsNone(self.hook("codex", DELETE, good))

    def test_usage_errors(self):
        cases = [
            (["test"], 2),
            (["test", "  "], 2),
            (["allow-once"], 2),
            (["allow-once", ""], 2),
            (["allow-once", DELETE], 1),  # no terminal
            (["test", DELETE], 0),
        ]
        for argv, code in cases:
            with self.subTest(argv=argv):
                r = self.cli(*argv, "--json")
                self.assertEqual(r.returncode, code, r.stderr)
                d = json.loads(r.stdout)
                self.assertEqual(d["ok"], code == 0)
                self.assertEqual(bool(d["errors"]), code != 0)
        self.assertFalse((self.state / "guard-allow.json").exists())


class JevBranchTest(unittest.TestCase):
    def test_is_ambiguous(self):
        cases = {
            "kubectl get pods": True,
            "sudo -u deploy terraform plan": True,
            "make deploy": True,
            "./deploy.sh": True,
            "bash scripts/run.sh": False,
            "ls -la": False,
            "echo 'unterminated": False,
            "command -v terraform": False,
        }
        for cmd, want in cases.items():
            with self.subTest(cmd):
                self.assertEqual(idstack.is_ambiguous(cmd), want)

    def test_jev_only_adds_holds(self):
        def answers(p: float) -> dict:
            names = ("changes_remote_state", "deletes_data", "targets_production")
            return {"answers": {q: {"noul": p} for q in names}}

        cases = [
            # command, jev on, response, match, source
            ("make deploy", True, answers(0.9), True, "jev"),
            ("make deploy", True, answers(0.1), False, "rules"),
            ("make deploy", True, None, True, "jev"),  # a failed call is unsettled, which holds
            ("make deploy", True, ["not", "an", "object"], True, "jev"),
            ("make deploy", False, answers(0.9), False, "rules"),
            ("ls -la", True, answers(0.9), False, "rules"),  # not ambiguous: Jev is not asked
            (DELETE, True, answers(0.0), True, "rules"),  # a rule hit stands whatever Jev says
        ]
        for cmd, jev, response, match, source in cases:
            with (
                self.subTest(cmd=cmd, jev=jev, response=response),
                mock.patch.object(idstack, "jev_ask", return_value=(response, None, {})) as ask,
                mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key"}),
            ):
                d = idstack.guard_decide(cmd, {"mode": "ask", "jev": jev})
                self.assertEqual((d["match"], d["source"]), (match, source))
                self.assertEqual(ask.called, jev and cmd == "make deploy")

    def test_no_key_means_no_call(self):
        with (
            mock.patch.object(idstack, "jev_ask") as ask,
            mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}),
        ):
            self.assertFalse(idstack.guard_decide("make deploy", {"mode": "ask", "jev": True})["match"])
            ask.assert_not_called()


class OpencodeInstallTest(HookCase):
    def test_commented_config_is_refused(self):
        base = self.tmp / "xdg/opencode"
        base.mkdir(parents=True)
        (base / "opencode.jsonc").write_text("// mine\n{}\n")
        r = subprocess.run(
            [sys.executable, str(BIN), "guard", "install", "--harness", "opencode", "--json"],
            capture_output=True,
            text=True,
            env={**self.env, "HOME": str(self.tmp), "XDG_CONFIG_HOME": str(self.tmp / "xdg")},
            stdin=subprocess.DEVNULL,
        )
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("opencode.jsonc", json.loads(r.stdout)["errors"][0])
        self.assertEqual((base / "opencode.jsonc").read_text(), "// mine\n{}\n")
        self.assertFalse((base / "opencode.json").exists())


if __name__ == "__main__":
    unittest.main()
