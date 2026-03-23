# Canonical Schema Notes

## Tenant and naming rules

- Canonical scope is `organization -> workspace -> case-bound entity`.
- Every case-bound table carries both `organization_id` and `workspace_id`.
- Table names are plural snake_case, foreign keys use `<entity>_id`, enum-like fields use constrained text columns.
- Mutable projections live in the base table (`claims`, `artifacts`, `workspaces`); immutable history lives in `*_versions` or append-only ledgers.

## Synchronization with specs 02 / 08 / 09 / 10 / 11

- `dialogue_messages` includes `workspace_version_id` and `question_class` so each answer is attributable to a concrete model version.
- `claims.confidence_score` and `claim_versions.confidence_score` are bounded numeric scores in `0.0 .. 1.0`.
- `workspaces` carries re-entry state (`reentry_status`, `reentry_started_at`) for version-aware dialogue.
- `reentry_jobs` stores dependent projections, affected stages, and stale outputs to keep Sprint 5 re-entry lineage explicit.
- Retrieval/governance indexes are present on `organization_id`, `workspace_id`, `session_id`, `claim_type`, `status`, and `created_at`.

## Data rules

- `workspace_key` and `(workspace_id, version_no)` must be unique.
- `claims` is the latest projection; every write must also append a `claim_versions` row.
- Materialized file exports are derived from canonical DB state only.
- `governance_events` is append-only in normal flows and is used for dual-write drift alarms.
- New migrations must remain reversible or document why rollback must be handled through restore-from-backup rather than downgrade.
