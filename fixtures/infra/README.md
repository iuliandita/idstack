# Fixture estate

A pretend estate for idstack's behavioral evals. Nothing here reaches real infrastructure:

- `terraform/` uses only the built-in `terraform_data` resource, so a plan or apply touches a local state file and nothing else.
- `k8s/` and `ansible/` are rendered and checked, never applied. Evals run with `KUBECONFIG` pointed at an empty file.

`scripts/eval.py` copies this directory to a temporary path before each run.
