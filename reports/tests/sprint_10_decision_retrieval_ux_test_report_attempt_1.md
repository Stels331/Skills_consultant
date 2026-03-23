# Sprint 10 Test Report

## Commands

```bash
python3 -m py_compile app/canonical_db/decision_retrieval.py app/dialogue_api.py tests/test_sprint_10_decision_retrieval_ux.py
python3 -m unittest tests.test_sprint_10_decision_retrieval_ux
python3 -m unittest tests.test_sprint_08_decision_domain tests.test_sprint_09_decision_assurance tests.test_sprint_10_decision_retrieval_ux
python3 -m unittest tests.test_sprint_07_hardening_release tests.test_sprint_08_decision_domain tests.test_sprint_09_decision_assurance tests.test_sprint_10_decision_retrieval_ux
python3 -m unittest tests.test_sprint_05_model_updates_reentry tests.test_sprint_06_isolation tests.test_sprint_07_hardening_release tests.test_sprint_08_decision_domain tests.test_sprint_09_decision_assurance tests.test_sprint_10_decision_retrieval_ux
```

## Result

- `py_compile`: passed
- `tests.test_sprint_10_decision_retrieval_ux`: passed, 4 tests
- `tests.test_sprint_08_decision_domain + tests.test_sprint_09_decision_assurance + tests.test_sprint_10_decision_retrieval_ux`: passed, 16 tests
- `tests.test_sprint_07_hardening_release + tests.test_sprint_08_decision_domain + tests.test_sprint_09_decision_assurance + tests.test_sprint_10_decision_retrieval_ux`: passed, 21 tests
- `tests.test_sprint_05_model_updates_reentry + tests.test_sprint_06_isolation + tests.test_sprint_07_hardening_release + tests.test_sprint_08_decision_domain + tests.test_sprint_09_decision_assurance + tests.test_sprint_10_decision_retrieval_ux`: passed, 37 tests

## Notes

- Sprint 10 was implemented without advancing sprint-loop state because `SPRINT_08_DECISION_DOMAIN` remains pending manual acceptance in the loop.
- `decision_query` tests use a grounded phrase with `budget limit`, because the existing graph-first retrieval contract still requires token overlap with modeled claims before the Sprint 10 decision payload is composed.
