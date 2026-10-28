# Security policy

Report suspected vulnerabilities through
[GitHub private security reporting](https://github.com/iuliandita/idstack/security/advisories/new).
Do not post working bypasses or secrets in public issues. Include the idstack commit or version,
the harness and its version, the install mode, a redacted reproduction, and the impact.

In scope:

- The installer: anything that makes it overwrite files it should not, fetch something other than
  what it pins, or run something it does not show.
- The safety model: a playbook, overlay, or decision rule that lets an agent change live state
  without a gate, or lets a Jev answer loosen a gate.
- The guard: a state-mutating command it should match that runs without an ask or block, or a way
  for an agent to approve its own command.
- `idstack plan-summary --predicate` exiting 0 on a plan that has a delete, replace, or forget, an
  out-of-scope change, or an IAM or network change the grant did not allow.
- `idstack judge`: any path where a Jev answer, a failed call, or a missing answer clears an item
  instead of tightening it.
- Leaks of credentials or private data through playbook output or evidence logs.

Out of scope: pstack itself (report to [cursor/plugins](https://github.com/cursor/plugins)), the
pstack mirror (report to [backnotprop/pstack](https://github.com/backnotprop/pstack)), and the
harnesses.

Skills and plugins run with your permissions. The installer fetches pstack from `cursor/plugins`
for Claude Code and from a pinned commit of `backnotprop/pstack` for Codex and OpenCode; review
those sources before you trust them.

Fixes target the `develop` branch; older versions may not receive backports. This is a personal
project without a guaranteed response time.
