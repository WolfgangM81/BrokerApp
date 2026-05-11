# Day-2 operations

Once steps 10–95 are done. This is the cheat sheet for everything that
comes up during the lifetime of the cluster.

## Quick health check

```bash
kubectl -n brokerapp get pods,svc,ingress,cronjobs
kubectl -n brokerapp get pvc                       # all Bound
kubectl -n brokerapp top pods                      # nothing maxed out
kubectl -n longhorn-system get volumes             # all Healthy
kubectl get certificate -A                         # all Ready=True
```

If any of these aren't green, start with `kubectl describe <resource>`
on the offender.

## Logs

### Tail one component

```bash
kubectl -n brokerapp logs -l app.kubernetes.io/component=api -f --tail=100
kubectl -n brokerapp logs -l app.kubernetes.io/component=worker -f --tail=100
kubectl -n brokerapp logs -l app.kubernetes.io/component=forecast-worker -f --tail=100
```

### Query Loki for structured logs

Grafana → **Explore** → datasource = `loki`:

```logql
# Everything from the API at INFO+ level
{namespace="brokerapp", app_kubernetes_io_component="api"}
  | json | level=~"info|warning|error"

# All errors anywhere in the namespace, last hour
{namespace="brokerapp"} |~ `"level":\s*"(error|warning)"`

# Trace a single request_id across services
{namespace="brokerapp"} | json | request_id="<paste from response header>"

# Ingest task results
{namespace="brokerapp", app_kubernetes_io_component="worker"}
  | json | logger=~"ingest\\..*"
```

## Metrics + alerts

Prometheus port-forward (or via Grafana):

```bash
kubectl -n observability port-forward svc/kps-kube-prometheus-stack-prometheus 9090
```

Useful queries:

```promql
# API request rate
sum by (handler) (rate(http_request_total{namespace="brokerapp",service="brokerapp-api"}[5m]))

# API p95 latency
histogram_quantile(0.95,
  sum by (le, handler) (rate(http_request_duration_seconds_bucket{namespace="brokerapp"}[5m])))

# Worker queue length
celery_queue_length{queue=~"ingest|forecast"}

# Forecast inference time per model
forecast_inference_seconds_sum / forecast_inference_seconds_count
```

Alertmanager (port-forward `kps-kube-prometheus-stack-alertmanager
9093`) shows active + silenced alerts. Silences are CSRF-protected; do
them through the UI.

## Database

### Open a psql

```bash
kubectl -n brokerapp exec -it brokerapp-db-0 -- \
  psql -U brokerapp -d brokerapp
```

### Run a one-off migration check

```bash
kubectl -n brokerapp run alembic-once --rm -it --restart=Never \
  --image=gitlab.orbiter:5050/wolfgangm81/brokerapp/migrate:latest \
  --env DATABASE_URL="postgresql+psycopg://brokerapp:$(kubectl -n brokerapp get secret brokerapp-db-secrets -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)@brokerapp-db:5432/brokerapp" \
  --image-pull-policy=Always -- alembic current
```

### Force a migration manually

```bash
kubectl -n brokerapp delete job brokerapp-db-migrate --ignore-not-found
helm upgrade --reuse-values --post-renderer ... # or simply re-deploy
```

The migration is a Helm hook; re-deploying re-runs it.

## Backups

### Verify last night's backup landed in MinIO

```bash
kubectl -n minio port-forward svc/minio 9000 &
mc alias set brokerapp-mc http://localhost:9000 \
  $(vault kv get -field=backup-access-key kv/brokerapp/minio) \
  $(vault kv get -field=backup-secret-key kv/brokerapp/minio)
mc ls brokerapp-mc/backups/postgres/ | tail -5
```

### Check the weekly restore-test

```bash
kubectl -n brokerapp get jobs --selector=app.kubernetes.io/name=brokerapp-restore-test
kubectl -n brokerapp logs -l app.kubernetes.io/name=brokerapp-restore-test --tail=200
```

Expect `restore-test-ok brokerapp-...dump.age` at the end. If it's
red for two weeks running, treat as an incident — see
[`restore.md`](./restore.md).

## Celery + queues

```bash
# Inspect active workers
kubectl -n brokerapp exec -it deploy/brokerapp-worker -- \
  celery -A ingest.celery_app:celery_app inspect active

# Inspect scheduled tasks
kubectl -n brokerapp exec -it deploy/brokerapp-worker -- \
  celery -A ingest.celery_app:celery_app inspect scheduled

# Purge a queue (only if you know what you're doing)
kubectl -n brokerapp exec -it deploy/brokerapp-worker -- \
  celery -A ingest.celery_app:celery_app purge -Q ingest
```

## MLflow + model promotion

Open `https://mlflow.brokerapp.orbiter/` (port-forward
`kubectl -n brokerapp port-forward svc/mlflow 5000` if you haven't
ingressed it).

Promotion flow:

1. After a nightly retrain, find the run in MLflow with the best
   backtest Sharpe / lowest RMSE for the asset class.
2. Click **Register Model** → version increments.
3. Set the stage to **Production**.
4. Restart the forecast worker so it picks up the new
   production-stage URI:
   ```bash
   kubectl -n brokerapp rollout restart deployment/brokerapp-forecast-worker
   ```

## Drift investigation

If Prometheus alert `BrokerAppDriftHigh` fires (or Grafana shows PSI

> 0.25 for any feature, see ADR-0012):

```bash
# 1. Look at the per-feature drift report from the latest backtest
kubectl -n brokerapp exec -it deploy/brokerapp-forecast-worker -- \
  python -c "from forecast.tasks import drift_summary; print(drift_summary())"

# 2. Force a backtest re-run and compare
kubectl -n brokerapp exec -it deploy/brokerapp-forecast-worker -- \
  celery -A forecast.celery_app:celery_app call forecast.backtest_asset \
  --args='["<asset-uuid>","lightgbm",5]'

# 3. If the new model is materially better, promote it via MLflow.
```

## Scaling

| Resource             | Knob                                        | Why                     |
| -------------------- | ------------------------------------------- | ----------------------- |
| API replicas         | `helm upgrade ... --set api.replicaCount=N` | RPS pressure            |
| Worker replicas      | `... --set worker.replicaCount=N`           | ingest queue depth      |
| Forecast workers     | `... --set forecastWorker.replicaCount=N`   | nightly retrain backlog |
| DB volume            | grow Longhorn PVC + `pg_repack`             | bars table size         |
| Prometheus retention | `kps` values                                | space crunch            |

Auto-scaling: `api` has HPA disabled by default
(`autoscaling.enabled=false`). Flip it to true when there's real
traffic; CPU target 75% works for our workload.

## Disaster recovery

See [restore.md](./restore.md) — the runbook for "the DB is gone" /
"the cluster is gone".

## Updating the cluster

| What                  | How                                                                              |
| --------------------- | -------------------------------------------------------------------------------- |
| k3s                   | `curl -sfL https://get.k3s.io \| sh -` on each node, one at a time               |
| Longhorn              | `helm upgrade longhorn longhorn/longhorn --reuse-values --version <new>`         |
| cert-manager          | `helm upgrade cert-manager jetstack/cert-manager --reuse-values --version <new>` |
| kube-prometheus-stack | `helm upgrade kps ... --reuse-values --version <new>`                            |
| BrokerApp itself      | normal `git push` → CI runs `helm upgrade`                                       |

Always check release notes for breaking changes (especially Longhorn
and kube-prometheus-stack).
