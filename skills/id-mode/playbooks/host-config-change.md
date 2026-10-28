### Host config change

**You own convergence. A second run changes nothing.**

For Ansible roles and playbooks against hosts and VMs. Load **ansible** and the OS skill for the target distro. The gate block, grants, and predicates are in `references/gates.md`.

1. Find the repo's rules and the delivery path: run by hand, or applied by CI on merge, and which git events deploy. If CI applies on merge, the merge is the gate.
2. Pin the target: inventory, group, and the canary host per `references/targets.md`. Pass `-i <inventory> --limit <hosts>` every time.
3. Make the change.
4. Run `ansible-lint` with the repo's profile and `ansible-playbook --syntax-check`.
5. Run `ansible-playbook --check --diff --limit <canary>`. Note tasks that check mode cannot predict (`command`, `shell`). Summarize with `plan-reader`.
6. Run **Opening a PR** with the check-mode summary in the body.
7. **Gate:** run on the canary only. A predicate grant passes only when its check against the `--check --diff` output passes and is logged.
8. Run the same play again on the canary. Expect `changed=0`. Anything else is an idempotence bug: fix it before going wider.
9. **Gate:** the rest of the fleet with `serial`, restart-sensitive services last.
10. Verify per host with a read-only check of the service the change affects, using `change-verifier`.

Never: run without `--limit`, widen past the canary before the second run shows `changed=0`, or reuse check output after the inventory or the play changed.

Calls: **ansible**, the matching OS skill (**arch-linux**, **debian-ubuntu**, **rhel-fedora**, or **nixos**).
Principles: make-operations-idempotent, reversible-first, sequence-verifiable-units.

**Reply:** canary result, idempotence result, hosts converged, and hosts held.
