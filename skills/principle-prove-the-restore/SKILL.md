---
name: principle-prove-the-restore
description: "Apply when relying on a backup: before upgrades, decommissions, risky changes, and in restore drills. A backup that has not been restored is a hypothesis, and it must be independent of what it protects."
disable-model-invocation: true
---

# Prove the Restore

A backup counts only when it has been restored and the restored data checked. Until then it is a hypothesis. A backup also counts only when it is independent of the thing it protects.

**Why:** backup jobs report success when they write something, not when that something can be read back into a working system. Common failures stay invisible until the day they matter: an empty dump, a missing encryption key, a snapshot of a volume mid-write, a restore that takes ten times the agreed window. And a backup managed by the same credentials or the same IaC as its source can be destroyed by the same mistake, which is how one 2026 incident lost a production database and its automated snapshots in one command.

**The idea:** restore into isolation (a scratch namespace, an isolated VM network, a throwaway database), never over the live target. Check the data at the application level: row counts, checksums, a health endpoint, opening a file. "Restore completed" and "PVC Bound" are proxies. Time the restore against the recovery-time target. Check independence: different credentials, a different lifecycle, an off-site copy, and nothing that the source's IaC could delete.

**The test:**
1. When was this backup last restored, and what proved the data was right?
2. Could the credentials or code that manage the source also delete this backup?
3. How long did the last restore take, against the agreed recovery time?
