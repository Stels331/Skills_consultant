# Sprint 08 Test Report

## Commands

```bash
python3 -m py_compile app/canonical_db/domain.py app/canonical_db/decision_domain.py app/canonical_db/dialogue_backend.py alembic/versions/20260323_0005_decision_domain.py tests/test_sprint_08_decision_domain.py
python3 -m unittest tests.test_sprint_08_decision_domain
python3 -m unittest tests.test_sprint_07_hardening_release tests.test_sprint_08_decision_domain
python3 -m unittest tests.test_sprint_05_model_updates_reentry tests.test_sprint_06_isolation tests.test_sprint_07_hardening_release tests.test_sprint_08_decision_domain
```

## Result

- `py_compile`: passed
- `tests.test_sprint_08_decision_domain`: passed, 7 tests
- `tests.test_sprint_07_hardening_release + tests.test_sprint_08_decision_domain`: passed, 12 tests
- `tests.test_sprint_05_model_updates_reentry + tests.test_sprint_06_isolation + tests.test_sprint_07_hardening_release + tests.test_sprint_08_decision_domain`: passed, 28 tests

## Notes

- Sprint 8 migration initially failed because SQLite kept old index names during table rebuild for `dialogue_messages` and `question_queue`.
- Migration `20260323_0005_decision_domain.py` was corrected to drop legacy indexes before recreating the tables.
- No regression was detected in Sprint 5-7 suites after the fix.
