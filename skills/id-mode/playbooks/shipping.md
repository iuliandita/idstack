### Shipping (idstack overlay)

Read the shared playbook first: pstack `poteto-mode/playbooks/shipping.md`.

Then apply these gates. They win on conflict.

1. When merges deploy, landing a stack is a series of state-mutating writes: one gate per PR, never one approval for the stack.
2. Between merges, verify the previous one landed in live state with `change-verifier` (synced revision against the merge commit, a re-plan showing no changes, the running image digest), not by CI status.
3. A PR whose merge also needs a manual apply gets its plan produced after the previous apply, then its own gate.
4. Stop at the first PR that fails verification. Report the landed run and the rest as held.
