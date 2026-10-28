### Autonomous run (idstack overlay)

Read the shared playbook first: pstack `poteto-mode/playbooks/autonomous-run.md`.

Then apply these gates. They win on conflict.

1. The exit predicate includes a stop line before any state-mutating step that no grant covers. Record it as the first todo item.
2. Reaching the stop line is a successful stop, not a dead end. Prepare everything up to it (plans, renders, PRs, gate blocks) so the operator can approve in one pass.
3. "Don't stop" or "run until done" extends reversible work only. It does not approve applies, syncs, merges that deploy, or messages.
4. A predicate grant is checked against each artifact as it is produced, and every check is logged.
