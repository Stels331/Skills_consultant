# Acceptance Bundle: SPRINT_08_DECISION_DOMAIN

## Sprint State

```json

{
  "current_sprint": "SPRINT_08_DECISION_DOMAIN",
  "status": "awaiting_acceptance",
  "attempt": 1,
  "last_commit": "14261efcc215a858e648b3fda9c64c239ce217db",
  "codex_summary_path": "reports/tests/sprint_08_decision_domain_codex_summary_attempt_1.md",
  "test_report_path": "reports/tests/sprint_08_decision_domain_test_report_attempt_1.md",
  "acceptance_notes_path": null
}

```

## Acceptance Prompt

# Manual Acceptance Prompt

Ты выполняешь ручную приемку текущего спринта.

Проверь только текущий спринт:

- `Current sprint`: `SPRINT_08_DECISION_DOMAIN`
- `Sprint spec`: `TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_08_DECISION_DOMAIN.md`
- `Current status`: `awaiting_acceptance`
- `Attempt`: `1`
- `Codex summary`: `reports/tests/sprint_08_decision_domain_codex_summary_attempt_1.md`
- `Test report`: `reports/tests/sprint_08_decision_domain_test_report_attempt_1.md`

## Что проверить

- Все обязательные задачи спринта действительно выполнены.
- Критерии приемки закрыты без очевидных пробелов.
- Релевантные тесты запущены и отражены в test report.
- Нет явного выхода за scope спринта.
- Все ограничения, blocker'ы и допущения зафиксированы явно.

## Формат результата

Сохрани результат ручной проверки в markdown-файл в `reports/reviews/`.

Структура результата:

```md
# Acceptance Result: SPRINT_08_DECISION_DOMAIN

Decision: accept
```

или

```md
# Acceptance Result: SPRINT_08_DECISION_DOMAIN

Decision: changes requested

Findings:
- ...
- ...
```

После этого зафиксируй решение через `accept-sprint` или `request-changes`.

## Sprint Spec Path

TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_08_DECISION_DOMAIN.md

## Sprint Spec

# Sprint 8. Decision Domain Model And Contracts

## Цель

Сделать решение first-class частью canonical model: проблема, варианты, сравнение и выбранный вариант должны жить в системе как явные сущности, а не только как prose-ответы.

## Ожидаемый результат спринта

- в canonical model появляются `ProblemFrame`, `DecisionOption`, `DecisionComparison`, `DecisionDraft`, `DecisionRecord`, `DecisionEvidenceLink`, `DecisionReview`, `DecisionOutcome`;
- `ProblemFrame` и `DecisionOption` имеют явный lifecycle/invalidation policy;
- рекомендации можно сохранить, перечитать и сравнить как structured decision contracts;
- каждый decision contract связан с claims, artifacts, projections и governance trail;
- prose recommendation без decision contract переводится в `degrade` или `block`.

## Зависимости и техдолг из Sprint 1-5

- decision tables должны продолжить schema conventions, уже закрепленные в Sprint 1;
- `QuestionRouter` из Sprint 3 должен получить расширение для `decision_query` без переписывания существующих query classes;
- candidate pool, comparison и final selection должны использовать уже существующий dialogue/governance correlation chain, а не отдельный parallel flow.

## Задачи

### S8-T1. Расширить canonical schema decision-сущностями

Описание:
- добавить таблицы и доменные модели для `problem_frames`, `decision_options`, `decision_comparisons`, `decision_drafts`, `decision_records`, `decision_evidence_links`, `decision_reviews`, `decision_outcomes`;
- зафиксировать version-aware и tenant-aware связи на `organization_id`, `workspace_id`, `workspace_version_id`;
- предусмотреть поля для rationale, rejected alternatives, review_due и status;
- предусмотреть outcome-facing поля: `historical_value_score`, `last_outcome_status`, `last_outcome_at`;
- зафиксировать структуру `DecisionEvidenceLink`: `link_type`, `link_strength`, `link_direction`, `source_ref`, `criticality`;
- перед стартом реализации пройти pre-S8 schema checklist: naming conventions, nullable rules, index patterns и tenant/version fields должны совпадать с established conventions Sprint 1.

Критерии приемки:
- decision-сущности хранятся в canonical DB и изолированы по tenant/workspace;
- schema позволяет связать decision contract с конкретной published/pending version;
- schema позволяет связать `DecisionOutcome` с конкретным `DecisionRecord` и workspace version;
- migration не ломает уже существующие dialogue/reentry таблицы;
- intermediate draft state поддержан без premature creation of final `DecisionRecord`;
- decision tables соответствуют established S1 Alembic/schema conventions.

### S8-T2. Реализовать `ProblemFrameBuilder`

