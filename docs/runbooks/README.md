# Runbooks

Operational documentation. Two flavors:

## 1. Cluster bring-up (one-time, in order)

Start at [`00-overview.md`](./00-overview.md). The numbered files walk
from "three blank Lenovo m75q boxes" to "BrokerApp running at
https://brokerapp.orbiter":

| Step | Topic |
|------|-------|
| [00](./00-overview.md) | Overview, reading order, prerequisites |
| [10](./10-prereqs.md) | Hardware + OS prep (Ubuntu LTS, ZeroTier, SSH) |
| [20](./20-kubernetes.md) | k3s 3-node cluster |
| [30](./30-storage-longhorn.md) | Longhorn storage |
| [40](./40-ingress-tls.md) | Traefik + cert-manager + internal CA |
| [50](./50-monitoring.md) | kube-prometheus-stack + Loki + Grafana |
| [60](./60-minio.md) | MinIO object storage |
| [70](./70-authentik.md) | Authentik OIDC applications |
| [80](./80-vault.md) | Vault secrets (KV-v2 layout + values) |
| [90](./90-gitlab-ci.md) | GitLab Runner, CI variables, registry pull secret |
| [95](./95-deploy.md) | First `helm upgrade` + smoke tests |

Automated bootstrap of the in-cluster pieces:

```bash
export KUBECONFIG=~/.kube/brokerapp.yaml
bash infra/scripts/bootstrap-cluster.sh
```

The script is idempotent. It installs Longhorn, cert-manager,
kube-prometheus-stack, Loki, Promtail, and MinIO. UI-clicks-only
steps (Authentik, Vault, GitLab CI) stay in their respective
runbooks.

## 2. Day-to-day operations (reference)

- [`day2-operations.md`](./day2-operations.md) — health checks, log
  queries, metrics, backups, Celery, MLflow promotion, drift, scaling.
- [`restore.md`](./restore.md) — DB restore from backup, cluster
  rebuild procedure.
