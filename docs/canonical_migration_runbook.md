# Canonical Migration Runbook

## Bootstrap

1. Set a DSN through `CANONICAL_DB_DSN`, `DATABASE_URL`, or `CANONICAL_DB_DSN_<ENV>`.
2. Run `make db-bootstrap`.
3. Verify the current revision with `make db-current-revision`.

Default local/test bootstrap uses `sqlite:///.codex_data/canonical.db`. Production should point the same env vars to PostgreSQL.

## Upgrade / downgrade workflow

- Upgrade to head: `make db-upgrade`
- Downgrade one revision: `make db-downgrade`
- Re-apply after rollback drill: `make db-upgrade`

The revision files live under [alembic/versions](/Users/stas/Documents/Системное Мышление/Системное мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/alembic/versions).

## Rollback policy

- Schema-only rollback uses `downgrade -1` when the latest revision is reversible.
- Data-affecting incidents roll back application traffic first, then restore the last verified DB backup if downgrade is unsafe.
- Dual-write cutover must stay disabled unless export parity, drift alarms, and restore rehearsal are all green.

## Revision conventions

- Revision ids use `YYYYMMDD_NNNN`.
- One migration file per deployable schema change.
- Risky changes follow `expand -> migrate -> contract`.
