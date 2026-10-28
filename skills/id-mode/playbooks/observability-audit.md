### Observability audit

**You own the gaps. An unmonitored failure is a future incident.**

For checking that monitoring would catch what matters, and that alerts are worth reading. This playbook changes nothing. Fixes go through the change playbooks (`gitops-change` for rules and dashboards in git, plus `iac-change`, `host-config-change`, `edge-change`, `dependency-bump`, `upgrade` where they apply), and findings become tracked issues.

1. Pin the target per `references/targets.md`: the Prometheus, Alertmanager, and log endpoints, read-only.
2. Coverage: every service has metrics, logs, and health checks. List dead scrape targets, for example `up == 0`.
3. Watch the watchers: alerts exist for backup failures, certificate expiry, disk and storage growth, NFS or network mounts, the monitoring stack itself, and the alert delivery path.
4. Alert hygiene: list the noisiest alerts over 30 days, flapping alerts, rules that never fired (check retention first), rule evaluation failures, and missing runbook links.
5. SLOs: where they exist, check the burn-rate alert windows. Where they should exist, propose them.
6. Routing: check grouping, inhibition, repeat intervals, and the digest versus page split. Validate with `amtool check-config <file>` and `promtool check rules <file>`.
7. Cardinality: top series by metric name with `topk(10, count by (__name__)({__name__=~".+"}))`, and head series growth.
8. File an issue per gap with the evidence.

Never: silence, delete, or edit an alert or rule to improve the numbers.

Calls: **observability**.
Principles: pin-the-target, explain-the-number, encode-lessons-in-structure.

**Reply:** gap table, alert hygiene table, issues filed.
