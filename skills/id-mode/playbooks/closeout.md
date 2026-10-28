### Closeout

**You own leaving nothing ambiguous.**

For the end of a work session. It reports and sweeps. It deletes nothing without the operator's confirmation.

1. Check that everything intended is committed and pushed, and that nothing intended is only local. Run `git status` and compare local and remote refs.
2. List PR and MR states. Each is merged, open with a reason, or abandoned.
3. List gates still held and what each needs (an approval, a fresh plan, a soak period). Mark saved plan files that are now stale.
4. Sweep branches and worktrees, local and remote, using pstack's `worktree-cleanup`. List the merged or abandoned ones and recommend what to delete.
5. **Gate:** deletion of any branch or worktree. Delete only after the operator confirms the exact list.
6. Record lessons. Repo-specific lessons go to the repo's agent instructions, tracked or local-only by sensitivity. Cross-project facts go to the operator's memory store if one is configured. Never store secrets or internal hostnames in a tracked file.
7. Write a short "what's left" list with an owner for each item.

Never: delete a branch or worktree that holds unpushed work, or close a tracked issue the fix has not been verified for.

Calls: **git**.
Principles: reversible-first, encode-lessons-in-structure.

**Reply:** the what's-left list first, then the state lines.
