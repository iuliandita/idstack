### Env promotion

**You own the difference between environments. Make it intentional.**

For carrying a change across environments (dev, QA, prod) where parity matters. The gate block, grants, and predicates are in `references/gates.md`.

1. Pin the source and target environments per `references/targets.md`. Production needs the task to say production.
2. Diff source and target for the component: values, versions, resources, secret references, storage.
3. Classify every difference as intended (sizing, hostnames, secret references) or drift. Write the intended list down.
4. Port the change, keeping the intended differences.
5. Render both environments and compare. The only remaining differences should be the intended list.
6. Continue through the target environment's change playbook (`iac-change` or `gitops-change`), with its gates. That playbook runs **Opening a PR**.
7. Verify the target behaves like the source with `change-verifier`: same dashboards populated, same alerts loaded, same health.

Never: promote past an unexplained difference, or copy a secret value between environments.

Calls: **terraform**, **kubernetes**, **observability**.
Principles: model-the-domain (an explicit list of intended differences), prove-it-works.

**Reply:** intended differences, drift found, and promotion state per environment.
