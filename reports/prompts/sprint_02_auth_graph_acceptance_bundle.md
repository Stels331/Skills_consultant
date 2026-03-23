# Acceptance Bundle: SPRINT_02_AUTH_GRAPH

## Sprint State

```json

{
  "current_sprint": "SPRINT_02_AUTH_GRAPH",
  "status": "awaiting_acceptance",
  "attempt": 1,
  "last_commit": "not-created (local changes ready for manual review)",
  "codex_summary_path": "reports/tests/sprint_02_auth_graph_codex_summary_attempt_1.md",
  "test_report_path": "reports/tests/sprint_02_auth_graph_test_report_attempt_1.md",
  "acceptance_notes_path": null
}

```

## Acceptance Prompt

# Manual Acceptance Prompt

Ты выполняешь ручную приемку текущего спринта.

Проверь только текущий спринт:

- `Current sprint`: `SPRINT_02_AUTH_GRAPH`
- `Sprint spec`: `TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_02_AUTH_GRAPH.md`
- `Current status`: `awaiting_acceptance`
- `Attempt`: `1`
- `Codex summary`: `reports/tests/sprint_02_auth_graph_codex_summary_attempt_1.md`
- `Test report`: `reports/tests/sprint_02_auth_graph_test_report_attempt_1.md`

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
# Acceptance Result: SPRINT_02_AUTH_GRAPH

Decision: accept
```

или

```md
# Acceptance Result: SPRINT_02_AUTH_GRAPH

Decision: changes requested

Findings:
- ...
- ...
```

После этого зафиксируй решение через `accept-sprint` или `request-changes`.

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

## Codex Summary Path

reports/tests/sprint_02_auth_graph_codex_summary_attempt_1.md

## Codex Summary

# Sprint 02 Codex Summary

- Добавлена ревизия БД `20260322_0002_auth_graph` с таблицами `user_profiles`, `auth_sessions`, `projection_snapshots`, `materialized_artifact_index_entries`.
- Расширены доменные модели и sqlite-репозитории для profile/session/membership, claim version history, projection snapshots и materialized artifact index.
- Реализованы сервисы `AuthService`, `OrganizationService`, `TenantAuthorizationService`, `ClaimGraphService`, `ProjectionRegistry`, `ProjectionService`, `MaterializedArtifactIndex`.
- Добавлен интеграционный тестовый набор `tests/test_sprint_02_auth_graph.py` под Sprint 2.
- Актуализированы foundation-тесты под наличие второй alembic revision без поломки Sprint 1.

## Test Report Path

reports/tests/sprint_02_auth_graph_test_report_attempt_1.md

## Test Report

# Sprint 02 Test Report

Executed:

```bash
python3 -m unittest tests.test_sprint_02_auth_graph
python3 -m unittest tests.test_sprint_01_foundation tests.test_sprint_02_auth_graph
python3 -m py_compile app/canonical_db/domain.py app/canonical_db/repositories.py app/canonical_db/tenant_auth.py app/canonical_db/claim_graph.py app/canonical_db/projections.py app/canonical_db/runtime.py scripts/run_sprint_loop.py
```

Result:

- `tests.test_sprint_02_auth_graph`: `6 tests`, `OK`
- `tests.test_sprint_01_foundation + tests.test_sprint_02_auth_graph`: `14 tests`, `OK`
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
