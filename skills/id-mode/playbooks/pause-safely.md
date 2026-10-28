### Pause safely (idstack overlay)

Read the shared playbook first: pstack `poteto-mode/playbooks/pause-safely.md`.

Then apply these gates. They win on conflict.

The checkpoint also records:

1. Every pinned target and how it was checked.
2. Gates held: the gate block, and whether the operator answered.
3. Saved plan files, renders, and check-mode output, with when each was produced. Mark each as stale for the resumer: a resumed session produces them again before any gate.
4. Any partly applied change: what applied, what did not, and the read-only command that shows the current state.
5. Grants in force, in the operator's words. They expire with the task; a resumed session asks again.
