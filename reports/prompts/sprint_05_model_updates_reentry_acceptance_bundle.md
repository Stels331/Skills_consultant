# Acceptance Bundle: SPRINT_05_MODEL_UPDATES_REENTRY

## Sprint State

```json

{
  "current_sprint": "SPRINT_05_MODEL_UPDATES_REENTRY",
  "status": "awaiting_acceptance",
  "attempt": 1,
  "last_commit": "not-created (local changes ready for manual review)",
  "codex_summary_path": "reports/tests/sprint_05_model_updates_reentry_codex_summary_attempt_1.md",
  "test_report_path": "reports/tests/sprint_05_model_updates_reentry_test_report_attempt_1.md",
  "acceptance_notes_path": null
}

```

## Acceptance Prompt

# Manual Acceptance Prompt

Ты выполняешь ручную приемку текущего спринта.

Проверь только текущий спринт:

- `Current sprint`: `SPRINT_05_MODEL_UPDATES_REENTRY`
- `Sprint spec`: `TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_05_MODEL_UPDATES_REENTRY.md`
- `Current status`: `awaiting_acceptance`
- `Attempt`: `1`
- `Codex summary`: `reports/tests/sprint_05_model_updates_reentry_codex_summary_attempt_1.md`
- `Test report`: `reports/tests/sprint_05_model_updates_reentry_test_report_attempt_1.md`

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
# Acceptance Result: SPRINT_05_MODEL_UPDATES_REENTRY

Decision: accept
```

или

```md
# Acceptance Result: SPRINT_05_MODEL_UPDATES_REENTRY

Decision: changes requested

