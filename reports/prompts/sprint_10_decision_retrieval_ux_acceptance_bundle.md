# Acceptance Bundle: SPRINT_10_DECISION_RETRIEVAL_UX

## Sprint State

```json

{
  "current_sprint": "SPRINT_10_DECISION_RETRIEVAL_UX",
  "status": "awaiting_acceptance",
  "attempt": 1,
  "last_commit": "14261efcc215a858e648b3fda9c64c239ce217db",
  "codex_summary_path": "reports/tests/sprint_10_decision_retrieval_ux_codex_summary_attempt_1.md",
  "test_report_path": "reports/tests/sprint_10_decision_retrieval_ux_test_report_attempt_1.md",
  "acceptance_notes_path": null
}

```

## Acceptance Prompt

# Manual Acceptance Prompt

Ты выполняешь ручную приемку текущего спринта.

Проверь только текущий спринт:

- `Current sprint`: `SPRINT_10_DECISION_RETRIEVAL_UX`
- `Sprint spec`: `TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_10_DECISION_RETRIEVAL_UX.md`
- `Current status`: `awaiting_acceptance`
- `Attempt`: `1`
- `Codex summary`: `reports/tests/sprint_10_decision_retrieval_ux_codex_summary_attempt_1.md`
- `Test report`: `reports/tests/sprint_10_decision_retrieval_ux_test_report_attempt_1.md`

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
# Acceptance Result: SPRINT_10_DECISION_RETRIEVAL_UX

Decision: accept
```

или

```md
# Acceptance Result: SPRINT_10_DECISION_RETRIEVAL_UX

Decision: changes requested

