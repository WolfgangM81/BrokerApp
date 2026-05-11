#!/usr/bin/env bash
# Bootstrap a fresh k3s cluster with everything BrokerApp needs.
#
# Idempotent. Re-running after a failure picks up where you left off.
# What it does NOT do:
#   - install the OS / configure ZeroTier on the three nodes (step 10)
#   - install k3s itself (step 20 — uses SSH which is too easy to break)
#   - configure Authentik / Vault / GitLab (steps 70 / 80 / 90 — UI clicks)
#   - run the actual `helm upgrade brokerapp ...` (step 95 — that's CI's job)
#
# What it does:
#   - Longhorn
#   - cert-manager + ClusterIssuer
#   - kube-prometheus-stack + Loki + Promtail
#   - MinIO
#   - Namespace + ResourceQuota
#   - gitlab-registry pull secret (interactive prompt for the deploy token)
#
# Usage:
#   export KUBECONFIG=~/.kube/brokerapp.yaml
#   bash infra/scripts/bootstrap-cluster.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# ---------- pretty ----------
log()  { printf '\033[1;34m[bootstrap]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[ok]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[fail]\033[0m %s\n' "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "missing prerequisite: $1"; }

need kubectl
need helm
need openssl
[[ -n "${KUBECONFIG:-}" ]] || die "KUBECONFIG is not set"
kubectl get nodes >/dev/null 2>&1 || die "kubectl can't reach the cluster (\$KUBECONFIG=$KUBECONFIG)"

helm_install() {
  # $1 release  $2 chart  $3 namespace  $4 version  $5+ extra args
  local release="$1" chart="$2" ns="$3" version="$4"
  shift 4
  log "helm upgrade --install $release ($version)"
  helm upgrade --install "$release" "$chart" \
    --namespace "$ns" --create-namespace \
    --version "$version" \
    --wait --timeout 15m \
    "$@"
}

# ---------- Helm repos ----------
log "adding helm repos"
helm repo add longhorn             https://charts.longhorn.io                 2>/dev/null || true
helm repo add jetstack             https://charts.jetstack.io                 2>/dev/null || true
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
helm repo add grafana              https://grafana.github.io/helm-charts      2>/dev/null || true
helm repo add minio                https://charts.min.io                      2>/dev/null || true
helm repo update >/dev/null

# ---------- Namespace + Quota ----------
if ! kubectl get namespace brokerapp >/dev/null 2>&1; then
  kubectl create namespace brokerapp
fi
kubectl label namespace brokerapp pod-security.kubernetes.io/enforce=baseline --overwrite

cat <<'YAML' | kubectl apply -n brokerapp -f - >/dev/null
apiVersion: v1
kind: ResourceQuota
metadata:
  name: brokerapp-quota
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 80Gi
    limits.cpu: "40"
    limits.memory: 160Gi
    persistentvolumeclaims: "30"
YAML
ok "namespace + quota"

# ---------- Longhorn ----------
helm_install longhorn longhorn/longhorn longhorn-system 1.7.2 \
  --set defaultSettings.defaultDataPath=/var/lib/longhorn \
  --set defaultSettings.defaultReplicaCount=2 \
  --set persistence.defaultClass=true \
  --set persistence.defaultClassReplicaCount=2 \
  --set ingress.enabled=false
ok "longhorn"

# ---------- cert-manager + ClusterIssuer ----------
helm_install cert-manager jetstack/cert-manager cert-manager v1.16.1 \
  --set installCRDs=true
log "applying ClusterIssuer manifest"
kubectl apply -f "$REPO_ROOT/infra/helm/observability/cluster-issuer.yaml" >/dev/null
# Wait for the CA Certificate to be Ready before declaring success.
for _ in $(seq 1 60); do
  status=$(kubectl -n cert-manager get certificate brokerapp-internal-ca \
    -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)
  [[ "$status" == "True" ]] && break
  sleep 2
done
[[ "$status" == "True" ]] || die "ClusterIssuer CA never reached Ready"
ok "cert-manager + ClusterIssuer"

# ---------- kube-prometheus-stack ----------
helm_install kps prometheus-community/kube-prometheus-stack observability 65.0.0 \
  -f "$REPO_ROOT/infra/helm/observability/kube-prometheus-stack-values.yaml"
ok "kube-prometheus-stack"

# ---------- Loki + Promtail ----------
helm_install loki     grafana/loki     observability 6.16.0 \
  -f "$REPO_ROOT/infra/helm/observability/loki-values.yaml"
helm_install promtail grafana/promtail observability 6.16.6 \
  -f "$REPO_ROOT/infra/helm/observability/promtail-values.yaml"
ok "loki + promtail"

# ---------- MinIO ----------
if kubectl -n minio get secret minio-credentials >/dev/null 2>&1; then
  log "minio root credentials already exist — reusing"
  ROOT_USER=$(kubectl -n minio get secret minio-credentials -o jsonpath='{.data.root-user}' | base64 -d)
  ROOT_PASS=$(kubectl -n minio get secret minio-credentials -o jsonpath='{.data.root-password}' | base64 -d)
else
  ROOT_USER=brokerapp-admin
  ROOT_PASS=$(openssl rand -hex 32)
  kubectl create namespace minio 2>/dev/null || true
  kubectl -n minio create secret generic minio-credentials \
    --from-literal=root-user="$ROOT_USER" \
    --from-literal=root-password="$ROOT_PASS"
fi
helm_install minio minio/minio minio 5.3.0 \
  --set mode=standalone \
  --set persistence.enabled=true \
  --set persistence.storageClass=longhorn \
  --set persistence.size=200Gi \
  --set existingSecret=minio-credentials \
  --set replicas=1 \
  --set resources.requests.memory=1Gi \
  --set ingress.enabled=false \
  --set consoleIngress.enabled=false
ok "minio  (root user: $ROOT_USER — password is in secret minio/minio-credentials)"

cat <<EOF
====================================================================
 Next, run the manual steps below — they need UI clicks or one-time
 secrets that this script intentionally does NOT touch.

  1. infra/scripts/bootstrap-cluster.sh  (this)                ✓
  2. docs/runbooks/60-minio.md            (mc user creation)
  3. docs/runbooks/70-authentik.md        (OIDC apps in UI)
  4. docs/runbooks/80-vault.md            (vault kv put ...)
  5. docs/runbooks/90-gitlab-ci.md        (Variables + pull secret)
  6. docs/runbooks/95-deploy.md           (helm upgrade via CI)

 MinIO root credentials are persisted in:
   kubectl -n minio get secret minio-credentials -o yaml
 Don't print them to logs.
====================================================================
EOF
