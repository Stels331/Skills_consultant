# Dual-Write Policy

- Canonical write order is `DB transaction -> governance event -> file materialization`.
- File exports are compatibility/debug artifacts only and must be regenerated from DB state, never mutated as primary state.
- Materializer writes deterministic JSON with sorted keys and stable file ordering.
- If an exported file already exists with drift from canonical content, the materializer records a `sync_error` governance event.

## Exit Criteria

- Drift rate: `0` unresolved `sync_error` events across the last 100 workspace materializations.
- Export completeness: `100%` of canonical artifacts for the workspace are represented in the materialized tree.
- Determinism: two consecutive materializations without DB changes produce identical content hashes.
- Rollback readiness: latest reversible migration drill `upgrade -> downgrade -1 -> upgrade` passes in CI and backup restore note is current.
