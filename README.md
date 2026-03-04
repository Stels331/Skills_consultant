# New Project (Electronic Consultant v1)

Current implementation status:
- Sprint 01 / Task S1-T1: workspace manager (filesystem-only, no DB) completed.
- Sprint 01 / Task S1-T2: schema-based artifact validation (local, no external services) completed.
- Sprint 01 / Task S1-T3: deterministic router + transition guards + context budget enforcer completed.
- Sprint 02 / Task S2-T2 (partial): typization stage + dynamic type registry files completed.

## Quick start

Create a workspace:

```bash
python3 scripts/workspace_cli.py --project-root . create
```

Set workspace state:

```bash
python3 scripts/workspace_cli.py --project-root . set-state case_YYYYMMDD_NNN ACTIVE --reason "start"
```

Create checkpoint:

```bash
python3 scripts/workspace_cli.py --project-root . checkpoint case_YYYYMMDD_NNN --reason "before structural update" --structural
```

Run tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Validate workspace artifacts:

```bash
python3 scripts/validate_workspace.py case_YYYYMMDD_NNN
```

Run typization stage:

```bash
python3 scripts/run_typization.py case_YYYYMMDD_NNN
```

One-command smoke run:

```bash
make run-smoke WORKSPACE_ID=case_YYYYMMDD_NNN
```
