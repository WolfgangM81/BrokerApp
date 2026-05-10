# BrokerApp Helm charts

Three sub-charts (`api`, `web`, `worker`) and an `umbrella` chart that bundles
them. Deployed by the GitLab CI pipeline (see `.gitlab-ci.yml`) via
`helm upgrade --install`.

## Layout

```
infra/helm/
├── api/         # FastAPI gateway
├── web/         # Next.js frontend
├── worker/      # Celery worker (+ beat, optional)
└── umbrella/    # bundles api + web + worker
```

## Local lint / template

```bash
helm dependency update infra/helm/umbrella

helm lint   infra/helm/umbrella
helm template brokerapp infra/helm/umbrella --namespace brokerapp
```

## Deploy (manual, debugging only)

CI/CD is the canonical path. For ad-hoc debugging:

```bash
helm upgrade --install brokerapp infra/helm/umbrella \
  --namespace brokerapp \
  --create-namespace \
  --set api.image.tag=$(git rev-parse --short HEAD) \
  --set web.image.tag=$(git rev-parse --short HEAD) \
  --set worker.image.tag=$(git rev-parse --short HEAD)
```

## Secrets

This skeleton expects three opaque secrets to exist in the namespace, created
by the GitLab CI pipeline from Vault-sourced variables:

- `brokerapp-api-secrets`
- `brokerapp-web-secrets`
- `brokerapp-worker-secrets`

The Vault → CI Variables → k8s Secret materialization is implemented in Phase 4.
For now the charts reference these names so the structure is in place.