Описание:
- собирать `ProblemFrame` из selected problem, supporting claims, unresolved unknowns и active constraints;
- отделять root problem, scope boundary и success criteria;
- фиксировать problem frame как отдельный артефакт, а не как поле в ответе;
- ввести immutable/versioned semantics или `frame_invalidation_trigger`, чтобы новый critical claim не оставлял frame silently valid.

Критерии приемки:
- по кейсу можно построить один актуальный `ProblemFrame`;
- root problem и symptoms не смешиваются;
- `ProblemFrame` пригоден как вход для option generation и retrieval;
- появление нового critical support или contradiction переводит frame в invalidated/rebuild-required state;
- invalidated frame каскадно помечает связанные `DecisionOption`, `DecisionComparison`, `DecisionDraft` как stale/rebuild-required, а не оставляет их silently active;
- опубликованный `DecisionRecord`, зависящий от invalidated frame, переводится минимум в `review_required`.

### S8-T3. Реализовать `DecisionOptionEngine`

Описание:
- формировать canonical `DecisionOption` из solution portfolio и candidate interventions;
- хранить assumptions, `confidence_in_assumptions`, benefits, costs, risks и prerequisites;
- не давать UI/LLM “выбирать вариант”, который не существует как option entity;
- ввести lifecycle policy для option: `draft -> candidate -> active -> stale -> retired`.

Критерии приемки:
- каждая рекомендуемая альтернатива имеет `DecisionOption`;
- option хранит machine-readable assumptions и risk markers;
- один и тот же option можно использовать в сравнении и review lifecycle;
- если underlying evidence materially changed, option получает stale/rebuild-required marker.

### S8-T4. Реализовать `DecisionComparisonService`

Описание:
- собирать `DecisionComparison` по базовым dimensions: feasibility, cost, risk, reversibility, strategic fit, operational load;
- поддержать `domain-specific dimension injection` поверх базового набора dimensions;
- сохранять trade-offs, blockers и rationale notes;
- обеспечивать связь с existing comparison artifacts и governance records.

Критерии приемки:
- decision comparison строится по фиксированному базовому набору dimensions;
- domain-specific dimensions можно добавлять policy-driven способом без переписывания core service;
- rejected alternatives фиксируются явно, а не исчезают из истории;
- comparison пригоден для audit и повторной проверки.

### S8-T5. Реализовать `DecisionContractService`

Описание:
- на основе `ProblemFrame`, `DecisionOption` и `DecisionComparison` формировать `DecisionRecord`;
- сохранять selected option, rejected alternatives, decision basis, linked evidence, review_due и limitations;
- если контракт неполон, возвращать `degrade`/`block` вместо “полезного” prose-only ответа;
- зафиксировать `degraded partial recommendation`: user получает structured partial answer с explicit uncertainty markers, missing basis и reason codes.
- явно зафиксировать transition `DecisionDraft -> DecisionRecord`: promotion происходит только после complete comparison state и explicit selection trigger от orchestration/user action, а не silently после любого rebuild.
- auto-promotion path допустим только как orchestrated system action с явными safeguards и governance event, а не как implicit side effect rebuild-а.

Критерии приемки:
- любая рекомендация из dialogue layer может быть представлена как `DecisionRecord`;
- prose recommendation без supporting contract не считается accepted outcome;
- `DecisionRecord` объясняет не только что выбрано, но и почему;
- degraded recommendation не маскируется под final decision и явно показывает, чего не хватает;
- draft state не auto-promote-ится без явного promotion trigger.

### S8-T5.1. Реализовать базовую outcome-модель для решений

Описание:
- ввести `DecisionOutcome` как first-class canonical entity;
- outcome должен хранить `decision_id`, `outcome_type`, `outcome_score`, `source`, `evidence`, `recorded_at`;
- outcome не вычисляется из prose summary, а записывается из явных lifecycle/governance/review signals;
- подготовить `historical_value_score` как агрегируемый derived field для будущего Sprint 9-10.

Критерии приемки:
- решение может иметь `0..N` outcome records;
- positive/negative outcome history сериализуется machine-readable;
- `historical_value_score` существует как canonical field, даже если полная policy его обновления реализуется позже.

### S8-T6. Добавить governance events для decision lifecycle

Описание:
- ввести события `decision_option_created`, `decision_compared`, `decision_selected`, `decision_rejected`, `decision_review_due`, `decision_retired`, `decision_outcome_recorded`;
- связать их с actor, workspace version и correlation id запроса;
- сделать decision lifecycle видимым в ledger и diff/history panels;
- явно зафиксировать семантику:
  - `decision_option_created` нужен для lifecycle option до selection;
  - `decision_rejected` нужен, если option отвергнут явно, а не только выводится из comparison.
  - candidate pool логируется через `decision_option_created`, даже если option не дошел до final comparison;
  - при большом candidate pool допустим агрегирующий `candidate_pool_snapshot`, но с traceable ссылками на individual option ids.

