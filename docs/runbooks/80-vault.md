# Step 80 — Vault: secret layout + populate

Every secret BrokerApp needs lives under `kv/brokerapp/...`. GitLab CI
reads from there and materialises k8s `Secret` resources at deploy
time (`deploy:k8s` job).

## 80.1 Enable the KV-v2 mount (skip if it already exists)

```bash
export VAULT_ADDR=https://vault.orbiter
vault login -method=oidc           # or whatever method your homelab uses
vault secrets enable -path=kv -version=2 kv 2>/dev/null || true
```

## 80.2 KV layout

```text
kv/brokerapp/
├── db                          # postgres credentials
├── api                         # API secrets (Authentik, internal token, ...)
├── web                         # NextAuth client secret + AUTH_SECRET
├── worker                      # Celery broker DSN + internal token
├── forecast                    # forecast worker (same shape as worker)
├── minio                       # service-user access keys
├── backup                      # age public key + private key
└── authentik                   # OIDC client secret (web) + IDs
```

## 80.3 Generate the secrets

```bash
# 1) Postgres
DB_PASS=$(openssl rand -hex 24)

# 2) Internal worker → API shared token (≥32 chars)
INTERNAL_TOKEN=$(openssl rand -hex 32)

# 3) NextAuth AUTH_SECRET (32+ bytes, base64)
AUTH_SECRET=$(openssl rand -base64 32)

# 4) age keypair for backup encryption
age-keygen -o /tmp/age.key
AGE_PRIV=$(cat /tmp/age.key)
AGE_PUB=$(grep -oE 'age1[a-z0-9]+' /tmp/age.key | head -1)
shred -u /tmp/age.key
```

Keep `INTERNAL_TOKEN`, `AUTH_SECRET`, `AGE_PRIV` for the next step
(don't print them to logs in a real shell).

## 80.4 Write the secrets

```bash
# --- DB ---
vault kv put kv/brokerapp/db \
  POSTGRES_USER=brokerapp \
  POSTGRES_PASSWORD="$DB_PASS" \
  POSTGRES_DB=brokerapp \
  POSTGRES_HOST=brokerapp-db \
  POSTGRES_PORT=5432

# --- API ---
vault kv put kv/brokerapp/api \
  ENVIRONMENT=production \
  API_CORS_ORIGINS=https://brokerapp.orbiter \
  AUTHENTIK_ISSUER=https://auth.orbiter/application/o/brokerapp/ \
  AUTHENTIK_AUDIENCE=brokerapp \
  AUTHENTIK_JWKS_URL=https://auth.orbiter/application/o/brokerapp/jwks/ \
  AUTHENTIK_ADMIN_GROUP=brokerapp-admins \
  INTERNAL_TOKEN="$INTERNAL_TOKEN" \
  REDIS_URL="redis://brokerapp-redis-master.brokerapp.svc.cluster.local:6379/0"

# --- Web (Auth.js) ---
vault kv put kv/brokerapp/web \
  NODE_ENV=production \
  NEXT_PUBLIC_API_URL=https://api.brokerapp.orbiter \
  AUTH_SECRET="$AUTH_SECRET" \
  AUTH_AUTHENTIK_ID=brokerapp \
  AUTH_AUTHENTIK_SECRET="<paste-the-client-secret-from-Authentik>" \
  AUTH_AUTHENTIK_ISSUER=https://auth.orbiter/application/o/brokerapp/

# --- Ingest worker ---
vault kv put kv/brokerapp/worker \
  POSTGRES_USER=brokerapp \
  POSTGRES_PASSWORD="$DB_PASS" \
  POSTGRES_DB=brokerapp \
  POSTGRES_HOST=brokerapp-db \
  POSTGRES_PORT=5432 \
  REDIS_URL="redis://brokerapp-redis-master.brokerapp.svc.cluster.local:6379/0" \
  INTERNAL_TOKEN="$INTERNAL_TOKEN" \
  API_BASE_URL=https://api.brokerapp.orbiter

# --- Forecast worker ---
vault kv put kv/brokerapp/forecast \
  POSTGRES_USER=brokerapp \
  POSTGRES_PASSWORD="$DB_PASS" \
  POSTGRES_DB=brokerapp \
  POSTGRES_HOST=brokerapp-db \
  POSTGRES_PORT=5432 \
  REDIS_URL="redis://brokerapp-redis-master.brokerapp.svc.cluster.local:6379/0" \
  MLFLOW_TRACKING_URI=http://mlflow.brokerapp.svc.cluster.local:5000

# --- MinIO access for the in-cluster pieces ---
vault kv put kv/brokerapp/minio \
  mlflow-access-key=mlflow \
  mlflow-secret-key=<paste from step 60> \
  backup-access-key=backup \
  backup-secret-key=<paste from step 60> \
  longhorn-access-key=longhorn \
  longhorn-secret-key=<paste from step 60>

# --- Backup (used by the backup CronJob) ---
vault kv put kv/brokerapp/backup \
  age.pub="$AGE_PUB" \
  age.key="$AGE_PRIV" \
  minio-access-key=backup \
  minio-secret-key=<paste from step 60>

# --- Authentik (for the CI to know what the client ID/secret are) ---
vault kv put kv/brokerapp/authentik \
  client_id=brokerapp \
  client_secret=<paste-web-client-secret> \
  mobile_client_id=brokerapp-mobile
```

## 80.5 Verify

```bash
for p in db api web worker forecast minio backup authentik; do
  echo "=== kv/brokerapp/$p ==="
  vault kv list kv/brokerapp || true
  vault kv get -format=json "kv/brokerapp/$p" | jq '.data.data | keys'
done
```

You should see the expected keys in each path.

## 80.6 (Optional) Lock down with policies

If you don't already have one, create a Vault policy that only lets
the GitLab CI service account read `kv/brokerapp/*`:

```bash
cat <<'HCL' | vault policy write brokerapp-ci -
path "kv/data/brokerapp/*"      { capabilities = ["read"] }
path "kv/metadata/brokerapp/*"  { capabilities = ["list"] }
HCL

# Create the token GitLab uses (see step 90):
vault token create -policy=brokerapp-ci -ttl=8760h -display-name="gitlab-brokerapp"
```

Save the token output as `VAULT_TOKEN` for step 90.

## 80.7 Off-cluster break-glass for `age.key`

The age private key is what the restore-test CronJob (ADR-0010) and a
human operator both need to decrypt backups. If Vault is unreachable
during a disaster, you can't restore.

Print it to a USB token (or your password manager) **now**:

```bash
vault kv get -field=age.key kv/brokerapp/backup
```

Store the output in a sealed envelope / a YubiKey-protected vault entry
/ a piece of paper in your safe — whichever your homelab risk tolerance
prefers. The point is: it lives somewhere that does _not_ depend on
the cluster.

Next: [90-gitlab-ci.md](./90-gitlab-ci.md).
