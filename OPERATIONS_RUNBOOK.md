# OPERATIONS RUNBOOK

## Daily Operations
1. Run integration suite: `python3 scripts/run_integration_suite.py`.
2. Check pilot gaps: `governance/pilot_gap_register.md`.
3. Check risk register: `governance/risk_register.md`.
4. Verify latest workspaces via `scripts/build_audit_trail.py <workspace_id>`.

## Incident Response
1. Diagnose failed stage: `python3 scripts/diagnose_stage.py <workspace_id> <stage>`.
2. If expired/recheck, trigger incremental loop: `python3 scripts/run_incremental.py <workspace_id> <stage>`.
3. Re-run reporting and validate workspace contracts.
