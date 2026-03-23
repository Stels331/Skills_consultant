# Codex Bundle: SPRINT_05_MODEL_UPDATES_REENTRY

## Sprint State

```json

{
  "current_sprint": "SPRINT_05_MODEL_UPDATES_REENTRY",
  "status": "in_progress",
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

- `Current sprint`: `SPRINT_05_MODEL_UPDATES_REENTRY`
- `Sprint spec`: `TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_05_MODEL_UPDATES_REENTRY.md`
- `Sprint status`: `in_progress`
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

## Previous Acceptance Notes Path

none

## Previous Acceptance Notes

Not provided
