# Sprint 08 Codex Summary

- Added decision-domain canonical entities in [app/canonical_db/domain.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/canonical_db/domain.py).
- Added Sprint 8 migration [20260323_0005_decision_domain.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/alembic/versions/20260323_0005_decision_domain.py) with decision tables and `decision_query` support in rebuilt `dialogue_messages` and `question_queue`.
- Added sqlite repositories and services in [decision_domain.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/canonical_db/decision_domain.py):
  - `ProblemFrameBuilder`
  - `DecisionOptionEngine`
  - `DecisionComparisonService`
  - `DecisionContractService`
  - `DecisionReviewService`
- Extended [dialogue_backend.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/canonical_db/dialogue_backend.py) with `decision_query`.
- Added [test_sprint_08_decision_domain.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышение/Skills/FPF-skill_2/electronic_consultant_v3_old/tests/test_sprint_08_decision_domain.py) covering schema, lifecycle, invalidation cascade, partial contract gating, outcome recording and review close.

Implemented Sprint 8 behavior:

- `ProblemFrame` is stored as first-class canonical state.
- `DecisionOption`, `DecisionComparison`, `DecisionDraft`, `DecisionRecord`, `DecisionReview`, `DecisionOutcome` are persisted in canonical DB.
- invalidated frame cascades to stale downstream objects and published `DecisionRecord -> review_required`.
- outcome events update `historical_value_score`, `last_outcome_status`, `last_outcome_at`.
- governance trail records compare/select/reject/review_due/outcome events.
