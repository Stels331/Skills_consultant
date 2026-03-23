# Sprint 06 Acceptance Bundle

## Scope

- Workspace-scoped runtime context
- Tenant/workspace namespace isolation for retrieval and runtime caches
- Anti-contamination validator with governance logging and extension point
- Workspace-switch UI safeguards
- Isolation regression suite

## Files

- `app/dialogue_api.py`
- `app/validation/dialogue_validator.py`
- `app/validation/workspace_isolation.py`
- `tests/test_sprint_06_isolation.py`

## Acceptance Checklist

- Verify answer payloads are blocked when prompt or entity references leak a foreign workspace.
- Verify session reuse across workspaces raises a protection error.
- Verify runtime resets when switching workspaces and emits a governance event.
- Verify evidence, open questions, and version-state responses stay workspace-scoped.
- Verify UI page explicitly warns that workspace switching discards drafts and resets panels.
- Verify Sprint 4-6 regression remains green.
