### Live diagnosis

**You own the diagnosis. Observe before you theorize, and change nothing.**

For a live symptom (alert, outage, error spike, slow service, failed job) with an unknown cause. This playbook is read-only. Fixes go through the change playbooks (`iac-change`, `gitops-change`, `host-config-change`, `edge-change`, `dependency-bump`, `upgrade`), and confirmed findings become tracked issues.

1. Pin the target per `references/targets.md`. Confirm VPN and access. Use read-only credentials if they exist and report whether the active ones can write.
2. Open a timeline file per `references/evidence.md`: UTC timestamp first, one line per observation or command.
3. Define the symptom with a query that shows it (an error rate, a failing check, a log line count). Bound every query by time range and limit.
4. Bisect by layer: network and DNS, ingress and certificates, workload, storage, node, upstream dependency, recent changes (deploys, bumps, config, certificate expiry). Each pass picks the split that rules out the most.
5. Send bulk log and metric reading to `id-agent` delegates on the `why investigators` model. Give each the pinned target and a read-only command list. Keep only the reduced findings in the main thread.
   Jev decision point (optional): `idstack judge log-filtering <chunks.json>`, each item a symptom and a log chunk. Keep `flag` and `unsettled` chunks (related above 0.3) for the reasoning model. If the kept chunks do not explain the symptom, keep the full logs and widen the search. A filtered-out chunk is never evidence that something did not happen.
6. Check recent changes against the symptom's start time.
   Jev decision point (optional): `idstack judge suspect-changes <changes.json>`, each item an alert and a change. It ranks the changes by plausible cause; examine them and examine them read-only from the top. Any rollback goes through a gate.
7. Confirm the mechanism with evidence, not a plausible story. Name what would disprove it and check that.
8. If mitigation is needed now, propose it as a **Gate** (rollback, failover, scale, restart) and hand to `incident`.
9. Hand the fix to the matching change playbook and file the issue.

Never: restart, scale, or edit anything to "see if it helps", or read Secret values.

Calls: **debug-triage**, **kubernetes-health**, **observability**, **networking**, **databases**.
Principles: pin-the-target, fix-root-causes, attack-the-premise, guard-the-context-window.

**Reply:** symptom query, mechanism with evidence, ruled-out causes, proposed mitigation and fix.