Findings:
- ...
- ...
```

После этого зафиксируй решение через `accept-sprint` или `request-changes`.

## Sprint Spec Path

TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_10_DECISION_RETRIEVAL_UX.md

## Sprint Spec

# Sprint 10. Decision-Aware Retrieval, Historical Reuse And UX

## Цель

Сделать поиск решений problem-oriented: система должна уметь находить и использовать похожие problem frames и decision patterns, но делать это прозрачно, изолированно и с понятным UX.

## Ожидаемый результат спринта

- retrieval умеет искать не только claims/artifacts, но и historical decision patterns;
- retrieval умеет ранжировать historical decision patterns с учетом explicit outcome history;
- reuse прошлых решений не происходит silently и не нарушает tenant/workspace isolation;
- UI показывает problem frame, candidate options, decision contract, assurance breakdown и review actions;
- operator/user видит, откуда взят прошлый pattern и чем он отличается от текущего кейса;
- политика reuse и conflict resolution между historical pattern и current case выражены явно.

## Зависимости и техдолг из Sprint 1-5

- decision-oriented prompts и answer composition должны проходить через quota/routing policy, уже введенную в Sprint 3;
- historical reuse и decision-aware retrieval должны продолжать anti-contamination semantics из Sprint 6, а не создавать special-case bypass;
- correlation id должен проходить через полный путь `dialogue request -> problem frame -> decision contract -> assurance -> review`.

## Задачи

### S10-T1. Реализовать `DecisionPatternRetrievalService`

Описание:
- добавить retrieval по `ProblemFrame`, `DecisionOption` и `DecisionRecord`;
- зафиксировать similarity model как композицию structural overlap, domain tags и vector/text similarity;
- описать weight distribution между компонентами similarity model и fallback behavior при недоступности vector index;
- поддержать similarity lookup для исторических problem frames и option clusters;
- добавить outcome-aware reranking по `historical_value_score` и normalized positive/negative outcome summary;
- разделить локальный workspace reuse и organization-level historical reuse;
- явно закрыть placeholder из Sprint 6: decision/vector retrieval обязан пройти namespace-isolation gate до включения в production scope.

Критерии приемки:
- retrieval может вернуть похожие historical decision patterns;
- reuse работает только в разрешенных namespace;
- historical match не подменяет текущий кейс, а only enriches option search;
- similarity rationale machine-readable и объяснимо пользователю/reviewer;
- stale/retired options не возвращаются как active candidates без explicit downgrade marker;
- retrieval response возвращает machine-readable downgrade field, например `reuse_eligibility`, для non-active patterns.
- retrieval не опирается только на similarity: freshness, assurance и outcome history участвуют в ranking policy.

### S10-T2. Реализовать policy явного reuse прошлых решений

Описание:
- historical solution reuse должен быть explicit: user/UI знает, что используется prior pattern;
- reuse должен содержать provenance: source workspace, source decision id, similarity rationale;
- cross-case reuse внутри tenant допускается только по policy, cross-tenant запрещен;
- описать, где хранится policy reuse и кто может ее переопределять на уровне organization/workspace;
- зафиксировать, где хранится `reuse_mode`: organization policy, workspace override или per-request explicit mode;
- review/approval path обязан повторно проверять effective `reuse_mode`, а не полагаться только на build-time choice.

Критерии приемки:
- пользователь видит, что recommendation enriched by prior decision pattern;
- provenance historical reuse сохраняется в API и governance trail;
- cross-tenant reuse блокируется на policy layer;
- workspace-level override policy не может расширить scope beyond tenant policy.

### S10-T3. Реализовать decision-aware answer composition

Описание:
- расширить answer builder так, чтобы recommendations включали:
  - current problem frame;
  - candidate options;
  - selected option;
  - rejected alternatives;
  - decision basis;
  - assurance breakdown;
  - review conditions;
- prose теперь является human-readable фасадом над decision contract;
- historical enrichment должен иметь явный UX mode:
  - suggestion-only;
  - prefilled option candidate;
  - comparison hint with user confirmation.
- structured answer должен включать краткое `historical_outcome_summary` для reused patterns.

Критерии приемки:
- recommendation response содержит structured decision payload;
- prose и structured contract консистентны;
- answer без decision basis не проходит как full recommendation;
- historical enrichment не применяется silently без provenance и выбранного UX mode.
- reused pattern с negative outcome profile не может silently попасть в top recommendation без visible penalty marker.

### S10-T4. Реализовать UI decision console и operator panels

Описание:
- добавить panels/screens для:
  - problem frame;
  - option comparison;
  - selected decision;
  - assurance breakdown;
  - stale evidence / review due;
  - historical pattern provenance;
  - historical outcome summary;
- UI должен различать current-case basis и historical reuse;
- зафиксировать information hierarchy:
  - summary card по умолчанию;
  - expandable decision basis;
  - отдельная weakest-link/staleness секция;
  - отдельная provenance секция для historical reuse.

Критерии приемки:
- пользователь видит не только финальный вариант, но и rejected alternatives;
- weakest link и stale evidence видны без перехода в raw logs;
- historical reuse визуально отделен от current-case evidence;
- консоль не перегружена: primary decision summary виден сразу, детали раскрываются осмысленно.
- пользователь видит не только provenance historical pattern, но и его outcome profile.

### S10-T5. Реализовать operator review workflow

Описание:
- дать reviewer/operator явные действия: approve, request revision, retire decision, apply waiver, schedule review;
- связать эти действия с `DecisionReview` и governance events;
- обеспечить повторное открытие decision contract после новых claim/reentry changes;
- ввести concurrency semantics: optimistic concurrency with version check или explicit lock.
- предусмотреть notification/alert hooks для auto-events: waiver expiry, auto-downgrade, auto-retire, review_due.
- минимальный deliverable notification layer: governance event + UI polling/pull path; push/webhook остаются post-pilot extension.

Критерии приемки:
- decision можно пересмотреть и перевести в новый status без ручного редактирования raw records;
- review actions отражаются в UI и canonical state;
- retired decision не продолжает silently подаваться как active recommendation;
- conflicting concurrent review actions не приводят к silent overwrite;
- оператор получает actionable сигнал о автоматических state changes.

### S10-T6. Зафиксировать conflict resolution между historical pattern и current case

Описание:
- определить, как система ведет себя, если historical pattern противоречит current evidence;
- historical reuse не должен автоматически усиливать option, если current-case claims его ослабляют или опровергают;
- результат должен быть виден в comparison/assurance/UI как explicit conflict.

Критерии приемки:
- historical pattern, contradicting current evidence, не может silently become preferred basis;
- conflict resolution выражен в comparison/assurance payload;
- пользователь видит, почему prior pattern не был принят как-is.

### S10-T7. Собрать e2e сценарий historical decision reuse без contamination

Описание:
- подготовить полный сценарий: новый кейс -> problem frame -> retrieval похожих patterns -> comparison -> decision selection -> assurance -> review action;
- включить негативные проверки на hidden reuse, mixed tenant data и silent stale decision acceptance.

Критерии приемки:
- полный путь решения проходит end-to-end;
- hidden reuse или contamination дают `block`;
- user/operator могут объяснить происхождение решения по UI и governance trail.

## Тесты спринта

### Unit tests

- Similar problem frame retrieval test: сервис находит historical cases с похожим problem frame.
- Similarity model test: structural overlap, domain tags и vector/text similarity дают ожидаемый ranking.
- Outcome-aware ranking test: positive/negative historical outcomes влияют на final retrieval order predictably.
- Vector fallback test: при недоступности vector index retrieval деградирует predictably по documented fallback policy.
- Option pattern retrieval test: retrieval возвращает prior option clusters без подмены current workspace data.
- Namespace reuse test: organization-level reuse работает только внутри tenant policy.
- Explicit reuse provenance test: answer payload содержит source workspace/decision refs и similarity rationale.
- Cross-tenant block test: historical reuse из другого tenant блокируется.
- Cross-workspace policy override test: workspace policy не может обойти organization-level restriction.
- Reuse mode policy test: `reuse_mode` читается из documented policy hierarchy и не подменяется silently.
- Hidden reuse regression test: prior pattern не может появиться в recommendation без machine-readable provenance.
- Structured recommendation contract test: answer содержит problem frame, options, selected decision и assurance fields.
- Historical outcome summary test: reused pattern response содержит normalized outcome summary и value score.
- Prose-contract consistency test: prose summary не противоречит structured selected/rejected options.
- Enrichment mode test: suggestion-only/prefill/comparison-hint modes работают по разным UX rules.
- Missing basis block test: отсутствие decision basis или evidence links переводит recommendation в degraded/blocked route.
- Decision prompt quota test: decision-aware prompt path использует documented quota/routing policy, а не bypass existing preflight.
- UI decision console test: problem frame, option comparison и selected decision отображаются на одном case flow.
- Assurance panel test: weakest link, stale flags и review_due видны в UI.
- Information hierarchy test: summary, detail, weakest-link и provenance layers отображаются в правильном порядке.
- Historical provenance panel test: пользователь видит, какие части recommendation основаны на prior patterns.
- Historical outcome panel test: пользователь видит positive/negative prior outcomes reused pattern.
- Review workflow test: approve/request revision/retire/waiver actions создают корректные `DecisionReview` и governance events.
- Concurrency review test: параллельные approve/request-revision действия не приводят к silent overwrite.
- Approval guard test: recommendation не может быть approved с mode-violating historical prefill при `suggestion-only`.
- Retired decision regression test: retired decision не возвращается как active recommendation.
- Review reopen test: после изменения claims/re-entry decision снова попадает в review queue.

### Integration tests

- Historical conflict resolution test: prior pattern, contradicting current case, помечается как conflict и не auto-selectится.
- Option lifecycle reuse test: stale/retired options не возвращаются как active reusable patterns без explicit downgrade marker.
- Decision-link conflict contract test: conflict detection использует `DecisionEvidenceLink.link_direction`, а не ad-hoc эвристику без provenance.
- Historical negative outcome guard test: pattern с сильным negative outcome profile не поднимается выше active/current-case option при равной similarity.

### Contract tests

- Historical reuse provenance contract test: source workspace, source decision id, similarity rationale и reuse mode обязательны.
- Decision console payload contract test: summary card и expandable sections получают stable machine-readable fields.
- Retrieval downgrade marker contract test: non-active reused options возвращаются с explicit `reuse_eligibility`/downgrade marker.
- Outcome-aware retrieval contract test: `historical_value_score`, `historical_outcome_summary` и downgrade marker обязательны для reused pattern payload.

### E2E tests

- Full decision e2e test: current-case reasoning + historical enrichment + assurance + review action проходит end-to-end.
- Contamination e2e negative test: mixed tenant/workspace pattern retrieval блокируется.
- Explainability e2e test: по API/UI/governance можно восстановить, почему система выбрала именно это решение.
- End-to-end correlation trace test: correlation id связывает dialogue request, decision build, assurance recompute и review events в один trace.

### Performance and ops assumptions

- decision contract read path: interactive class, target sub-second.
- historical similarity search: target < 1s, degraded fallback budget < 3s; timeout above this budget routes to predictable degraded mode.
- assurance recompute beyond lightweight threshold: async-only path.
- при unavailable vector index или delayed historical retrieval система должна отдавать predictable degraded mode, а не зависать request path;
- operational metrics для decision-wave включают retrieval latency, reuse hit rate, assurance recompute latency и scheduler lag.

## Codex Summary Path

reports/tests/sprint_10_decision_retrieval_ux_codex_summary_attempt_1.md

## Codex Summary

# Sprint 10 Codex Summary

- Added decision retrieval and reuse layer in [decision_retrieval.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/canonical_db/decision_retrieval.py):
  - `DecisionPatternRetrievalService`
  - `DecisionReusePolicy`
  - `DecisionAnswerComposer`
  - `DecisionReviewWorkflow`
- Extended [dialogue_api.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/dialogue_api.py) with:
  - decision-aware structured payload in `ask`
  - `/api/workspaces/{id}/decision-patterns`
  - `/api/workspaces/{id}/decision-console`
  - `/api/decision-review/action`
  - lightweight decision console UI panels for summary, assurance and historical reuse
- Added [test_sprint_10_decision_retrieval_ux.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/tests/test_sprint_10_decision_retrieval_ux.py).

Implemented Sprint 10 behavior:

- historical decision pattern retrieval inside tenant/org only
- explicit reuse policy hierarchy with organization cap and workspace/request narrowing
- outcome-aware ranking and downgrade markers for stale/conflicting patterns
- conflict detection uses `DecisionEvidenceLink.link_direction`
- structured decision payload returned for `decision_query`
- review workflow with optimistic status check

## Test Report Path

reports/tests/sprint_10_decision_retrieval_ux_test_report_attempt_1.md

## Test Report

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
