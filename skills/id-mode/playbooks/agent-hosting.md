### Agent hosting

**You own what each agent can reach.**

For running autonomous agents or bots on your own infrastructure. This playbook changes nothing. Fixes go through the change playbooks (`iac-change`, `gitops-change`, `host-config-change`, `edge-change`, `dependency-bump`, `upgrade`), and findings become tracked issues.

1. Pin the target per `references/targets.md` for each host or cluster that runs agents.
2. Inventory agents: where they run, what identity they use, and which tokens, kubeconfigs, and SSH keys they hold. Record names and scopes, never values.
3. Least privilege: read-only by default, write access scoped to named namespaces or repos, no cluster-admin, and no shared human credentials. Check effective permissions, for example `kubectl --context <ctx> auth can-i --list --as <identity>`.
4. Containment: resource limits, network policy, and no access to secret stores beyond their own.
5. Audit: actions are logged somewhere the agent cannot edit.
6. Lifecycle: how tokens are rotated, and how an agent is disabled quickly. Test the disable path on paper, not on a live agent.
7. File an issue per over-privileged item. Rotation goes through `secret-rotation`.

Never: read token values, or disable or revoke an agent from this playbook.

Calls: **kubernetes**, **security-audit**.
Principles: pin-the-target, reversible-first.

**Reply:** reach table per agent, over-privileged items, issues filed.
