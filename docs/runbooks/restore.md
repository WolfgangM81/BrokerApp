# Runbook — Restore from backup

ADR-0010 records the strategy. This runbook is the manual procedure when
the weekly automated restore-test isn't enough — a real disaster.

## Pre-flight

- Identify the failure mode:
  - Single accidentally-dropped table → point-in-time partial restore.
  - DB corruption / Longhorn loss → full DB restore from latest dump.
  - Cluster lost → see "Cluster rebuild" below.
- Decide which dump to restore. List candidates:
  ```bash
  mc ls minio/backups/postgres/ | sort | tail -n 20
  ```

## Decrypt + restore (full)

1. Pull the encrypted dump:
   ```bash
   mc cp minio/backups/postgres/brokerapp-YYYYMMDDTHHMMSSZ.dump.age /tmp/dump.age
   ```
2. Decrypt using the age private key from Vault (`brokerapp/backup/age.key`):
   ```bash
   age -d -i ~/secrets/age.key -o /tmp/dump /tmp/dump.age
   ```
3. Restore into a fresh database:
   ```bash
   PGPASSWORD=… psql -h $DB_HOST -U $DB_USER -d postgres \
     -c "DROP DATABASE IF EXISTS brokerapp_new; CREATE DATABASE brokerapp_new;"
   PGPASSWORD=… pg_restore -h $DB_HOST -U $DB_USER -d brokerapp_new \
     --no-owner --no-privileges /tmp/dump
   ```
4. Smoke queries (same as the weekly restore-test):
   ```sql
   SELECT count(*) FROM app.assets;
   SELECT count(*) FROM market.bars;
   ```
5. Cut over: `ALTER DATABASE brokerapp RENAME TO brokerapp_old;`
   then `ALTER DATABASE brokerapp_new RENAME TO brokerapp;`
6. Restart pods that hold open connections (api + worker).

## Cluster rebuild

1. Reinstall k8s nodes / Longhorn.
2. Restore Vault from its own backup (out of scope here).
3. Recreate `brokerapp` namespace + Vault-sourced secrets.
4. `helm upgrade --install brokerapp infra/helm/umbrella …`
5. Run the full restore above against the new DB.

## Verifying the restore-test CronJob

```bash
kubectl -n brokerapp get cronjob brokerapp-restore-test
kubectl -n brokerapp logs -l app.kubernetes.io/name=brokerapp-restore-test --tail=200
```

If it has been red for > 2 weekly runs, treat it as an outage of the
backup story itself.
