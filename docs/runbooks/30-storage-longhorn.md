# Step 30 — Storage (Longhorn)

We picked Longhorn (ADR-0010) so PVCs are replicated across all three
nodes. If one node dies, the StatefulSet can come back up on another
without data loss.

## 30.1 Install

```bash
helm repo add longhorn https://charts.longhorn.io
helm repo update

helm upgrade --install longhorn longhorn/longhorn \
  --namespace longhorn-system --create-namespace \
  --version 1.7.2 \
  --set defaultSettings.defaultDataPath=/var/lib/longhorn \
  --set defaultSettings.defaultReplicaCount=2 \
  --set persistence.defaultClass=true \
  --set persistence.defaultClassReplicaCount=2 \
  --set ingress.enabled=false \
  --wait --timeout 10m
```

Replica count of **2** on a 3-node cluster is the homelab sweet spot:
the cluster survives one node going away, and we don't burn 3× disk
on every volume.

## 30.2 Verify

```bash
kubectl -n longhorn-system get pods
kubectl get storageclass
```

You should see:

- `longhorn-manager` (3 pods, one per node)
- `longhorn-driver-deployer`, `csi-*` pods all `Running`
- `longhorn` StorageClass marked `(default)`

## 30.3 Smoke-test a PVC

```bash
cat <<'YAML' | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pvc-smoke
  namespace: default
spec:
  storageClassName: longhorn
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 1Gi
YAML

kubectl -n default wait --for=jsonpath='{.status.phase}'=Bound pvc/pvc-smoke --timeout=60s
kubectl -n default delete pvc pvc-smoke
```

If the PVC reaches `Bound` and deletion succeeds, Longhorn is healthy.

## 30.4 (Optional) Longhorn UI access

```bash
kubectl -n longhorn-system port-forward svc/longhorn-frontend 8080:80
```

Open `http://localhost:8080` — useful for visually checking
volume health, snapshots, and backup-target config.

## 30.5 (Recommended) Volume snapshots to MinIO

After [step 60 (MinIO)](./60-minio.md), come back here and configure
Longhorn's S3 backup target:

```text
Longhorn UI → Setting → General
  Backup Target:           s3://longhorn-backups@us-east-1/
  Backup Target Credential Secret: longhorn-s3-secret
```

Create the secret:

```bash
kubectl -n longhorn-system create secret generic longhorn-s3-secret \
  --from-literal=AWS_ACCESS_KEY_ID=$(vault kv get -field=longhorn-access-key kv/brokerapp/minio) \
  --from-literal=AWS_SECRET_ACCESS_KEY=$(vault kv get -field=longhorn-secret-key kv/brokerapp/minio) \
  --from-literal=AWS_ENDPOINTS=http://minio.minio.svc.cluster.local:9000
```

This is independent of the BrokerApp pg_dump backups; it lets Longhorn
itself snapshot whole volumes.

Next: [40-ingress-tls.md](./40-ingress-tls.md).
