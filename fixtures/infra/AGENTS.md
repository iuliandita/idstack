# Fixture estate: agent notes

- Estate: `fixture-lab`. One environment, `staging`. There is no production here.
- Terraform: `terraform/`, local state, no backend, no lock convention.
- Kubernetes: `k8s/shop/`, namespace `shop`, delivered by `kubectl apply -k` (no GitOps controller).
- Ansible: `ansible/`, inventory `inventory.ini`, canary host `web-1`.
- Merging to the default branch does not deploy anything.
