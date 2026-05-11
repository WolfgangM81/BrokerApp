# Step 50 — Monitoring (Prometheus + Loki + Grafana + Alertmanager)

The repo ships with the values files; this runbook only commands `helm
upgrade --install` and then verifies.

## 50.1 Add Helm repos

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana             https://grafana.github.io/helm-charts
helm repo update
```

## 50.2 kube-prometheus-stack

```bash
helm upgrade --install kps prometheus-community/kube-prometheus-stack \
  --namespace observability --create-namespace \
  --version 65.0.0 \
  -f infra/helm/observability/kube-prometheus-stack-values.yaml \
  --wait --timeout 15m
```

This installs:

- Prometheus (15-day retention, 50 GiB on Longhorn)
- Alertmanager (routes via webhook → `https://ntfy.orbiter/brokerapp-alerts`)
- Grafana (Ingress `grafana.brokerapp.orbiter`)
- kube-state-metrics + node-exporter
- Default ServiceMonitors for the cluster

### Set the Grafana admin password

```bash
kubectl -n observability create secret generic grafana-admin \
  --from-literal=admin-user=admin \
  --from-literal=admin-password=$(openssl rand -hex 24)

# point Grafana at it
kubectl -n observability patch deployment kps-grafana --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/env/-","value":{"name":"GF_SECURITY_ADMIN_PASSWORD","valueFrom":{"secretKeyRef":{"name":"grafana-admin","key":"admin-password"}}}}]'

# get the password to log in with
kubectl -n observability get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d; echo
```

## 50.3 Loki + Promtail

```bash
helm upgrade --install loki grafana/loki \
  --namespace observability \
  --version 6.16.0 \
  -f infra/helm/observability/loki-values.yaml \
  --wait --timeout 10m

helm upgrade --install promtail grafana/promtail \
  --namespace observability \
  --version 6.16.6 \
  -f infra/helm/observability/promtail-values.yaml \
  --wait --timeout 5m
```

Promtail runs as a DaemonSet on every node and ships container logs to
Loki. It parses our `structlog` JSON lines and tags them with `level`,
`request_id`, and `service` so you can query them in Grafana.

## 50.4 Add Loki as a Grafana datasource

Grafana → **Settings** (gear icon) → **Data sources** → **Add data source**:

| Field   | Value                                                 |
| ------- | ----------------------------------------------------- |
| Type    | Loki                                                  |
| Name    | `loki`                                                |
| URL     | `http://loki-gateway.observability.svc.cluster.local` |
| Default | ✅                                                    |

Click **Save & test** — should show _"Data source connected"_.

## 50.5 Verify the BrokerApp ServiceMonitor is being scraped

Once the API is deployed (step 95):

```bash
kubectl -n observability port-forward svc/kps-kube-prometheus-stack-prometheus 9090
```

Open `http://localhost:9090/targets` → look for `serviceMonitor/brokerapp/brokerapp-api`.
Status should be `UP` for both replicas.

## 50.6 Alertmanager → ntfy

The `kube-prometheus-stack-values.yaml` already wires Alertmanager to
post resolved + firing alerts to `https://ntfy.orbiter/brokerapp-alerts`.

Test it manually:

```bash
kubectl -n observability port-forward svc/kps-kube-prometheus-stack-alertmanager 9093 &
amtool alert add \
  --alertmanager.url=http://localhost:9093 \
  alertname=TestAlert severity=warning instance=manual-test \
  --annotation=summary="Phase-50 smoke test"
```

You should get an ntfy notification within ~30 s.

## 50.7 Open Grafana

Once DNS / cert is up (step 40):

```bash
open https://grafana.brokerapp.orbiter/
```

Log in with `admin` / the password from §50.2. Default dashboards:

- Kubernetes / Compute Resources / Cluster
- Kubernetes / Compute Resources / Namespace (Pods)
- Node Exporter / Nodes

BrokerApp-specific dashboards land in `infra/grafana-dashboards/` and
will be imported via the `grafana_dashboard` ConfigMap label in a
later phase.

Next: [60-minio.md](./60-minio.md).
