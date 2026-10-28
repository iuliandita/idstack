### Vulnerability response

**You own the proof that the vulnerable version is gone from what runs.**

For one CVE or advisory. Where are we exposed, and is it fixed. Finding exposure is read-only. Fixes go through `dependency-bump` or `upgrade`.

1. Pin the target per `references/targets.md` for each environment searched. Read the advisory text and note the affected and fixed versions.
2. Find every place the component runs: image SBOMs, chart renders, host package lists, lockfiles. Record each with its current version.
3. Prioritize: listed in CISA KEV, EPSS score, internet-facing or not, reachable or not, vendor fix available.
4. Patch through `dependency-bump` or `upgrade`. Open a tracked issue per exposed location group first.
5. Verify from live state. Rescan the new artifact (`trivy image <ref>`), confirm running pods use the new digest, and confirm host package versions. A merged PR is not proof.
6. If no fix exists, propose a mitigation (disable the feature, restrict exposure) as a **Gate**. Open an issue with a review date.

Never: mark an item fixed from a green build or a merged PR, or clear a finding because a scanner stopped reporting it without checking why.

Calls: **security-audit**, **docker**, **kubernetes**.
Principles: pin-the-target, prove-it-works.

**Reply:** exposure table, patched locations with evidence, mitigations and their review dates.
