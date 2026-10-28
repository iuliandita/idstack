### Bug fix (idstack overlay)

Read the shared playbook first: pstack `poteto-mode/playbooks/bug-fix.md`.

Then apply these gates. They win on conflict.

1. For an infra defect, "reproduce" means observing it in live state with read-only commands (a query, `describe`, a plan that shows the wrong diff, a failing `curl`), or in a fixture. Pin the target first. Never reproduce by changing live state.
2. Binary-search the cause per the **live-diagnosis** playbook when the defect is in a running system. Instrumenting a live system is a state change and goes through a gate.
3. Deliver the fix through the matching change playbook (`iac-change`, `gitops-change`, `host-config-change`, `edge-change`), with its gates. The shared playbook's implementation step does not apply anything.
4. Verify on live state with `change-verifier`, against the same read-only check that showed the defect.
5. When a failing check exists (a test, a policy rule, a plan assertion), it lands before the fix in commit order.
