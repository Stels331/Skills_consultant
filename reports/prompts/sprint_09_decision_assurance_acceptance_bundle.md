# Acceptance Bundle: SPRINT_09_DECISION_ASSURANCE

## Sprint State

```json

{
  "current_sprint": "SPRINT_09_DECISION_ASSURANCE",
  "status": "awaiting_acceptance",
  "attempt": 1,
  "last_commit": "14261efcc215a858e648b3fda9c64c239ce217db",
  "codex_summary_path": "reports/tests/sprint_09_decision_assurance_codex_summary_attempt_1.md",
  "test_report_path": "reports/tests/sprint_09_decision_assurance_test_report_attempt_1.md",
  "acceptance_notes_path": null
}

```

## Acceptance Prompt

# Manual Acceptance Prompt

Ты выполняешь ручную приемку текущего спринта.

Проверь только текущий спринт:

- `Current sprint`: `SPRINT_09_DECISION_ASSURANCE`
- `Sprint spec`: `TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_09_DECISION_ASSURANCE.md`
- `Current status`: `awaiting_acceptance`
- `Attempt`: `1`
- `Codex summary`: `reports/tests/sprint_09_decision_assurance_codex_summary_attempt_1.md`
- `Test report`: `reports/tests/sprint_09_decision_assurance_test_report_attempt_1.md`

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
# Acceptance Result: SPRINT_09_DECISION_ASSURANCE

Decision: accept
```

или

```md
# Acceptance Result: SPRINT_09_DECISION_ASSURANCE

Decision: changes requested

