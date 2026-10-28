### Edge change

**You own reachability. Keep a way back in.**

For DNS records, reverse proxy routes, firewall rules, VPN users and peers, TLS certificates, and IP allowlists, including the same change across several repos. Load **networking**. The gate block, grants, and predicates are in `references/gates.md`.

1. Find the repo's rules and which git events deploy. List every place the change must land (DNS zone, proxy config, firewall, several IaC repos for one allowlist). Find stale entries the change replaces.
2. Pin the target per location per `references/targets.md`: zone and provider account, proxy host, appliance.
3. Back up the current config: zone export, firewall config export, proxy config in git.
4. Confirm an out-of-band path exists (console, second VPN, a session kept open) before touching anything that could cut access. A change to the operator's own access path is never grantable.
5. Make the change in IaC where it lives in IaC. For appliances without an API, draft the exact change for the human to apply.
6. For DNS, lower the TTL ahead of a cutover and wait out the old TTL. For certificates, use a staging issuer first when available.
7. Run **Opening a PR** per repo that holds part of the change.
8. **Gate:** per location. One rule at a time on firewalls, with revert-on-timeout where the appliance supports it.
9. Verify from each side with `change-verifier`. `dig @<ns>` against the authoritative server and against a public resolver, `curl --resolve`, `openssl s_client -connect host:443 -servername host` for the served chain and expiry, a connection test from each network segment, and the VPN client actually connecting.
10. **Gate:** remove the stale entries found in step 1.

Never: change firewall or VPN rules that carry the session without the out-of-band path, or batch several firewall rules into one gate.

Calls: **networking**, **opnsense-pfsense**, **terraform**.
Principles: reversible-first, pin-the-target, prove-it-works.

**Reply:** locations changed, verification per side, stale entries removed, and held locations.
