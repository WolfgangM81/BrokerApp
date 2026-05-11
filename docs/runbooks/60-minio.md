# Step 60 — MinIO (object storage)

MinIO backs:
- `mlflow` bucket — MLflow artifacts (models, plots, metrics blobs)
- `backups` bucket — nightly age-encrypted pg_dump archives
- `longhorn-backups` bucket — Longhorn volume snapshots (optional)

## 60.1 Install MinIO

```bash
helm repo add minio https://charts.min.io
helm repo update

# generate strong root credentials
ROOT_USER=brokerapp-admin
ROOT_PASS=$(openssl rand -hex 32)

helm upgrade --install minio minio/minio \
  --namespace minio --create-namespace \
  --version 5.3.0 \
  --set mode=standalone \
  --set persistence.enabled=true \
  --set persistence.storageClass=longhorn \
  --set persistence.size=200Gi \
  --set rootUser="$ROOT_USER" \
  --set rootPassword="$ROOT_PASS" \
  --set replicas=1 \
  --set resources.requests.memory=1Gi \
  --set ingress.enabled=false \
  --set consoleIngress.enabled=false \
  --wait --timeout 10m

echo "ROOT_USER=$ROOT_USER"
echo "ROOT_PASS=$ROOT_PASS"
```

> **Write `ROOT_PASS` down now** — you'll put it in Vault in step 80.

## 60.2 mc client → cluster-internal alias

From your workstation:

```bash
kubectl -n minio port-forward svc/minio 9000:9000 &
MC_FW_PID=$!
mc alias set brokerapp-mc http://localhost:9000 "$ROOT_USER" "$ROOT_PASS"
```

## 60.3 Create the buckets and per-purpose access keys

```bash
# Buckets
mc mb --ignore-existing brokerapp-mc/mlflow
mc mb --ignore-existing brokerapp-mc/backups
mc mb --ignore-existing brokerapp-mc/longhorn-backups
mc anonymous set none brokerapp-mc/mlflow
mc anonymous set none brokerapp-mc/backups
mc anonymous set none brokerapp-mc/longhorn-backups

# Service users (scoped credentials, kept in Vault)
gen() {
  user=$1; secret=$(openssl rand -hex 24)
  mc admin user add brokerapp-mc "$user" "$secret"
  mc admin policy attach brokerapp-mc readwrite --user "$user"
  echo "$user=$secret"
}

gen mlflow
gen backup
gen longhorn

kill "$MC_FW_PID"
```

The three `<user>=<secret>` lines are what you'll feed Vault in step 80.
Keep them safe.

## 60.4 (Optional) MinIO Console

```bash
kubectl -n minio port-forward svc/minio-console 9001:9001
# open http://localhost:9001
# user: $ROOT_USER  password: $ROOT_PASS
```

The console is where you can inspect bucket contents and ACLs without
the CLI.

## 60.5 Verify the MLflow → MinIO contract

This is just a sanity ping; the actual MLflow server starts as a
sub-chart in step 95.

```bash
kubectl -n minio port-forward svc/minio 9000:9000 &
mc cp /etc/hosts brokerapp-mc/mlflow/test/hosts
mc ls brokerapp-mc/mlflow/test/
mc rm brokerapp-mc/mlflow/test/hosts
kill %1
```

If the upload, list, and delete all work, MinIO is healthy.

Next: [70-authentik.md](./70-authentik.md).
