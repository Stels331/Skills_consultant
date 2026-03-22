# Sprint 4. FPF Validation, Dialogue API, Single-Case UI

## Цель

Закрыть контур `question -> grounded answer -> validated response -> UI`, не превращая продукт в обычный чат.

## Ожидаемый результат спринта

- backend выдает machine-validated dialogue answer package;
- FPF validator различает `pass`, `degrade`, `block`;
- доступен базовый dialogue API для фронтенда;
- UI показывает активный кейс, grounding, unknowns и validation status;
- single-case workflow usable end-to-end.

## Задачи

### S4-T1. Реализовать `FPFResponseValidator`

Описание:
- проверять traceability, epistemic separation, unsupported conclusions, uncertainty routing и anti-cross-case contamination;
- возвращать `pass`, `degrade`, `block`;
- поддержать escalation retry loop в допустимых пределах.

Критерии приемки:
- validator независим от prompt builder;
- blocked answer не возвращается как normal completed answer;
- degraded answer маркируется reason codes.

### S4-T2. Зафиксировать answer contract и dialogue API

Описание:
- контракты для `GroundedAnswer`, validation payload, used claims, used artifacts, open unknowns;
- API endpoints для session history, ask question, evidence panel data, open questions data;
- версии контрактов должны быть готовы для фронтенда и тестов.

Критерии приемки:
- фронтенд получает один структурированный payload вместо ad hoc полей;
- answer API возвращает validation status и grounding references;
- контракты документированы и schema-validated.

### S4-T3. Реализовать базовый single-case UI

Описание:
- Case Overview, Dialogue Console, Evidence/Claims Panel, Open Questions Panel;
- верхняя плашка с organization, workspace title, `workspace_id`, stage, model status;
- answer cards с `epistemic_status`, `confidence_score`, `FPF status`, used claims/artifacts.

Критерии приемки:
- UI остается `case-first`, а не `chat-first`;
- пользователь всегда видит, в каком кейсе находится;
- grounding и open unknowns доступны рядом с ответом.

### S4-T4. Реализовать block/degrade UX и safe fallback behavior

Описание:
- для `block` показывать причину, safe fallback и clarification path;
- для `degrade` показывать дисклеймер и пониженную уверенность;
- не допускать визуального смешения заблокированного ответа и нормального ответа.

Критерии приемки:
- `block` не рендерится как successful assistant answer;
- `degrade` содержит человекочитаемое объяснение ограничения;
- пользователь может перейти к следующему безопасному действию.

### S4-T5. Реализовать basic governance/event surfacing

Описание:
- вывести validation events, routing outcome и answer lineage в UI/backend payload;
- подготовить зачаток Governance Log Panel;
- обеспечить trace между answer, validator result и used claims.

Критерии приемки:
- по ответу можно восстановить used claims и validation outcome;
- governance data не требует ручного чтения сырых логов;
- frontend может открыть связанные события без доп. пересчета.

## Тесты спринта

### Для S4-T1

- Validator unit suite: unsupported claim promotion, missing citation, out-of-workspace leakage, uncertainty omission.
- Outcome mapping test: каждый тип нарушения стабильно дает `degrade` или `block` по policy.
- Escalation loop test: blocked answer на `cheap` может эскалироваться только на один tier выше, затем цикл завершается.

### Для S4-T2

- API contract test: ответ `/dialogue/ask` проходит JSON schema validation.
- Session/history integration test: history endpoint возвращает только сообщения активной сессии и workspace.
- Evidence/open questions endpoint test: payload содержит claims, artifacts, unknowns и version metadata.

### Для S4-T3

- Frontend e2e test: пользователь открывает кейс, задает вопрос, видит grounded answer card и evidence panel.
- Context visibility test: верхняя плашка всегда показывает активную организацию и `workspace_id`.
- UI state test: loading, empty state и validation error отображаются различимо.

### Для S4-T4

- Block UX test: blocked payload отображается как safe fallback card, а не как обычный answer.
- Degrade UX test: degraded payload показывает warning/disclaimer и пониженную confidence presentation.
- Clarification CTA test: при `block` пользователь может перейти к clarification path без ручной навигации.

### Для S4-T5

- Traceability integration test: из answer payload доступны links на validator outcome и used claims.
- Governance panel test: validation и routing events отображаются в chronological order.
- Regression test: UI не теряет traceability fields после ответа с `degrade`.