Критерии приемки:
- decision lifecycle воспроизводим по governance trail;
- selected/rejected alternatives различимы на уровне событий;
- один correlation id связывает dialogue request, comparison и decision selection.
- outcome events различимы отдельно от review/selection events.

### S8-T7. Реализовать минимальный lifecycle для `DecisionReview`

Описание:
- уже в этом спринте поддержать `create -> close` для review records;
- не откладывать базовую review сущность до operator UX спринта;
- дать `DecisionRecord` machine-readable state: `draft`, `selected`, `review_required`, `closed`, `retired`;
- зафиксировать связь state machine:
  - `review_required` на `DecisionRecord` автоматически создает open `DecisionReview`;
  - `close` review синхронно обновляет record state.

Критерии приемки:
- `DecisionReview` можно создать и закрыть без UI-heavy workflow;
- review entity не является “пустой заглушкой” до Sprint 10;
- lifecycle decisions читается из canonical state и governance trail.

## Тесты спринта

### Unit tests

- Schema migration test: новые decision tables создаются и корректно связываются с workspace/version entities.
- Problem frame build test: selected problem, constraints и unknowns собираются в один `ProblemFrame`.
- Root-vs-symptom test: symptom markers не попадают в root problem field silently.
- Frame invalidation test: новый critical claim или contradiction переводит frame в invalidated/rebuild-required state.
- Version-binding test: `ProblemFrame` привязан к активной версии workspace.
- Option materialization test: каждая candidate recommendation становится `DecisionOption`.
- Assumption confidence test: option хранит `confidence_in_assumptions` отдельно от general confidence.
- Assumption/risk serialization test: assumptions и risks хранятся machine-readable.
- Duplicate option test: повторный rebuild не создает дубли без явного version change.
- Comparison dimensions test: service возвращает expected dimensions с per-option judgments.
- Domain dimension injection test: дополнительный domain-specific dimension подключается policy-driven способом.
- Rejected alternatives test: comparison сохраняет rejected options, а не только winner.
- Decision contract integration test: из problem frame + comparison строится `DecisionRecord`.
- Missing contract gate test: рекомендация без selected option/evidence links получает `degrade` или `block`.
- Partial recommendation contract test: degraded recommendation сохраняет explicit uncertainty markers и missing basis fields.
- Linked evidence test: `DecisionRecord` содержит refs на claims, artifacts и projections.
- Decision outcome creation test: `DecisionOutcome` сохраняется как отдельная сущность, а не как prose note.
- Historical value field test: `DecisionRecord` хранит `historical_value_score` и last outcome metadata.

### Integration tests

- Tenant isolation test: decision-сущности не читаются без `organization_id` и `workspace_id`.
- Repository contract test: create/read/update review status работает без потери linked evidence refs.
- Trade-off audit test: governance trail содержит evidence of comparison execution.
- Governance event completeness test: create/compare/select/reject пишут все обязательные события.
- Outcome governance test: `decision_outcome_recorded` попадает в ledger c `decision_id` и normalized score.
- Correlation id trace test: decision events связаны с исходным dialogue request.
- Review lifecycle integration test: `DecisionReview` проходит минимум `create -> close` без UI workflow.
- Invalidation propagation test: invalidated `ProblemFrame` помечает downstream options/comparisons/drafts как stale.
- Rejected-option semantics test: governance trail различает explicit rejection и option-never-considered state.
- Decision-record invalidation test: published `DecisionRecord` переходит в `review_required` при invalidated upstream frame.

### Contract tests

- DecisionEvidenceLink contract test: `link_type`, `link_strength`, `link_direction` и `source_ref` обязательны и сериализуются стабильно.
- Decision state contract test: `DecisionDraft` и final `DecisionRecord` не смешиваются на уровне API/repository contract.
- DecisionOutcome contract test: `outcome_type`, `outcome_score`, `source` и `recorded_at` обязательны и стабильно сериализуются.

### API/UI tests

- Decision history API test: UI/API может прочитать chronological decision lifecycle для workspace.
- Router extension test: `QuestionRouter` маршрутизирует decision-oriented intent в `decision_query` без регрессии существующих classes.

## Codex Summary Path

reports/tests/sprint_08_decision_domain_codex_summary_attempt_1.md

## Codex Summary

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

## Test Report Path

reports/tests/sprint_08_decision_domain_test_report_attempt_1.md

## Test Report

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

## Commit / Diff Context

14261efcc215a858e648b3fda9c64c239ce217db

## Diff Hint

git diff 528147c4a3f1e827e824a2aeedb66cffbc48dc6f..14261efcc215a858e648b3fda9c64c239ce217db

## Acceptance Checklist

- Все обязательные задачи спринта закрыты.

- Критерии приемки спринта выполнены.

- Релевантные тесты запущены и результаты зафиксированы.

- Нет очевидного scope creep вне спринта.

- Оставшиеся ограничения и blockers описаны явно.
