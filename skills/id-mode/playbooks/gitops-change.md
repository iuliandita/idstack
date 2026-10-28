### GitOps change

**You own the rendered diff. Git is the only way in.**

For Kubernetes manifests, Helm values or charts, and Kustomize overlays delivered by ArgoCD or Flux. Load **kubernetes** for the domain. The gate block, grants, and predicates are in `references/gates.md`.

1. Find the repo's rules and the delivery path: which ArgoCD app or Flux kustomization owns these files, auto-sync and prune settings, sync waves, and which git events deploy. Record them. If the target is GitOps-managed, never `kubectl apply` it directly.
2. Pin the target: cluster context and the ArgoCD or Flux instance per `references/targets.md`.
3. Make the change in git.
4. Render every affected app with `helm template` or `kustomize build`.
5. Validate the render: `kubeconform -strict` with CRD schemas, plus the repo's linters and policy checks (kube-linter, Kyverno CLI, conftest) when present.
6. Diff against live, read-only: `argocd app diff`, `flux diff kustomization`, or `kubectl diff --server-side`.
7. Summarize large diffs with `plan-reader`. Call out CRD changes, PVC and storage changes, RBAC, NetworkPolicy, and anything with `Prune=true` that would be deleted.
8. Run **Opening a PR** with the render-and-diff summary in the body.
9. **Gate:** the merge if merge triggers auto-sync, otherwise the sync. A predicate grant passes only when its check against the rendered diff passes and is logged.
10. After sync, compare the app's synced revision to the merged git commit. "Synced/Healthy" is not proof. Wait for health with a timeout, then check the running image digests or config values that should have changed, with `change-verifier`.
11. Rollback is `git revert` through the same path, and it is a gate too.

Never: `kubectl apply` or `kubectl edit` a managed resource, or reuse a diff after the target or the base commit changed.

Calls: **kubernetes**, **kubernetes-health**.
Principles: plan-before-apply, prove-it-works, reversible-first.

**Reply:** apps affected, diff summary, synced revision vs. HEAD, health, and held items.
