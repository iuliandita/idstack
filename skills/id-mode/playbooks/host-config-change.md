### Host config change

**You own convergence. A second run changes nothing.**

For Ansible roles and playbooks against hosts and VMs. Load **ansible** and the OS skill for the target distro. The gate block, grants, and predicates are in `references/gates.md`.

1. Find the repo's rules and the delivery path: run by hand, or applied by CI on merge, and which git events deploy. If CI applies on merge, the merge is the gate.
2. Pin the target: inventory, group, and the canary host per `references/targets.md`. Pass `-i <inventory> --limit <hosts>` every time.
3. Make the change.
4. Run `ansible-lint` with the repo's profile and `ansible-playbook --syntax-check`.
5. Before any `--check` run, search the plays and roles in scope for `check_mode: false` (or `no`). A task that sets it runs for real under `--check`: stop at a **Gate** before that run. Run tasks that template secrets with `diff: false`, or drop `--diff`, so the output never prints a secret value.
6. Run `ansible-playbook --check --diff --limit <canary>`. Note tasks that check mode cannot predict (`command`, `shell`, `raw`, `script`). Summarize with `plan-reader`.
7. Run **Opening a PR** with the check-mode summary in the body.
8. **Gate:** run on the canary only. A predicate grant passes only when its check against the `--check --diff` output passes and is logged.
9. Run the same play again on the canary. Expect `changed=0`. Anything else is an idempotence bug: fix it before going wider.
10. Run `ansible-playbook --check --diff --limit <fleet batch>` for the rest of the fleet. Summarize with `plan-reader`.
11. **Gate:** the rest of the fleet with `serial`, restart-sensitive services last. Its evidence is the fleet check-mode summary, not the canary's.
12. Verify per host with a read-only check of the service the change affects, using `change-verifier`.

Never: run without `--limit`, widen past the canary before the second run shows `changed=0`, or reuse check output after the inventory or the play changed.

Calls: **ansible**, the matching OS skill (**arch-linux**, **debian-ubuntu**, **rhel-fedora**, or **nixos**).
Principles: make-operations-idempotent, reversible-first, sequence-verifiable-units.

**Reply:** canary result, idempotence result, hosts converged, and hosts held.
