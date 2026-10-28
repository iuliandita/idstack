### Babysit (idstack overlay)

Read the shared playbook first: pstack `poteto-mode/playbooks/babysit.md`.

Then apply these gates. They win on conflict.

1. Resolve the forge and use its CLI throughout: `gh` for GitHub, `glab` for GitLab, the forge's API for Forgejo or Gitea.
2. Before any merge, find out whether merging deploys (auto-sync, CI apply, release on tag) per `references/gates.md`. A merge that deploys is a gate.
3. Classify each CI failure as flake, infrastructure, or real before acting. Retrigger only a flake or infrastructure failure, at most once per failure, with a fresh run. A real failure goes back to the change.
4. A plan or render attached to the PR goes stale when the base moves or another apply lands. Produce it again before the gate.