Findings:
- ...
- ...
```

После этого зафиксируй решение через `accept-sprint` или `request-changes`.

## Sprint Spec Path

TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_09_DECISION_ASSURANCE.md

## Sprint Spec

# Sprint 9. Decision Assurance, Staleness And Review Lifecycle

## Цель

Сделать надежность решений вычислимой и объяснимой: recommendation должна слабеть при устаревшем или противоречивом evidence, а review/re-entry должны запускаться по явным триггерам.

## Ожидаемый результат спринта

- у каждого `DecisionRecord` есть assurance object с `assurance_score`, `assurance_status`, `weakest_link_ref`, `decay_penalty`, `review_required`;
- формула assurance aggregation зафиксирована как спецификация, а не оставлена “на усмотрение реализации”;
- stale evidence и contradiction signals влияют на trust к решению;
- historical outcome signals влияют на trust к решению как bounded secondary factor;
- review_due и waiver lifecycle становятся явными и аудируемыми;
- re-entry обновляет decision assurance после изменения model/evidence base.

## Зависимости и техдолг из Sprint 1-5

- assurance-aware validation должна расширять `FPFResponseValidator` из Sprint 4, а не заменять его отдельной chain;
- contract между `ReentryPlanner/ReentryWorker` из Sprint 5 и assurance recompute должен быть machine-readable и versioned;
- direct claim update path, если он существует вне explicit re-entry, обязан публиковать invalidation hook для assurance snapshot.

## Задачи

### S9-T1. Реализовать `DecisionAssuranceEngine`

Описание:
- считать assurance не как простое среднее confidence, а по зафиксированной модели агрегации;
- минимально зафиксировать тип модели: `base score * multiplicative penalties`, с отдельным weakest-link floor и contradiction penalties;
- criticality support должна читаться из canonical metadata `DecisionEvidenceLink.criticality`, а не выводиться ad-hoc;
- учитывать freshness supporting evidence, unresolved unknowns и hypothesis-grade supports;
- учитывать `historical_outcome_modifier` из explicit decision outcomes, но в bounded policy envelope;
- возвращать machine-readable assurance breakdown.

Критерии приемки:
- assurance score объясним по breakdown, а не только одним числом;
- weakest supporting element можно явно показать пользователю;
- слабый critical support способен понизить весь decision contract;
- две независимые реализации по спецификации дают совместимый score profile;
- если `criticality` не задана, применяется documented default weight class `standard`.
- historical outcome factor не может вытеснить hard expiry, contradiction или floor policy.

### S9-T2. Ввести freshness/decay policy для decision evidence

Описание:
- добавить `valid_until`/review horizon или эквивалентный freshness policy для decision evidence links;
- разделить `hard expiry` и `soft staleness`;
- по истечении срока понижать assurance и помечать решение как stale/review-required;
- связать expiry с governance events.

Критерии приемки:
- expired critical evidence не оставляет решение в `pass`;
- `hard expiry` и `soft staleness` дают разные penalties и разные user-facing indicators;
- stale flags и decay penalty сохраняются в canonical state;
- evidence expiry виден в UI/API и audit trail.

### S9-T3. Реализовать review triggers и decision refresh orchestration

Описание:
- запускать review, когда updated claim/projection/evidence materially affects existing decision;
- маркировать затронутые `DecisionRecord` как `review_required` до полного recompute;
- после re-entry пересчитывать assurance и review status;
- ввести `recompute_scope`: `full` vs `incremental`.
- зафиксировать контракт с `Sprint 5 ReentryPlanner/ReentryWorker`: re-entry публикует machine-readable changed-support set, который используется assurance engine для invalidation/recompute.
- учесть direct decision-outcome updates как еще один recompute trigger для `historical_outcome_modifier`.

Критерии приемки:
- изменение critical support переводит решение в review path;
- pending re-entry не публикует silently “свежее” решение;
- после успешного re-entry decision assurance обновлен, а stale flags очищены или понижены осмысленно;
- incremental recompute не пересчитывает всю decision graph без необходимости.

### S9-T3.1. Реализовать `DecisionOutcomeResolver`

Описание:
- читать governance/review/re-entry/retirement события и нормализовать их в `DecisionOutcome`;
- не вычислять “успех” решения из свободного текста;
- поддержать outcome types вроде `operator_confirmed`, `implemented_successfully`, `stable_after_reentry_window`, `rejected_after_review`, `caused_reentry`, `retired_due_to_assurance_floor`;
- публиковать нормализованный `historical_outcome_modifier` для assurance engine.

Критерии приемки:
- положительные и отрицательные outcome-события записываются из machine-readable источников;
- resolver не зависит от ad-hoc LLM interpretation;
- один `DecisionRecord` может иметь multiple outcomes с traceable provenance.

### S9-T4. Реализовать explicit `waiver` и override policy

Описание:
- поддержать controlled waiver для временного использования degraded decision;
- waiver должен иметь justification, actor, expiry, scope и residual risk;
- отсутствие или истечение waiver не должно скрывать degradation;
- зафиксировать `renewal_policy`: как система ведет себя при expiry ночью/без оператора.

Критерии приемки:
- waiver не стирает degraded status, а only explains tolerated residual risk;
- expired waiver автоматически возвращает решение в review-required/degraded state;
- waiver lifecycle полностью аудируем;
- expiry policy предсказуема: `auto-expire-notify` или другой явно выбранный режим.

### S9-T5. Расширить validator и dialogue contracts decision assurance полями

Описание:
- хранить `assurance_snapshot` в canonical state и инвалидировать его по событиям вместо обязательного recompute на каждый request;
- зафиксировать snapshot granularity: snapshot хранится на уровне `DecisionRecord`, но содержит link-level breakdown для incremental invalidation;
- добавить в answer/recommendation payload: `assurance_score`, `assurance_status`, `weakest_link_ref`, `review_due`, `staleness_flags`, `waiver_active`;
- если decision contract не проходит assurance threshold, dialogue validator должен деградировать или блокировать output;
- сохранить совместимость с существующим FPF response validator.

Критерии приемки:
- user-facing recommendation показывает не только text, но и assurance state;
- assurance threshold влияет на final validation route;
- weakest-link explanation и review_due доступны через API;
- request path использует cached `assurance_snapshot`, если он не invalidated.
- API может вернуть `historical_outcome_summary` и bounded `historical_outcome_modifier`.

### S9-T6. Добавить governance events decision assurance lifecycle

Описание:
- ввести события `decision_assurance_recomputed`, `evidence_expired`, `decision_downgraded`, `decision_review_due`, `waiver_applied`, `waiver_expired`, `decision_outcome_applied_to_assurance`;
- связать их с re-entry и version state;
- обеспечить доступность этих событий для ops/UI.

Критерии приемки:
- degraded/review-required решения отражаются в ledger;
- assurance recompute и waiver lifecycle читаются хронологически;
- events пригодны для diff/history и audit explanations.
- влияние historical outcomes на assurance читается через ledger отдельно от freshness/waiver events.

### S9-T7. Зафиксировать `assurance floor policy`

Описание:
- определить минимальный уровень reliability, ниже которого decision нельзя держать даже в degraded состоянии;
- различить `degraded but usable` и `must retire`;
- связать floor policy с critical decision classes;
- critical decision classes должны быть конфигурируемы на policy layer организации, а не только hardcoded.

Критерии приемки:
- существует machine-readable threshold для auto-retire/block;
- waiver не обходит assurance floor для запрещенных decision classes;
- floor policy отражается в validator и governance events;
- если organization policy не задала critical classes, применяется documented platform default, а не implicit floor=0.

### S9-T8. Реализовать assurance recompute scheduling

Описание:
- добавить scheduled/background recompute для `soft staleness` и expiry-driven invalidation;
- recompute должен запускаться не только event-driven от claim updates, но и time-driven от freshness horizons;
- operational dependency этого scheduler должна быть совместима с worker topology из Sprint 7;
- scheduler должен быть idempotent при retry/restart после crash.

Критерии приемки:
- истечение freshness horizon без новых user events приводит к recompute/invalidaton;
- scheduling policy документирована и наблюдаема;
- recompute scheduler не конфликтует с обычным re-entry worker;
- crash + restart не создает duplicate `decision_assurance_recomputed` events и не удваивает penalties.

## Тесты спринта

### Unit tests

- Assurance scoring test: critical weak support понижает overall assurance сильнее, чем secondary support.
- Criticality metadata test: engine использует explicit criticality/weight class из evidence link metadata.
- Weakest-link test: engine возвращает ref на конкретный weakest claim/artifact/evidence link.
- Dependency penalty test: contradiction или unresolved unknown повышает penalty без скрытого ignore.
- Aggregation model compatibility test: implementation соответствует зафиксированной multiplicative/floor модели.
- Expired evidence test: evidence за пределом freshness horizon переводит решение в degraded/review-required.
- Hard-vs-soft staleness test: hard expiry и soft staleness дают разные penalties и routes.
- Decay progression test: score уменьшается predictably при наступлении expiry.
- Staleness serialization test: stale flags и decay penalty сохраняются в canonical storage и API.
- Review trigger integration test: update critical claim помечает `DecisionRecord` как `review_required`.
- Reentry refresh test: после re-entry assurance recompute обновляет score и status.
- Incremental recompute scope test: partial re-entry пересчитывает только affected decision supports.
- Pending version honesty test: во время `reentry_status = in_progress` пользователь видит, что решение опирается на current published version.
- Historical outcome modifier test: positive/negative outcomes меняют assurance только в bounded policy range.
- Waiver creation test: waiver сохраняет actor, scope, expiry и justification.
- Waiver expiry test: по истечении waiver решение возвращается в degraded/review-required.
- Renewal policy test: expiry ведет себя согласно зафиксированной policy, а не случайному cron behavior.
- Residual risk visibility test: UI/API показывают waiver как override, а не как hidden pass.
- API contract test: recommendation payload содержит assurance fields и weakest link explanation.
- Validation threshold test: low assurance route переводит response в `degrade` или `block`.
- Assurance snapshot cache test: request path использует cached snapshot, пока он не invalidated event-ом.
- Snapshot granularity test: one-link change инвалидирует link-level breakdown и parent record snapshot predictably.
- Backward compatibility test: обычный grounded answer без decision payload не ломает существующий validator contract.

### Integration tests

- Governance lifecycle test: assurance recompute, expiry и waiver events пишутся append-only.
- Decision diff test: history panel показывает downgrade/review_due transitions.
- Audit explanation test: по event log можно объяснить, почему решение стало weak/stale.
- Assurance floor integration test: решение ниже floor автоматически уходит в retired/blocked route.
- Reentry-assurance contract test: changed-support set из re-entry приводит к корректному partial/full assurance recompute.
- Scheduler expiry integration test: soft staleness без claim update все равно приводит к recompute.
- Scheduler idempotency test: retry/restart scheduler не создает duplicate recompute side effects.
- Outcome-resolver integration test: governance/review/re-entry events нормализуются в `DecisionOutcome` и влияют на assurance recompute.

### Contract tests

- Assurance object schema test: `assurance_score`, `assurance_status`, `weakest_link_ref`, `decay_penalty`, `review_required` обязательны и стабильно сериализуются.
- Waiver policy contract test: `renewal_policy`, `expiry`, `scope`, `residual_risk` обязательны для active waiver.
- Critical decision class policy test: policy layer задает floor-sensitive decision classes machine-readable способом.
- Reentry changed-support contract test: format `changed-support set` зафиксирован и совместим между Sprint 5 и Sprint 9.
- Historical outcome policy contract test: modifier bounds, outcome types и normalized scoring serialизуются machine-readable.

### UI/API tests

- Staleness indicator API test: hard expiry и soft staleness отображаются разными indicator codes.

## Codex Summary Path

reports/tests/sprint_09_decision_assurance_codex_summary_attempt_1.md

## Codex Summary

# Sprint 09 Codex Summary

- Added assurance and waiver canonical entities in [domain.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/canonical_db/domain.py).
- Added Sprint 9 migration [20260323_0006_decision_assurance.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/alembic/versions/20260323_0006_decision_assurance.py).
- Added assurance runtime module [decision_assurance.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/canonical_db/decision_assurance.py) with:
  - `DecisionAssuranceEngine`
  - `DecisionOutcomeResolver`
  - `DecisionAssuranceScheduler`
  - `DecisionWaiverService`
  - sqlite repositories for assurance snapshots and waivers
- Extended [runtime.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/canonical_db/runtime.py) to expose decision repos in the shared bundle.
- Extended [dialogue_validator.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/validation/dialogue_validator.py) with decision-assurance-aware degrade/block route.
- Extended [dialogue_api.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/dialogue_api.py) to attach latest decision assurance payload to dialogue answers when a decision contract exists.
- Added [test_sprint_09_decision_assurance.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/tests/test_sprint_09_decision_assurance.py).

Implemented Sprint 9 behavior:

- assurance snapshot with `assurance_score`, `assurance_status`, `weakest_link_ref`, `decay_penalty`, `review_required`
- hard expiry vs soft staleness handling
- bounded historical outcome modifier
- explicit waiver lifecycle with expiry
- idempotent scheduler-driven recompute
- validator hook that degrades or blocks answers based on decision assurance

## Test Report Path

reports/tests/sprint_09_decision_assurance_test_report_attempt_1.md

## Test Report

# Sprint 09 Test Report

## Commands

```bash
python3 -m py_compile app/canonical_db/domain.py app/canonical_db/decision_assurance.py app/canonical_db/runtime.py app/dialogue_api.py app/validation/dialogue_validator.py alembic/versions/20260323_0006_decision_assurance.py tests/test_sprint_09_decision_assurance.py
python3 -m unittest tests.test_sprint_09_decision_assurance
python3 -m unittest tests.test_sprint_08_decision_domain tests.test_sprint_09_decision_assurance
python3 -m unittest tests.test_sprint_07_hardening_release tests.test_sprint_08_decision_domain tests.test_sprint_09_decision_assurance
python3 -m unittest tests.test_sprint_05_model_updates_reentry tests.test_sprint_06_isolation tests.test_sprint_07_hardening_release tests.test_sprint_08_decision_domain tests.test_sprint_09_decision_assurance
```

## Result

- `py_compile`: passed
- `tests.test_sprint_09_decision_assurance`: passed, 5 tests
- `tests.test_sprint_08_decision_domain + tests.test_sprint_09_decision_assurance`: passed, 12 tests
- `tests.test_sprint_07_hardening_release + tests.test_sprint_08_decision_domain + tests.test_sprint_09_decision_assurance`: passed, 17 tests
- `tests.test_sprint_05_model_updates_reentry + tests.test_sprint_06_isolation + tests.test_sprint_07_hardening_release + tests.test_sprint_08_decision_domain + tests.test_sprint_09_decision_assurance`: passed, 33 tests

## Notes

- Sprint 9 was implemented without advancing sprint-loop state because `SPRINT_08_DECISION_DOMAIN` is still waiting for manual acceptance.
- Assurance payload is attached only when a workspace already has a decision contract; Sprint 7 behavior for ordinary dialogue requests remains compatible.

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
