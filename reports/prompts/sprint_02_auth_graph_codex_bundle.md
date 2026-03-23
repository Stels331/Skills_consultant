# Codex Bundle: SPRINT_02_AUTH_GRAPH

## Sprint State

```json

{
  "current_sprint": "SPRINT_02_AUTH_GRAPH",
  "status": "in_progress",
  "attempt": 1,
  "last_commit": "not-created (local changes ready for manual review)",
  "codex_summary_path": "reports/tests/sprint_02_auth_graph_codex_summary_attempt_1.md",
  "test_report_path": "reports/tests/sprint_02_auth_graph_test_report_attempt_1.md",
  "acceptance_notes_path": "reports/reviews/sprint_02_manual_acceptance.md"
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

- `Current sprint`: `SPRINT_02_AUTH_GRAPH`
- `Sprint spec`: `TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_02_AUTH_GRAPH.md`
- `Sprint status`: `in_progress`
- `Attempt`: `1`
- `Previous acceptance notes`: `reports/reviews/sprint_02_manual_acceptance.md`

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

TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_02_AUTH_GRAPH.md

## Sprint Spec

# Sprint 2. Auth, Tenant Layer, Claim Graph

## Цель

Ввести tenant-aware account layer и перевести case model на claims/projections в БД, чтобы следующий спринт мог безопасно строить диалог на каноническом графе.

## Ожидаемый результат спринта

- пользователь может зарегистрироваться, войти и переключать организации;
- authorization проверяет tenant boundary до workspace boundary;
- claims, claim versions и relations живут в БД с immutable history;
- validators и projections читают canonical DB read model;
- подготовлена projection infrastructure, на которую позже опирается `ReentryPlanner`.

## Задачи

### S2-T1. Реализовать auth/session foundation

Описание:
- registration, login, logout, password reset hooks;
- session storage и проверка статуса пользователя;
- `email_verified_at`, `last_login_at`, базовые account settings;
- подготовить точки расширения под external auth providers, не делая их обязательными.

Критерии приемки:
- новый пользователь может создать аккаунт и войти;
- заблокированный пользователь не получает session;
- session инвалидируется при logout.

### S2-T2. Реализовать organizations, memberships и role model

Описание:
- CRUD для organizations;
- invite/join flow для membership;
- роли `organization_owner`, `organization_admin`, `workspace_editor`, `workspace_viewer`;
- organization switcher backend contract.

Критерии приемки:
- пользователь видит только свои организации;
- смена active organization меняет контекст всех tenant-aware запросов;
- роль ограничивает допустимые операции.

### S2-T3. Ввести tenant-aware authorization guards

Описание:
- API guards сначала проверяют membership в организации, затем права на workspace;
- исключить доступ по знанию `workspace_id`;
- подготовить policy checks для dialogues, claims, artifacts, question queue и governance events.

Критерии приемки:
- все case-bound endpoints требуют tenant context;
- cross-tenant доступ блокируется до выполнения бизнес-логики;
- unauthorized access логируется как security event.

### S2-T4. Канонизировать claim graph и version history

Описание:
- нормализовать graph-native types: `source_fact`, `derived_metric`, `decision_constraint`, `normative_target`, `interpretation`, `hypothesis`;
- добавить immutable `claim_versions`;
- реализовать `claim_relations` и базовые relation types;
- определить conflict и duplicate handling.

Критерии приемки:
- обновление claim создает новую версию, а не затирает старую;
- relation graph собирается без обращения к файловому traversal;
- true contradiction и duplicate cluster различаются явно.

### S2-T5. Реализовать projections, `ProjectionRegistry` и migration validators на DB read model

Описание:
- materialize dialogue-friendly и validator-friendly projections из canonical БД;
- реализовать `ProjectionRegistry` как registry dependency contracts между node/claim categories и projection kinds;
- зафиксировать projection metadata, достаточную для последующего `updated node -> dependent projections`;
- перевести validators на repositories/projections вместо прямого чтения файлов;
- обеспечить детерминированную пересборку projections.

Критерии приемки:
- validators работают без legacy graph traversal;
- projections можно пересчитать из БД с тем же результатом;
- projection metadata хранит version/freshness context.
- `ProjectionRegistry` доступен как явный deliverable для Sprint 5, а не как скрытая зависимость.

### S2-T6. Реализовать `MaterializedArtifactIndex` foundation

Описание:
- реализовать `MaterializedArtifactIndex` как runtime/read-model индекс артефактов, stages и их projection dependencies;
- зафиксировать связь `projection_type -> consuming stages -> materialized outputs`;
- подготовить интерфейс, которым позже воспользуется `ReentryPlanner`.

Критерии приемки:
- можно вычислить `dependent projections -> affected stages -> stale outputs` без hardcoded stage map;
- индекс пересобирается детерминированно;
- `MaterializedArtifactIndex` доступен как явный deliverable для Sprint 5.

## Тесты спринта

### Для S2-T1

- Auth integration test: регистрация создает `users` и `user_profiles`, login выдает session, logout ее закрывает.
- Negative auth test: неверный пароль и `status != active` не создают session.
- Session expiry test: просроченная session отвергается middleware.

### Для S2-T2

- Membership flow test: owner создает организацию, приглашает пользователя, после join membership получает корректную роль.
- Organization switch test: active organization меняется без доступа к чужим данным.
- Role matrix test: `workspace_viewer` не может редактировать claims, `organization_admin` может управлять membership.

### Для S2-T3

- Tenant security test: пользователь из организации A не может читать workspace организации B даже при корректном `workspace_id`.
- Guard coverage test: все case-bound endpoints требуют membership check.
- Audit test: попытка unauthorized access пишет governance/security event.

### Для S2-T4

- Claim versioning test: update claim создает запись в `claim_versions` и обновляет active pointer.
- Relation integrity test: relation не может связывать claims из разных workspaces.
- Conflict test: противоречащие claims создают `conflict_case`, а семантические дубли — `duplicate_claim_cluster`.

### Для S2-T5

- Projection rebuild test: полный rebuild projections из БД дает стабильный результат на одном и том же dataset.
- Validator parity test: migrated validator outcome совпадает с legacy validator на контрольном наборе кейсов.
- Freshness test: после обновления claim старый projection помечается stale до пересборки.
- Projection registry dependency test: `ProjectionRegistry` корректно находит projection kinds по типу измененного node/claim.

### Для S2-T6

- Artifact index traversal test: `MaterializedArtifactIndex` возвращает stages и outputs для заданного projection type.
- Deterministic rebuild test: повторная сборка индекса не меняет dependency graph без входных изменений.
- Reentry dependency contract test: индекс совместим с `ReentryPlanner` и не требует hardcoded `node_type -> stage`.

## Previous Acceptance Notes Path

reports/reviews/sprint_02_manual_acceptance.md

## Previous Acceptance Notes

# Acceptance Result: SPRINT_02_AUTH_GRAPH

Decision: accept

Notes:
- Sprint accepted by user.
