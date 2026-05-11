# Step 95 — First deploy + smoke tests

Steps 10–90 prepared a *cluster that can host BrokerApp*. This runbook
actually deploys it and walks through "did it work?".

## 95.1 Pre-flight checklist

```bash
# k8s ready
kubectl get nodes -o wide                       # 3× Ready
kubectl -n brokerapp get resourcequota           # quota in place

# Storage ready
kubectl get sc | grep -i longhorn                # default StorageClass

# TLS ready
kubectl get clusterissuer brokerapp-internal-ca  # Ready=True

# Monitoring ready
kubectl -n observability get pods | grep -v Running | wc -l   # expect 1 (header)

# MinIO ready
kubectl -n minio get pods                        # Running

# Secrets pre-populated (from step 90.5)
kubectl -n brokerapp get secrets \
  brokerapp-db-secrets brokerapp-api-secrets \
  brokerapp-web-secrets brokerapp-worker-secrets \
  brokerapp-forecast-worker-secrets brokerapp-backup-secrets \
  gitlab-registry
```

If anything is missing, go back to its runbook.

## 95.2 First deploy via GitLab CI (canonical path)

```bash
git push origin claude/stock-forecast-app-kmWQG
```

Watch the pipeline. On main merge, the `deploy:k8s` job runs:

1. `helm dependency update infra/helm/umbrella`
2. `helm upgrade --install brokerapp infra/helm/umbrella ...`
   - Sub-charts: db, api, web, worker, forecast-worker, backup
   - Tags wired to `$CI_COMMIT_SHORT_SHA`
3. `--wait --timeout 10m` for everything to roll out

When the job is green, jump to 95.4.

## 95.3 First deploy from your workstation (only if CI is blocked)

```bash
helm dependency update infra/helm/umbrella

SHA=$(git rev-parse --short HEAD)

helm upgrade --install brokerapp infra/helm/umbrella \
  --namespace brokerapp --create-namespace \
  --set api.image.tag="$SHA" \
  --set web.image.tag="$SHA" \
  --set worker.image.tag="$SHA" \
  --set forecastWorker.image.tag="$SHA" \
  --set db.migration.image.tag="$SHA" \
  --wait --timeout 10m
```

If you haven't pushed images yet, you can `--set <comp>.image.tag=latest`
to use whatever's in the registry. But CI is the supported path.

## 95.4 Watch the rollout

```bash
watch -n2 kubectl -n brokerapp get pods,svc,ingress
```

Order of events:
1. `brokerapp-db-0` reaches `Running` (~30 s).
2. `brokerapp-db-migrate-<hash>` Job runs and reaches `Completed`.
   ```bash
   kubectl -n brokerapp logs job/brokerapp-db-migrate-<hash>
   ```
   You should see Alembic upgrade output ending in
   `INFO  [alembic.runtime.migration] Running upgrade ... -> 0003_trade_journal_and_paper`.
3. API, web, worker, forecast-worker pods reach `Running` (~30–90 s).
4. Ingresses get certs (~30 s after first reconciliation):
   ```bash
   kubectl -n brokerapp get certificate
   # both should be Ready=True
   ```

## 95.5 Smoke tests

### Health endpoint

```bash
curl -sS https://api.brokerapp.orbiter/healthz | jq .
# {"status":"ok","version":"0.1.0","timestamp":"..."}

curl -sS https://api.brokerapp.orbiter/readyz | jq .
# {"status":"ok","checks":[{"name":"postgres","ok":true},{"name":"redis","ok":true}]}
```

### Browser

Open `https://brokerapp.orbiter` — should redirect you to
`/auth/signin`, then through Authentik, then back to the dashboard.

### Asset → Watchlist → Backfill chain

The full Phase-1 acceptance check:

1. Log in.
2. Use the API (`/docs`) or your favourite REST client (with the
   Bearer token from the SessionProvider) to add an asset:
   ```bash
   TOKEN=$(...)   # capture from browser devtools (Application → Cookies →
                  # __Secure-authjs.session-token would need a Server-Action
                  # to surface the access_token — easier path is to call
                  # the API from the web UI's "add asset" page once it's built).
   curl -sS -X POST https://api.brokerapp.orbiter/v1/assets \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"symbol":"SPY","asset_class":"etf","source":"yfinance","exchange":"NYSEARCA","currency":"USD","calendar":"XNYS"}' | jq .
   ```
3. Create a watchlist and add SPY to it (via the web UI is easier).
4. Within ~60 s, check:
   ```bash
   kubectl -n brokerapp logs -l app.kubernetes.io/component=worker --tail=100 | grep backfill_done
   ```
   You should see `backfill_done asset_id=... rows=<number>`.
5. Confirm the data made it to the DB:
   ```bash
   kubectl -n brokerapp exec -it brokerapp-db-0 -- \
     psql -U brokerapp -d brokerapp -c \
     "SELECT count(*) FROM market.bars b JOIN app.assets a ON a.id=b.asset_id WHERE a.symbol='SPY';"
   ```
6. Fetch bars via the API:
   ```bash
   ASSET_ID=$(curl -sS https://api.brokerapp.orbiter/v1/assets?q=SPY \
     -H "Authorization: Bearer $TOKEN" | jq -r '.items[0].id')
   curl -sS "https://api.brokerapp.orbiter/v1/assets/$ASSET_ID/bars?granularity=1d&limit=5" \
     -H "Authorization: Bearer $TOKEN" | jq '.bars[0]'
   ```

### Forecast smoke (after some bars exist)

```bash
curl -sS -X POST "https://api.brokerapp.orbiter/v1/assets/$ASSET_ID/forecasts/run" \
  -H "Authorization: Bearer $TOKEN"
# {"asset_id":"...","dispatched":true,"model":"lightgbm"}

kubectl -n brokerapp logs -l app.kubernetes.io/component=forecast-worker --tail=200 | grep forecast_done
```

After completion:

```bash
curl -sS "https://api.brokerapp.orbiter/v1/assets/$ASSET_ID/forecasts" \
  -H "Authorization: Bearer $TOKEN" | jq '.[0]'
```

## 95.6 Set the production CronJobs running (already enabled by default)

- Ingest beat → universe refresh every 15 min during market hours
  (queue `ingest`)
- Forecast beat → nightly retrain at 01:30 UTC (queue `forecast`)
- Backup CronJob → 01:30 UTC nightly (separate queue / namespace)
- Restore-test CronJob → Sundays 04:30 UTC

```bash
kubectl -n brokerapp get cronjobs
```

If a job is suspended unexpectedly, `kubectl patch cronjob <name>
--type=merge -p '{"spec":{"suspend": false}}'`.

## 95.7 Verify monitoring

Open Grafana → **Explore** → datasource = `loki`:

```logql
{namespace="brokerapp"} | json | level="info"
```

You should see streaming log lines from API, worker, and forecast
pods, with `request_id`, `level`, and `service` extracted.

Prometheus targets (port-forward as in step 50): should now show
`UP` for `brokerapp-api`, `brokerapp-forecast-worker`,
`brokerapp-worker` (once they expose a `/metrics` endpoint —
Phase-1 has it on the API only).

## 95.8 Done

If steps 95.5–95.7 passed, BrokerApp is in production.

For day-to-day work, switch to [day2-operations.md](./day2-operations.md).