Findings:
- ...
- ...
```

После этого зафиксируй решение через `accept-sprint` или `request-changes`.

## Sprint Spec Path

TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_05_MODEL_UPDATES_REENTRY.md

## Sprint Spec

# Sprint 5. Clarification, Model Updates, Async Re-entry

## Цель

Сделать пользовательские уточнения first-class частью case model и запускать частичный пересчет только затронутых стадий.

## Ожидаемый результат спринта

- система отличает обычный вопрос от model update до retrieval;
- controlled clarification flow пишет типизированные user-origin claims;
- input acceptance не пропускает неоднозначные и условные вводы;
- re-entry планируется через lineage traversal, а не hardcoded stage map;
- async worker публикует новую версию модели и diff изменений.

## Задачи

### S5-T1. Реализовать `question_queue` и `ClarificationEngine`

Описание:
- создавать controlled clarification questions при epistemic gaps;
- хранить причину вопроса, недостающее знание и ожидаемое влияние;
- поддержать статусы `open`, `answered`, `rejected`, `obsolete`.

Критерии приемки:
- unanswered gaps попадают в open questions panel;
- вопрос содержит reason и impact preview;
- obsolete questions закрываются после успешного re-entry.

### S5-T2. Реализовать `TypedInputClassifier`

Описание:
- классифицировать ввод в `user_asserted_fact`, `user_declared_constraint`, `user_hypothesis`, `user_normative_target`;
- различать `clarification_provided` и обычный question path;
- сохранять classifier confidence и rationale.

Критерии приемки:
- raw user text не записывается в graph напрямую;
- provisional type сохраняется отдельно от final graph-native type;
- classifier output пригоден для audit trail.

### S5-T3. Реализовать `InputAcceptanceCheck`

Описание:
- отклонять сообщения, которые являются вопросом в форме утверждения;
- не давать conditional statements сразу стать fact-grade node;
- проверять конфликт со stable claims и insufficient concreteness;
- возвращать rejection/defer result с пояснением.

Критерии приемки:
- conditional input не проходит как `source_fact`;
- failed acceptance не пишет node в graph;
- UI получает понятную причину отклонения.

### S5-T4. Реализовать `ModelUpdateEngine`

Описание:
- после accepted input создавать intermediate user-origin claim;
- писать provenance: actor, source kind, timestamp, workspace version context;
- запускать lawful promotion только отдельным явным действием/правилом;
- обновлять projections и governance trail.

Критерии приемки:
- ledger различает `claim_created` и `claim_promoted`;
- промежуточные user-origin claims не маскируются под production types;
- update flow полностью трассируем.

### S5-T5. Реализовать `ReentryPlanner`

Описание:
- вычислять зависимые projections, affected stages, stale outputs и potentially stale nodes;
- использовать `ProjectionRegistry` и `MaterializedArtifactIndex`;
- готовить `ReentryPlan` для worker queue.

Критерии приемки:
- re-entry не опирается на жесткую таблицу `node_type -> stages`;
- пересчитываются только затронутые стадии;
- stale outputs помечаются до публикации новой версии.

### S5-T6. Реализовать `ReentryWorker`, version state API и diff panel data

Описание:
- worker берет workspace-level lock, исполняет job и публикует completion/failure events;
- API отдает `current_published_version`, `pending_version`, `reentry_status`, `affected_stages`;
- diff строится из event types `claim_created`, `claim_updated`, `claim_promoted`, `claim_degraded`, `projection_refreshed`, `stage_recomputed`.

Критерии приемки:
- пока `reentry_status = in_progress`, диалог отвечает по опубликованной версии;
- новая версия публикуется только после успешного partial recompute;
- diff основан на ledger, а не на произвольном сравнении текстов.

## Тесты спринта

### Для S5-T1

- Clarification generation test: epistemic gap создает запись в `question_queue` с reason и expected impact.
- Queue lifecycle test: question проходит статусы `open -> answered -> obsolete` или `open -> rejected`.
- UI data test: open questions endpoint возвращает reason, influence area и current status.

### Для S5-T2

- Classifier unit test: примеры для всех provisional user-origin types.
- Boundary routing test: сообщение вида "мы можем сдвинуть дедлайн на месяц" классифицируется как clarification/model update, а не ordinary evidence query.
- Audit metadata test: classifier result сохраняет confidence и rationale.

### Для S5-T3

- Acceptance negative test: условный ввод `if budget is 800k...` не записывается как fact-grade claim.
- Contradiction test: ввод, конфликтующий со stable claim, переводится в escalation/defer path.
- Rejection UX test: фронтенд получает reason code и текст пояснения, а graph остается неизменным.

### Для S5-T4

- Model update integration test: accepted clarification создает intermediate claim и governance event.
- Promotion lineage test: последующее lawful promotion пишет отдельный ledger event, не переписывая исходное происхождение claim.
- Provenance test: claim хранит actor=`user`, source kind=`dialogue_clarification`, version context.

### Для S5-T5

- Reentry planner unit test: изменение `decision_constraint` ищет affected projections через registry, а не по hardcoded map.
- Partial recompute test: re-entry plan включает только зависимые stages и stale outputs.
- Staleness marking test: outputs, затронутые планом, получают stale status до завершения worker job.

### Для S5-T6

- Worker integration test: job берет workspace lock, обновляет status и публикует новую версию после успешного recompute.
- Version-aware dialogue test: во время `in_progress` ответы строятся по `current_published_version` и содержат disclaimer.
- Diff generation test: panel data строится из ledger events и корректно показывает `claim_created`, `claim_updated`, `claim_promoted`, `claim_degraded`, `projection_refreshed`, `stage_recomputed`.
- Failure recovery test: при падении worker `pending_version` не публикуется silently, job получает failure status.

## Codex Summary Path

reports/tests/sprint_05_model_updates_reentry_codex_summary_attempt_1.md

## Codex Summary

# Sprint 05 Codex Summary

- Добавлен [app/canonical_db/model_updates.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/canonical_db/model_updates.py) с `ClarificationEngine`, `TypedInputClassifier`, `InputAcceptanceCheck`, `ModelUpdateEngine`, `ReentryPlanner`, `ReentryWorker` и `build_diff_panel`.
- Расширены доменные модели в [app/canonical_db/domain.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/canonical_db/domain.py) и добавлена миграция [20260323_0004_model_updates.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/alembic/versions/20260323_0004_model_updates.py) для metadata полей `question_queue`.
- Подключены `question_queue` и `reentry_jobs` в [app/canonical_db/runtime.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/canonical_db/runtime.py).
- Обновлен [app/dialogue_api.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/dialogue_api.py): open questions, version state, diff panel и version-aware dialogue disclaimer при `reentry_status = in_progress`.
- Расширен ledger whitelist в [app/pipeline/epistemic_ledger.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/app/pipeline/epistemic_ledger.py) событиями `projection_refreshed` и `stage_recomputed`.
- Добавлен тестовый набор [tests/test_sprint_05_model_updates_reentry.py](/Users/stas/Documents/Системное%20Мышление/Системное%20мышление/Skills/FPF-skill_2/electronic_consultant_v3_old/tests/test_sprint_05_model_updates_reentry.py), закрывающий clarification flow, acceptance gate, model update, re-entry planner/worker, version state и diff panel.

## Test Report Path

reports/tests/sprint_05_model_updates_reentry_test_report_attempt_1.md

## Test Report

# Sprint 05 Test Report

Executed:

```bash
python3 -m unittest tests.test_sprint_05_model_updates_reentry
python3 -m unittest tests.test_sprint_01_foundation tests.test_sprint_02_auth_graph tests.test_sprint_03_dialogue_core tests.test_sprint_04_validation_ui tests.test_sprint_05_model_updates_reentry
python3 -m py_compile app/canonical_db/model_updates.py app/dialogue_api.py app/canonical_db/runtime.py app/canonical_db/domain.py tests/test_sprint_05_model_updates_reentry.py
```

Result:

- `tests.test_sprint_05_model_updates_reentry`: `8 tests`, `OK`
- `tests.test_sprint_01_foundation + tests.test_sprint_02_auth_graph + tests.test_sprint_03_dialogue_core + tests.test_sprint_04_validation_ui + tests.test_sprint_05_model_updates_reentry`: `33 tests`, `OK`
- `py_compile`: `OK`

## Commit / Diff Context

not-created (local changes ready for manual review)

## Diff Hint

No commit recorded yet

## Acceptance Checklist

- Все обязательные задачи спринта закрыты.

- Критерии приемки спринта выполнены.

- Релевантные тесты запущены и результаты зафиксированы.

- Нет очевидного scope creep вне спринта.

- Оставшиеся ограничения и blockers описаны явно.
