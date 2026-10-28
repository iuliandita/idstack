# Gates

## Action classes

Classify every action before running it. Class follows the downstream effect, not the command name.

| Class | Examples | Rule |
| --- | --- | --- |
| Read | `get`, `describe`, `logs`, `plan`, `diff`, `template`, `--check`, PromQL and LogQL queries, `dig`, `openssl s_client`, scans of your own assets | Free. Bound it: time ranges, `--tail`, limits. Never read Secret values. |
| Reversible write | Branch, commit, push to a branch that triggers nothing, PR or MR, local render, restore into a scratch namespace, draft message, issue | Free, unless it triggers automation that deploys (below). |
| State-mutating | `apply`, `destroy`, state commands, `import`, `sync` to a shared environment, `delete`, `scale`, `drain`, `rollout restart`, `helm upgrade`, Ansible without `--check`, firewall or DNS changes, secret rotation or revocation, reboot, VM destroy or stop, sending an external message, a merge or push that deploys | Always a gate. |

**Git events can be writes.** A push, PR, merge, tag, or workflow dispatch that triggers automation able to deploy or change infrastructure is state-mutating: CI that applies on push, preview environments on PR, ArgoCD or Flux auto-sync on merge, a tag that publishes. That automation runs with its own credentials, so the agent's read-only credentials do not stop it. Every change playbook's first step finds out which git events deploy in the target repo and records it. If you cannot tell, treat the event as state-mutating.

## The gate block

Show this in one block, then stop.

```text
GATE: <one-line action>
Command:      <exact command, with the target passed explicitly>
Target:       <pinned context, account, workspace, host, zone>
Blast radius: <what it touches, who notices, what breaks if it is wrong>
Rollback:     <command or procedure, and how long it takes>
Verify:       <the read-only query that proves it worked>
Evidence:     <saved plan file, rendered diff, check-mode output it rests on, and its age>
```

**Approval** is per command and per turn. It does not carry into later turns or to a different command, target, or artifact. Silence is not approval. If the artifact changes after approval (re-plan, re-render), the gate is shown again.

## Grants

The operator can authorize work ahead of time in two forms. Record each as a todo item in the operator's words, then in its checkable form.

- **Stop line.** "Run until X, then stop." Reversible work proceeds freely up to the line. Reaching it is a successful stop.
- **Predicate grant.** "Apply if the plan shows only X." Turn it into a predicate a script can check against the reviewed artifact, run the check, and log the command and its output. Anything outside the predicate stops at a normal gate.

Example predicates:

- **Terraform, OpenTofu** (`plan.json` from `show -json`): no delete or replace, and every changed address in the named set. `idstack plan-summary plan.json --scope '<glob>' --predicate` checks both and exits 0 only on a pass. It also fails on any IAM or network change unless the grant names that kind of change and you pass `--allow-iam` or `--allow-network`. Without the CLI:

  ```sh
  jq '[.resource_changes[] | select(.change.actions - ["no-op","read","create","update"] != [])] | length' plan.json   # must print 0
  jq -r '.resource_changes[] | select(.change.actions != ["no-op"] and .change.actions != ["read"]) | .address' plan.json   # every line in the named set
  ```

- **Helm, Kustomize** (rendered diff against live): only the named kinds and names change; no deletions, and no CRD, RBAC, PVC, or NetworkPolicy changes.
- **Ansible** (`--check --diff` output): `changed` only on the named hosts and tasks, and no `command` or `shell` tasks in the changed set.

**Never grantable:** destroy, state surgery (`state rm`, `state mv`, `state push`, `force-unlock`), data deletion, revoking or rotating root or break-glass credentials, a change to the operator's own access path (VPN, SSH, firewall rules that carry the session). These always stop at a gate, whatever the grant says.

Grants last for the current task only.

## Repo rules

A repo rule that is stricter wins. If the repo says agents never apply, the agent never applies, even with a grant: it prepares the artifact and the gate block for the human to run.
