# Step 40 — Ingress + TLS

k3s ships with Traefik. We add cert-manager and a self-signed internal
CA so the `*.brokerapp.orbiter` ingresses get real certificates that
your browsers / clients can pin.

## 40.1 Verify Traefik is up

```bash
kubectl -n kube-system get pods -l app.kubernetes.io/name=traefik
kubectl -n kube-system get svc traefik
```

The `traefik` Service is of type `LoadBalancer`. k3s's ServiceLB
("klipper-lb") binds it to **every node IP on ports 80 + 443**. So
hitting any of the three m75q IPs reaches Traefik.

> Production fronting:
> point your homelab router / firewall (or `keepalived` if you want
> failover) at one of the node IPs for `*.orbiter`.

## 40.2 Install cert-manager

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update

helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --version v1.16.1 \
  --set installCRDs=true \
  --wait --timeout 5m

kubectl -n cert-manager get pods
```

## 40.3 Apply the BrokerApp ClusterIssuer

The manifest ships in the repo:

```bash
kubectl apply -f infra/helm/observability/cluster-issuer.yaml
```

This creates:

- `ClusterIssuer/brokerapp-internal-selfsigned` (boot-strap-only)
- `Certificate/brokerapp-internal-ca` (10-year CA root, in `cert-manager` ns)
- `ClusterIssuer/brokerapp-internal-ca` (signs everything ending in `.orbiter`)

Verify:

```bash
kubectl -n cert-manager get certificate brokerapp-internal-ca \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}{"\n"}'
# expect: True
```

## 40.4 Export the CA root and trust it on your devices

```bash
kubectl -n cert-manager get secret brokerapp-internal-ca-key-pair \
  -o jsonpath='{.data.tls\.crt}' | base64 -d > ~/.local/share/brokerapp-ca.crt
```

Trust it system-wide:

- **macOS**: `sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/.local/share/brokerapp-ca.crt`
- **Linux (Debian/Ubuntu)**:
  ```bash
  sudo cp ~/.local/share/brokerapp-ca.crt /usr/local/share/ca-certificates/brokerapp-ca.crt
  sudo update-ca-certificates
  ```
- **iOS / Android**: AirDrop / push the `.crt`, install as profile, then **enable trust** in Settings → General → About → Certificate Trust Settings.

> Without this step, browsers will refuse to load `https://brokerapp.orbiter`
> and the mobile app's OIDC redirect will fail.

## 40.5 DNS — point `*.brokerapp.orbiter` at the cluster

Add to your homelab DNS (Pi-hole / Unbound / AdGuard Home) — pick one
node IP, or a keepalived VIP:

```text
brokerapp.orbiter.        A  192.168.10.11
api.brokerapp.orbiter.    A  192.168.10.11
mlflow.brokerapp.orbiter. A  192.168.10.11
grafana.brokerapp.orbiter.A  192.168.10.11
```

> ZeroTier clients: add the same entries to whatever resolver they use,
> or push a static `/etc/hosts` snippet via Ansible.

## 40.6 Smoke test — get a cert for a throwaway domain

```bash
cat <<'YAML' | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: ping-orbiter
  namespace: default
spec:
  secretName: ping-orbiter-tls
  issuerRef:
    name: brokerapp-internal-ca
    kind: ClusterIssuer
  commonName: ping.orbiter
  dnsNames:
    - ping.orbiter
YAML

kubectl -n default wait --for=condition=Ready certificate/ping-orbiter --timeout=60s
kubectl -n default delete certificate ping-orbiter
kubectl -n default delete secret ping-orbiter-tls
```

If the certificate reaches `Ready=True` within a minute, the chain is
healthy and you can move on.

Next: [50-monitoring.md](./50-monitoring.md).
