### Queue burndown

**You own the merge frontier and the stop line.**

For a queue of PRs or MRs to land in order, where some merges need a plan and apply. Works with `gh` or `glab`. Runs pstack's `babysit` per item for conflicts, threads, and CI. The gate block, grants, and predicates are in `references/gates.md`.

1. Record the stop line the operator gave ("merge all, stop before apply", "stop at the first red plan") in their words and in checkable form. Pin the forge repo per `references/targets.md`.
2. List the queue with dependencies and order. Find which merges deploy and which need a manual apply after.
3. Per item, in order: rebase if needed, check CI, and confirm review threads are resolved.
4. Merge with a short squash message. **Gate** first when the merge deploys.
5. After each merge that needs an apply, re-plan, because the previous apply makes older plans stale. Summarize with `plan-reader`, then **Gate** the apply or check a predicate grant against the new plan.
6. Clean up after each item: delete merged branches, update the queue.
7. Stop at the stop line or at the first item that fails a gate.

Never: apply a plan produced before an earlier item applied, or continue past a red plan.

Calls: **git**, **terraform**.
Principles: sequence-verifiable-units, plan-before-apply.

**Reply:** merged items, applied items with plan summaries, where it stopped and why, and what is left.
