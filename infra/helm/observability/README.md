# Observability stack — kube-prometheus-stack + Loki

These are _external_ upstream charts with our values overrides; we do not
package them. Install once per cluster.

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm upgrade --install kps prometheus-community/kube-prometheus-stack \
  --namespace observability --create-namespace \
  -f infra/helm/observability/kube-prometheus-stack-values.yaml

helm upgrade --install loki grafana/loki \
  --namespace observability \
  -f infra/helm/observability/loki-values.yaml

helm upgrade --install promtail grafana/promtail \
  --namespace observability \
  -f infra/helm/observability/promtail-values.yaml
```

The BrokerApp namespace's `ServiceMonitor` for `api` is picked up
automatically because the kube-prometheus-stack is installed cluster-wide
with `serviceMonitorSelectorNilUsesHelmValues: false`.
