# Codex Bundle: SPRINT_08_DECISION_DOMAIN

## Sprint State

```json

{
  "current_sprint": "SPRINT_08_DECISION_DOMAIN",
  "status": "ready",
  "attempt": 1,
  "last_commit": null,
  "codex_summary_path": null,
  "test_report_path": null,
  "acceptance_notes_path": null
}

```

## Executor Prompt

# Codex Sprint Prompt Template

Ты `Codex`, исполнитель спринта.

Работай только в рамках текущего спринта:

- не переходи к следующему спринту;
- не закрывай задачи, которых нет в sprint file;
- сначала опирайся на sprint file, затем на linked specs;
- если ручная приемка предыдущей итерации вернула замечания, исправляй только их и связанные дефекты.

## Входные данные

- `Current sprint`: `SPRINT_08_DECISION_DOMAIN`
- `Sprint spec`: `TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_08_DECISION_DOMAIN.md`
- `Sprint status`: `ready`
- `Attempt`: `1`
- `Previous acceptance notes`: `none`

## Цель

Нужно полностью реализовать текущий спринт по его задачам, критериям приемки и тестам.

## Обязательные правила

- не начинай следующий спринт;
- не меняй scope спринта без явного замечания в acceptance notes;
- все изменения должны быть трассируемы к задачам спринта;
- после завершения:
  - прогоняй релевантные тесты;
  - сохрани test report;
  - создай commit;
  - сохрани короткий implementation summary.

## Ожидаемый результат

Верни только JSON-объект, без markdown-обертки и без пояснений вне JSON.

Допустимый формат:

```json
{
  "commit": "abc123",
  "blocker": null,
  "summary": "Краткий summary изменений",
  "test_report": "Какие тесты были запущены и каков результат"
}
```

Если вместо inline текста сохраняешь файлы, верни:

```json
{
  "commit": "abc123",
  "blocker": null,
  "summary": "Краткий summary изменений",
  "test_report": "Какие тесты были запущены и каков результат"
}
```

Если работа выполнена, но commit нельзя создать из-за ограничений окружения, верни:

```json
{
  "commit": null,
  "blocker": "Почему commit не был создан",
  "summary": "Краткий summary изменений",
  "test_report": "Какие тесты были запущены и каков результат"
}
```

## Sprint Spec Path

TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_08_DECISION_DOMAIN.md

## Sprint Spec

# Sprint 8. Decision Domain Model And Contracts

## Цель

Сделать решение first-class частью canonical model: проблема, варианты, сравнение и выбранный вариант должны жить в системе как явные сущности, а не только как prose-ответы.

## Ожидаемый результат спринта

- в canonical model появляются `ProblemFrame`, `DecisionOption`, `DecisionComparison`, `DecisionDraft`, `DecisionRecord`, `DecisionEvidenceLink`, `DecisionReview`;
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
- добавить таблицы и доменные модели для `problem_frames`, `decision_options`, `decision_comparisons`, `decision_drafts`, `decision_records`, `decision_evidence_links`, `decision_reviews`;
- зафиксировать version-aware и tenant-aware связи на `organization_id`, `workspace_id`, `workspace_version_id`;
- предусмотреть поля для rationale, rejected alternatives, review_due и status;
- зафиксировать структуру `DecisionEvidenceLink`: `link_type`, `link_strength`, `link_direction`, `source_ref`, `criticality`;
- перед стартом реализации пройти pre-S8 schema checklist: naming conventions, nullable rules, index patterns и tenant/version fields должны совпадать с established conventions Sprint 1.

Критерии приемки:
- decision-сущности хранятся в canonical DB и изолированы по tenant/workspace;
- schema позволяет связать decision contract с конкретной published/pending version;
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

### S8-T6. Добавить governance events для decision lifecycle

Описание:
- ввести события `decision_option_created`, `decision_compared`, `decision_selected`, `decision_rejected`, `decision_review_due`, `decision_retired`;
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

### Integration tests

- Tenant isolation test: decision-сущности не читаются без `organization_id` и `workspace_id`.
- Repository contract test: create/read/update review status работает без потери linked evidence refs.
- Trade-off audit test: governance trail содержит evidence of comparison execution.
- Governance event completeness test: create/compare/select/reject пишут все обязательные события.
- Correlation id trace test: decision events связаны с исходным dialogue request.
- Review lifecycle integration test: `DecisionReview` проходит минимум `create -> close` без UI workflow.
- Invalidation propagation test: invalidated `ProblemFrame` помечает downstream options/comparisons/drafts как stale.
- Rejected-option semantics test: governance trail различает explicit rejection и option-never-considered state.
- Decision-record invalidation test: published `DecisionRecord` переходит в `review_required` при invalidated upstream frame.

### Contract tests

- DecisionEvidenceLink contract test: `link_type`, `link_strength`, `link_direction` и `source_ref` обязательны и сериализуются стабильно.
- Decision state contract test: `DecisionDraft` и final `DecisionRecord` не смешиваются на уровне API/repository contract.

### API/UI tests

- Decision history API test: UI/API может прочитать chronological decision lifecycle для workspace.
- Router extension test: `QuestionRouter` маршрутизирует decision-oriented intent в `decision_query` без регрессии существующих classes.

## Previous Acceptance Notes Path

none

## Previous Acceptance Notes

Not provided
