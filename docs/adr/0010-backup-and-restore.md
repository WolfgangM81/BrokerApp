# ADR-0010: Backup and restore strategy

- **Status:** Accepted
- **Date:** 2026-05-10

## Context

We need a backup strategy that is:

- Realistic for a homelab cluster (no cloud blob storage, no 24/7 ops).
- Survives a node failure, a Longhorn disaster, an accidental DROP TABLE,
  and a complete cluster rebuild.
- Verifiable — an untested backup is not a backup.

## Decision

### What is backed up

| What | How | Where |
|------|-----|-------|
| Postgres / TimescaleDB | nightly `pg_dump --format=custom` per database | MinIO bucket `backups/postgres/` (in-cluster) |
| MinIO data (MLflow artifacts, …) | nightly `mc mirror` between MinIO buckets | MinIO bucket `backups/minio-snapshots/` |
| Both above, off-site | nightly `rsync --archive` over ZeroTier | external NAS / second homelab node |

### Encryption and rotation

- Each nightly artifact is **age-encrypted** with a public key whose
  private key lives in Vault. The Postgres dump format is custom (already
  compressed), so the encryption is the only post-processing.
- **Retention:** 30 days in MinIO, 90 days off-site, monthly snapshot
  retained for 12 months.

### Restore testing

- A **weekly CronJob** in the cluster restores the latest dump into a
  throwaway `brokerapp-restore-test` namespace and runs `SELECT
  count(*) FROM …` smoke queries against each main table. Failure pages
  ntfy.sh and writes a Prometheus metric `brokerapp_restore_test_success`.
- A **runbook** in `docs/runbooks/restore.md` documents the full manual
  restore procedure (cluster-rebuild scenario).

### Phasing

- The Helm-charts and CronJobs for this land in **Phase 4 (Operations)**.
- Phase 1 only declares the schema in `services/db/` so that
  `pg_dump`-based backups will Just Work once we ship.

## Consequences

**+** Tested, encrypted, redundant. Survives realistic failure scenarios.
**+** No cloud cost; uses existing homelab resources.
**−** Restore time is bounded by the size of the dump — minutes for now,
       potentially hours when we hit years of intraday bars. Add WAL-G
       continuous archiving in Phase 5 if we cross that threshold.
**−** Vault outage at restore time means we can't decrypt. Mitigation: a
       sealed "break-glass" copy of the age private key kept off-cluster.
