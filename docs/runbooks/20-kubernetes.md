# Step 20 — Kubernetes (k3s)

We use [k3s](https://k3s.io/) because:

- single binary, no etcd-by-hand,
- Traefik comes preinstalled (we'll just configure it),
- ServiceLB makes a homelab `LoadBalancer` reachable on every node IP.

## 20.1 Install the server on `m75q-01`

```bash
ssh m75q-01 << 'EOF'
curl -sfL https://get.k3s.io | sh -s - server \
  --cluster-init \
  --tls-san m75q-01.orbiter \
  --tls-san brokerapp.orbiter \
  --write-kubeconfig-mode 644 \
  --disable=local-storage    # we use Longhorn instead
EOF
```

Grab the join token:

```bash
TOKEN=$(ssh m75q-01 'sudo cat /var/lib/rancher/k3s/server/node-token')
echo "$TOKEN" > /tmp/k3s-token
```

## 20.2 Join the two agents

```bash
for n in m75q-02 m75q-03; do
  ssh "$n" K3S_TOKEN="$TOKEN" 'sh -c "curl -sfL https://get.k3s.io | K3S_URL=https://m75q-01.orbiter:6443 K3S_TOKEN=$K3S_TOKEN sh -"'
done
```

Wait ~60 seconds, then verify on `m75q-01`:

```bash
ssh m75q-01 'sudo kubectl get nodes -o wide'
```

You should see three `Ready` nodes.

## 20.3 Pull the kubeconfig to your workstation

```bash
mkdir -p ~/.kube
ssh m75q-01 'sudo cat /etc/rancher/k3s/k3s.yaml' \
  | sed "s/127.0.0.1/m75q-01.orbiter/" \
  > ~/.kube/brokerapp.yaml
chmod 600 ~/.kube/brokerapp.yaml
export KUBECONFIG=~/.kube/brokerapp.yaml
kubectl config rename-context default brokerapp
kubectl get nodes
```

Keep `export KUBECONFIG=~/.kube/brokerapp.yaml` in your shell rc (or
merge it into `~/.kube/config` if you prefer).

## 20.4 Create the namespace

```bash
kubectl create namespace brokerapp
kubectl label namespace brokerapp pod-security.kubernetes.io/enforce=baseline
```

## 20.5 Resource quota (defense-in-depth)

```bash
cat <<'YAML' | kubectl apply -n brokerapp -f -
apiVersion: v1
kind: ResourceQuota
metadata:
  name: brokerapp-quota
spec:
  hard:
    requests.cpu: "20"        # whole-cluster budget: 24 cores - 4 for the OS
    requests.memory: 80Gi
    limits.cpu: "40"
    limits.memory: 160Gi
    persistentvolumeclaims: "30"
YAML
```

## 20.6 Make `brokerapp` the default ns for our context

```bash
kubectl config set-context --current --namespace=brokerapp
```

## 20.7 Sanity

```bash
kubectl run hello --image=busybox --restart=Never --command -- sleep 5
kubectl wait --for=condition=Ready pod/hello --timeout=30s
kubectl logs hello && kubectl delete pod hello
```

If `kubectl get pods` shows `Running` then `Completed`, the cluster
is healthy and you can move on.

Next: [30-storage-longhorn.md](./30-storage-longhorn.md).
