### IaC change

**You own the plan. Nothing applies that was not reviewed.**

For a Terraform or OpenTofu change, from edit to verified apply. Load **terraform** for the domain. The gate block, grants, and predicates are in `references/gates.md`.

1. Find the repo's rules: whether an agent ever applies here, whether apply is manual or CI-driven, which git events deploy, the binary (Terraform or OpenTofu) and its pinned version, and where state lives. Record them. Repo rules win.
2. Pin the target: backend, workspace, and cloud identity per `references/targets.md`.
3. Check state before planning: the backend is reachable, the state serial and lineage look current, and there is no stray local state file. A state that looks older than the last known apply stops here. A restored stale state planned against live infrastructure is how an agent destroyed a production stack and its snapshots in February 2026.
4. Make the change. Prefer `moved`, `import`, and `removed` blocks (with `destroy = false` when the real resource stays) over state commands, because they show up in the plan.
5. Static checks: `fmt -check`, `validate`, and the repo's linters and scanners (tflint, trivy, checkov). Fix new findings or record why not.
6. Plan to a file: `plan -out=<name>.tfplan`, then `show -json <name>.tfplan > plan.json`. Use the repo's lock convention on shared state.
7. Summarize the plan with `plan-reader`: counts by action, every delete and replace, changes to stateful, IAM, and network resources, and every address outside the intended scope. Anything unexpected sends you back to step 4.
   Jev decision point (optional): per changed resource, ask "holds persistent data?" and "widens IAM permissions?". Any answer above 0.3 fails a predicate grant and moves plan reading to the `hardest tasks` model. Network exposure is checked in code from the plan, not by Jev.
8. For repos grouped by tenant or risk, split into targeted plans per group, one file each, lowest risk first.
9. Run **Opening a PR** with the plan summary in the body. Merging does not apply unless step 1 found that it does; if it does, the merge is the gate in step 10.
10. **Gate:** apply the saved plan file and nothing else. A predicate grant passes this gate only when its check against `plan.json` passes and is logged.
11. Re-plan after the apply. Expect no changes. Anything else is drift or a partial apply: stop and report it.
12. Run the gate's verification query with `change-verifier` and log the result.

Never: apply without a saved plan, reuse a plan after any other apply to the same state, or run `destroy` or state surgery under a grant.

Calls: **terraform**, **security-audit** for IAM- or network-heavy diffs.
Principles: plan-before-apply, pin-the-target, make-operations-idempotent, sequence-verifiable-units.

**Reply:** plan summary per group, what applied, the re-plan result, and held groups.
