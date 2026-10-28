### Capacity and cost

**You own the forecast and the evidence behind each cut.**

For storage growth, resource right-sizing, cloud spend, and licenses or seats. This playbook changes nothing. Changes go through the change playbooks (`iac-change`, `gitops-change`, `host-config-change`, `edge-change`, `dependency-bump`, `upgrade`), and findings become tracked issues. Removing unused resources also runs `decommission`.

1. Pin the target per `references/targets.md` for each cluster, account, or hypervisor. Use read-only credentials.
2. Storage: compute days-to-full per filesystem, volume, pool, and hypervisor storage from growth trends. Flag anything under the agreed horizon.
3. Compute: compare requests with actual use (krr or VPA in recommend mode), and check CPU throttling and OOM kills.
4. Cloud spend: find idle volumes, unattached IPs, oversized managed databases, and unused buckets, by tag or project.
5. Licenses and seats: inventory from real usage (hosts that are off, users who left), not from the billing page alone.
6. Propose each change with its evidence, the expected saving as a number, and the risk. A low-use signal is a hypothesis, not proof something is unused.
7. File an issue per proposal.

Never: resize, delete, or scale anything from this playbook.

Calls: **observability**, **virtualization**, **kubernetes**.
Principles: pin-the-target, explain-the-number.

**Reply:** forecast table, right-sizing proposals, savings with evidence.
