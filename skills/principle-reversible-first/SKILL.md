---
name: principle-reversible-first
description: "Apply when choosing how to make a change: prefer the step that can be undone. Park before teardown, power off before delete, warn before enforce, canary before fleet, one rule at a time."
disable-model-invocation: true
---

# Reversible First

When there are several ways to reach the same end state, take the one that can be undone first, prove it, and only then take the step that cannot.

**Why:** most infra mistakes are found within minutes of the change, by whoever depends on the thing. A reversible step turns that discovery into a quick undo. An irreversible one turns it into a recovery project, sometimes from backups that turn out not to restore.

**The idea:** split the change so the risky, final part comes last and alone.

- Park before teardown: scale to zero, power off, disable the DNS name, rename with an `OFF-` prefix. Soak. Then delete.
- Warn before enforce: audit mode, dry-run policies, log-only firewall rules, then enforcement.
- Canary before fleet: one host, one node, one environment, then the rest in batches.
- One rule at a time on firewalls and access paths, with a revert-on-timeout where the appliance supports it, and a way back in kept open.
- Write the rollback before the change, with how long it takes.

**The test:**
1. If this step is wrong, how do you undo it, and how long does that take?
2. Is there a version of this step that can be undone and still tells you whether the final step is safe?
3. Is the irreversible part last, alone, and behind its own gate?
