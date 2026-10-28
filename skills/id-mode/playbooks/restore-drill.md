### Restore drill

**You own the restore, not the backup job's exit code.**

For proving backups exist, are fresh, are independent of what they protect, and actually restore.

1. Pin the target per `references/targets.md`: the source environment and the isolated drill environment, separately.
2. Inventory backup sources: VM backups, cluster resource backups, volume backups, datastore snapshots, database dumps, file backups, managed-service backups. For each, record the RPO and RTO targets. The operator signs off on them.
3. Freshness: find the last successful run per source and compare it to its RPO. A job that exits 0 with an empty or tiny artifact is not fresh.
4. Independence: can the credentials or IaC that manage the source also delete the backup? Is there an off-site copy under different credentials? Is the cluster datastore token backed up with the snapshot?
5. **Gate:** restore into isolation (scratch namespace, isolated VM network, throwaway database). Never over the live target. The gate block names the isolation boundary.
6. Prove the data with application-level checks (row counts, checksums, a health endpoint, opening a file). "PVC Bound" and "restore Completed" are not proof.
7. Measure the restore time against the RTO. Report the number and what it includes.
8. **Gate:** clean up the drill resources. Delete only what the drill created, listed by name.
9. Record the result with date, evidence, and measured times so the next drill can compare. File an issue for each failed row.

Never: restore over live data, or run the drill with credentials that can delete the source.

Calls: **virtualization**, **databases**, **kubernetes**.
Principles: pin-the-target, prove-the-restore, explain-the-number.

**Reply:** table per source with freshness, independence, restore result, and measured RTO.
