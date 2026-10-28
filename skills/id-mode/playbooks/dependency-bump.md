### Dependency bump

**You own what the bump changes, not just that CI passed.**

For a backlog of Renovate or Dependabot PRs, or a single chart, provider, module, image, or action bump. The gate block, grants, and predicates are in `references/gates.md`.

1. Find the repo's rules: which git events deploy, and the operator's stop line. Pin the forge repo per `references/targets.md`.
2. List open bot PRs. Classify each: patch, minor, or major; image, chart, provider, module, or action; stateful or not; whether merge deploys.
3. For each non-trivial bump, read the release notes between the two versions for breaking changes, deprecations, and migrations.
   Jev decision point (optional): put the release-note bullets in a JSON array and run `idstack judge dependency-bump <bullets.json>` (breaking, needs an operator step, removes or renames a setting). Any `flag` or `unsettled` bullet removes auto-merge eligibility and sends the bump to a gate.
4. For charts, diff the default values between versions, render old and new with the repo's values, diff the renders, and diff CRDs separately because Helm does not upgrade CRDs.
5. For providers and modules, run the plan and summarize it with `plan-reader`, as in `iac-change`.
6. For GitHub Actions, confirm the new ref is pinned by SHA and comes from the original repo.
7. Merge the bumps that are green, low-risk, and do not deploy on merge, with short squash messages. Stop at the operator's stop line. Run **Opening a PR** for any bump you author.
8. **Gate:** each bump whose merge deploys, and every major.
9. If the bot has gone quiet, diagnose it read-only: bot logs, dashboard issue, config errors, rate limits, token expiry.

Never: merge on "CI is green" alone, merge a major without a gate, or auto-merge a bump that touched a stateful component.

Calls: **ci-cd**, **kubernetes**, **terraform**, **docker**.
Principles: explain-the-number (for "CI is green"), sequence-verifiable-units.

**Reply:** a table of bumps with class, risk, and action taken, then held bumps and why.
