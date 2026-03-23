# Sprint 06 Isolation Test Report

## Commands

```bash
python3 -m py_compile app/dialogue_api.py app/validation/dialogue_validator.py app/validation/workspace_isolation.py tests/test_sprint_06_isolation.py
python3 -m unittest tests.test_sprint_06_isolation
python3 -m unittest tests.test_sprint_04_validation_ui tests.test_sprint_05_model_updates_reentry tests.test_sprint_06_isolation
```

## Result

- `tests.test_sprint_06_isolation`: `8 tests`, `OK`
- Regression `tests.test_sprint_04_validation_ui tests.test_sprint_05_model_updates_reentry tests.test_sprint_06_isolation`: `20 tests`, `OK`
