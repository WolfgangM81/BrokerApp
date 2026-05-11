# Cluster bring-up — overview

This runbook brings BrokerApp from **three blank Lenovo m75q boxes** to a
running cluster serving `https://brokerapp.orbiter`. Every step is either
a copy-pasteable shell command or a UI walkthrough with the exact field
names you'll see.

## Reading order

| # | Runbook | Where it runs | Time |
|---|---|---|---|
| 10 | [Hardware + OS prep](./10-prereqs.md) | each Lenovo node | ~30 min × 3 |
| 20 | [Kubernetes (k3s)](./20-kubernetes.md) | 1 server + 2 agents | ~15 min |
| 30 | [Storage (Longhorn)](./30-storage-longhorn.md) | cluster | ~10 min |
| 40 | [Ingress + TLS](./40-ingress-tls.md) | cluster | ~10 min |
| 50 | [Monitoring stack](./50-monitoring.md) | cluster | ~15 min |
| 60 | [MinIO (object store)](./60-minio.md) | cluster | ~10 min |
| 70 | [Authentik OIDC apps](./70-authentik.md) | Authentik UI | ~10 min |
| 80 | [Vault secrets](./80-vault.md) | Vault UI + CLI | ~15 min |
| 90 | [GitLab CI](./90-gitlab-ci.md) | GitLab UI | ~10 min |
| 95 | [First deploy + smoke tests](./95-deploy.md) | local + cluster | ~20 min |
| — | [Day-2 operations](./day2-operations.md) | reference | n/a |
| — | [Restore from backup](./restore.md) | when needed | reference |

Total green-field bring-up: roughly **3 hours of attention** plus the
unattended bits (OS install, image builds).

## What you need before you start

- **Three Lenovo m75q** (Ryzen 5 PRO 3400GE, 32 GB, ≥256 GB NVMe each).
- A workstation with `ssh`, `kubectl`, `helm`, `git`, `jq`, `yq`,
  `mc` (MinIO client), `vault`, and `age` installed.
- An **already-running ZeroTier network** that the three nodes will join.
- An **already-running Authentik** instance reachable at
  `https://auth.orbiter`.
- An **already-running Vault** instance reachable at
  `https://vault.orbiter`.
- An **already-running GitLab** at `https://gitlab.orbiter` with a
  project at `wolfgangm81/brokerapp` and the container registry on
  port `5050`.
- DNS / hosts entries for the homelab — see step 40.

## Naming conventions used throughout

| Name | Value |
|---|---|
| Internal domain | `*.orbiter` |
| App domain | `brokerapp.orbiter`, `api.brokerapp.orbiter` |
| Cluster nodes | `m75q-01`, `m75q-02`, `m75q-03` |
| k8s context | `brokerapp` |
| Namespace | `brokerapp` |
| GitLab registry | `gitlab.orbiter:5050/wolfgangm81/brokerapp/<image>` |
| Vault KV mount | `kv/brokerapp/...` |

## Automation versus by hand

Anything that can run unattended is in `infra/scripts/bootstrap-cluster.sh`.
The script is **idempotent**: re-running it after a failure picks up
where you left off.

Anything that requires UI clicks or one-time secrets stays in these
runbooks. Each manual step lists the **exact** form fields and the
**exact** values to enter — you don't need to read the underlying
Authentik / Vault / GitLab docs.
