# Pinning the target

Before the first command against a live system, record the target, check it matches the task, and pass it explicitly on every later command. An implicit default (current context, default profile, whatever workspace is selected) is a bug.

| Target | Read it | Pass it explicitly |
| --- | --- | --- |
| Kubernetes cluster | `kubectl config current-context`, then `kubectl --context <ctx> cluster-info` | `--context <ctx>` on every `kubectl`, `--kube-context <ctx>` on `helm` |
| Terraform, OpenTofu | backend config and `terraform workspace show` in the root module; the cloud identity below | `-chdir=<root>`; select the workspace explicitly; never rely on `TF_WORKSPACE` left in the shell |
| AWS | `aws sts get-caller-identity --profile <p>` | `--profile <p>` and `--region <r>` |
| Google Cloud | `gcloud config list`, `gcloud auth list` | `--project <id>` |
| Azure | `az account show` | `--subscription <id>` |
| Ansible | `ansible-inventory -i <inv> --graph` for the group | `-i <inv> --limit <hosts>` |
| Hosts over SSH | `ssh <host> hostname` and the OS release file | the full host alias from SSH config |
| Proxmox | `pvesh get /cluster/status` on the node | `--node <name>` and the VM or container ID |
| ArgoCD, Flux | `argocd context`, `flux check --context <ctx>` | `--server` or `--argocd-context`; `--context` for Flux |
| DNS | the zone's authoritative servers via `dig NS <zone>` | the provider account or zone ID |
| Forge (GitHub, GitLab, Forgejo) | `gh auth status`, `glab auth status` | `--repo <owner/name>` or `-R` |

**Checks before the first live command:**

1. The target matches the task's named environment (dev, QA, prod, homelab). Production needs the task to say production.
2. The estate matches the session. Work and personal targets never mix in one session.
3. The credentials are the narrowest that work. Prefer a read-only context, profile, or token for read steps. Report whether the active credentials can write.
4. Connectivity is real (VPN up, DNS resolving the internal zone) before you interpret a failure as a fault.

Record the result as the second todo item: `target: <kind> <name> (checked with <command>)`.
