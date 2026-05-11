# Step 90 — GitLab CI variables + runner + registry

## 90.1 GitLab Runner — if you don't already have one

If `gitlab.orbiter` already has a shared runner that can talk to your
homelab, **skip this section**. Otherwise install a runner pod inside
the cluster:

```bash
helm repo add gitlab https://charts.gitlab.io
helm repo update

# Get the runner registration token from GitLab UI:
# Project → Settings → CI/CD → Runners → "Set up a project runner"
REGISTRATION_TOKEN=<paste>

helm upgrade --install gitlab-runner gitlab/gitlab-runner \
  --namespace gitlab-runner --create-namespace \
  --version 0.69.0 \
  --set gitlabUrl=https://gitlab.orbiter \
  --set runnerRegistrationToken="$REGISTRATION_TOKEN" \
  --set rbac.create=true \
  --set runners.privileged=false \
  --set runners.tags=brokerapp,homelab \
  --wait
```

The runner needs `docker:dind` access **only** if you're not using
Kaniko. Our `.gitlab-ci.yml` already uses Kaniko, so leave
`runners.privileged=false`.

## 90.2 Container registry — first push smoke-test

GitLab's container registry is enabled at `gitlab.orbiter:5050`. Verify
from your workstation:

```bash
docker login gitlab.orbiter:5050
# username: your gitlab user
# password: a personal access token with `read_registry write_registry`
```

If login succeeds, you're good.

## 90.3 Configure CI/CD variables

GitLab → Project `wolfgangm81/brokerapp` → **Settings** → **CI/CD** →
**Variables** → **Add variable**.

Use **Protected: ✅**, **Masked: ✅ (for token-like values)**,
**Expand variable reference: ❌**.

| Key                    | Value                                       | How to produce it                     |
| ---------------------- | ------------------------------------------- | ------------------------------------- |
| `KUBE_CONFIG`          | base64-encoded kubeconfig from step 20      | `base64 -w0 < ~/.kube/brokerapp.yaml` |
| `VAULT_ADDR`           | `https://vault.orbiter`                     | constant                              |
| `VAULT_TOKEN`          | token from step 80.6                        | `vault token create ...`              |
| `CI_REGISTRY_USER`     | `gitlab-ci-token`                           | auto (don't set explicitly)           |
| `CI_REGISTRY_PASSWORD` | `$CI_JOB_TOKEN`                             | auto (don't set explicitly)           |
| `CI_REGISTRY_IMAGE`    | `gitlab.orbiter:5050/wolfgangm81/brokerapp` | auto                                  |

> `CI_REGISTRY_*` variables are populated by GitLab automatically when
> you push to a project with the registry enabled. You only need to
> add `KUBE_CONFIG`, `VAULT_ADDR`, `VAULT_TOKEN` manually.

## 90.4 Create the `gitlab-registry` pull secret in the cluster

This lets the cluster pull images from `gitlab.orbiter:5050`:

```bash
# Create a deploy token for the registry:
# GitLab UI → Project → Settings → Repository → Deploy tokens
# Scopes: read_registry
DEPLOY_USER=brokerapp-cluster-puller
DEPLOY_PASS=<token from GitLab UI>

kubectl -n brokerapp create secret docker-registry gitlab-registry \
  --docker-server=gitlab.orbiter:5050 \
  --docker-username="$DEPLOY_USER" \
  --docker-password="$DEPLOY_PASS" \
  --docker-email=devnull@orbiter
```

This is the secret name referenced by every chart's
`imagePullSecrets: [{name: gitlab-registry}]`.

## 90.5 Materialise Vault secrets → k8s Secrets

Each Helm chart references a Secret (`brokerapp-api-secrets`,
`brokerapp-web-secrets`, `brokerapp-worker-secrets`,
`brokerapp-forecast-worker-secrets`, `brokerapp-db-secrets`,
`brokerapp-backup-secrets`). They're created from Vault by the CI
pipeline.

The easiest pattern: a `pre-deploy` job that pulls each Vault path and
runs `kubectl create secret`. Add this to `.gitlab-ci.yml` (or apply
the snippet ad-hoc before the first deploy):

```yaml
pre-deploy:secrets:
  stage: deploy
  image: alpine:3.20
  extends: .only-main
  before_script:
    - apk add --no-cache curl jq bash kubectl
    - mkdir -p ~/.kube && echo "$KUBE_CONFIG" | base64 -d > ~/.kube/config
    - chmod 600 ~/.kube/config
  script:
    - |
      set -euo pipefail
      vault_kv() {
        curl -sf -H "X-Vault-Token: $VAULT_TOKEN" \
          "$VAULT_ADDR/v1/kv/data/brokerapp/$1" | jq -r '.data.data'
      }
      for path in db api web worker forecast backup; do
        json=$(vault_kv "$path")
        # Build --from-literal args dynamically:
        args=$(echo "$json" | jq -r 'to_entries | map("--from-literal="+.key+"="+(.value|tostring)) | join(" ")')
        kubectl -n brokerapp delete secret "brokerapp-${path/worker/worker-}secrets" --ignore-not-found
        kubectl -n brokerapp create secret generic "brokerapp-${path/worker/worker-}secrets" $args
      done
```

> Naming nit: the umbrella's `forecastWorker` alias expects the secret
> `brokerapp-forecast-worker-secrets`. The shell snippet above maps
> `forecast` → `forecast-worker-` accordingly.

For Phase 8 / first deploy, you can also do this **once by hand** from
your workstation while Vault is fresh in your head — copy the same
loop into a local shell.

## 90.6 Push, watch CI

```bash
git push origin claude/stock-forecast-app-kmWQG
# In GitLab UI → CI/CD → Pipelines:
#   lint:* → test:* → build:* (only changed images) → deploy:k8s
```

Expected first-run timings (cold caches):

- `lint:*` ~30 s each
- `test:*` ~60 s each
- `build:api`, `build:migrate`, `build:web` ~3 min each
- `build:worker` ~6 min (TA-Lib compile)
- `build:forecast` ~4 min
- `deploy:k8s` ~3 min

Next: [95-deploy.md](./95-deploy.md).
