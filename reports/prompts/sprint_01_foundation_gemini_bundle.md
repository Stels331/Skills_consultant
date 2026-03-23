# Gemini Bundle: SPRINT_01_FOUNDATION

## Sprint State

```json

{
  "current_sprint": "SPRINT_01_FOUNDATION",
  "status": "awaiting_review",
  "review_status": "pending",
  "attempt": 1,
  "last_commit": "not-created (Не удалось создать commit: sandbox запрещает запись в git index (`fatal: Unable to create '.git/index.lock': Operation not permitted`).)",
  "codex_summary_path": "reports/tests/sprint_01_foundation_codex_summary_attempt_1.md",
  "test_report_path": "reports/tests/sprint_01_foundation_test_report_attempt_1.md",
  "review_report_path": null
}

```

## Reviewer Prompt

# Gemini Review Prompt Template

Ты `Gemini`, reviewer текущего спринта.

Ты не пишешь код и не предлагаешь делать следующий спринт заранее.

## Входные данные

- `Current sprint`: `SPRINT_01_FOUNDATION`
- `Sprint spec`: `TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_01_FOUNDATION.md`
- `Commit`: `not-created (Не удалось создать commit: sandbox запрещает запись в git index (`fatal: Unable to create '.git/index.lock': Operation not permitted`).)`
- `Codex summary`: `reports/tests/sprint_01_foundation_codex_summary_attempt_1.md`
- `Test report`: `reports/tests/sprint_01_foundation_test_report_attempt_1.md`
- `Git diff hint`: `No commit recorded yet`

## Твоя задача

Проверь только текущий спринт:

- соответствуют ли изменения задачам спринта;
- выполнены ли критерии приемки;
- покрыты ли тесты из sprint file;
- есть ли behavioural regressions;
- вышел ли Codex за scope спринта.

## Формат ответа

Верни только JSON-объект, без markdown-обертки и без пояснений вне JSON.

Если review пройден:

```json
{
  "status": "pass",
  "report": "Коротко: что проверено и почему спринт можно закрывать"
}
```

Если review не пройден:

```json
{
  "status": "fail",
  "report": "Findings по приоритету, ссылки на незакрытые задачи/критерии и что именно должен исправить Codex"
}
```

## Ограничения

- не одобряй по общему впечатлению;
- не выходи за текущий sprint file;
- не требуй unrelated refactors;
- не предлагай следующий спринт до статуса `pass`.

## Sprint Spec Path

TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_01_FOUNDATION.md

## Sprint Spec

# Sprint 1. Canonical DB Foundation

## Цель

Сделать PostgreSQL каноническим источником состояния, сохранив файловый слой как export/debug compatibility layer.

## Ожидаемый результат спринта

- базовая PostgreSQL schema покрывает account, workspace, artifact, claim, dialogue и governance сущности;
- migration workflow воспроизводим через Alembic;
- существующие file-based workspaces можно импортировать в БД;
- новые workspace пишутся в БД и materialize-ятся в файловый слой через dual-write;
- API собирается в базовый production Docker image;
- есть явная rollback policy для миграции.

## Задачи

### S1-T1. Спроектировать и зафиксировать canonical schema

Описание:
- реализовать таблицы `users`, `organizations`, `memberships`, `workspaces`, `workspace_versions`, `artifacts`, `claims`, `claim_versions`, `claim_relations`, `dialogue_sessions`, `dialogue_messages`, `question_queue`, `validation_runs`, `governance_events`, `retrieval_chunks`, `embedding_jobs`, `reentry_jobs`, `quota_ledger`;
- добавить обязательные поля `organization_id` и `workspace_id` во все case-bound сущности;
- синхронизировать SQL/DDl со спецификациями `09-11` до старта реализации, включая:
  - добавление отсутствующих `organization_id` в case-bound таблицы;
  - добавление `workspace_version_id` и `question_class` в `dialogue_messages`;
  - исправление типов полей наподобие `confidence_score`;
  - сверку `version-aware dialogue` и `re-entry` полей со сценариями Sprint 3-5;
- определить ключи, уникальные ограничения, enum-поля статусов и индексы под retrieval и governance trail.

Артефакты:
- ERD или schema notes;
- первая миграция Alembic;
- документ с data rules и naming conventions.

Критерии приемки:
- схема соответствует `02_DATABASE_SPEC.md` и `08_AUTH_BILLING_AND_TENANT_ER_MODEL.md`;
- схема дополнительно синхронизирована с runtime/API требованиями `09_DIALOGUE_RETRIEVAL_ARCHITECTURE.md`, `10_DIALOGUE_LAYER_IMPLEMENTATION_PLAN.md`, `11_DIALOGUE_MODEL_UPDATE_AND_REENTRY_SPEC.md`;
- все связи tenant -> workspace -> dialogue/claims выражены внешними ключами;
- есть индексы для `organization_id`, `workspace_id`, `session_id`, `claim_type`, `status`, `created_at`.

### S1-T2. Внедрить migration workflow и bootstrap БД

Описание:
- настроить Alembic env и соглашения по ревизиям;
- подготовить dev/test/prod конфигурации подключения;
- добавить команду bootstrap для локального подъема схемы;
- зафиксировать rollback-процедуру на случай неуспешной миграции.

Артефакты:
- `alembic.ini`, env, template revisions;
- команды в `Makefile` или scripts;
- runbook по миграциям.

Критерии приемки:
- пустая БД поднимается одной командой;
- миграции идемпотентно применяются в CI и локально;
- downgrade тестируется хотя бы на одну ревизию назад.

### S1-T3. Реализовать repository layer для canonical reads/writes

Описание:
- создать repository abstractions для users, organizations, workspaces, artifacts, claims, dialogue sessions и governance events;
- отделить domain models от ORM/storage деталей;
- подготовить транзакционные границы для case write operations.

Артефакты:
- repository interfaces;
- DB-backed implementations;
- transaction helpers.

Критерии приемки:
- pipeline и будущий dialogue layer читают state через repositories;
- запись complex aggregate выполняется атомарно;
- layer допускает подмену на test doubles.

### S1-T4. Собрать importer из файловой модели в БД

Описание:
- реализовать загрузку legacy workspace из файлового формата;
- переносить artifacts, claims, governance trail и version metadata;
- логировать частичные ошибки и unsupported sections;
- маркировать импортированный workspace как migrated с trace на source path.

Артефакты:
- importer service/CLI;
- import report format;
- mapping table `file entity -> DB entity`.

Критерии приемки:
- importer переносит минимум один реальный workspace end-to-end;
- импорт не дублирует записи при повторном запуске;
- import report показывает ошибки, пропуски и статистику.

### S1-T5. Ввести dual-write и file materialization foundation

Описание:
- для новых workspace первичная запись идет в БД;
- file export остается вторичным слоем для совместимости и debug;
- materialization выполняется из canonical DB state, а не из ad hoc runtime объектов;
- определить exit criteria для отключения file-primary режима.

Артефакты:
- dual-write policy;
- export materializer foundation;
- checklist выхода из legacy режима.

Критерии приемки:
- новый workspace появляется и в БД, и в экспортируемой файловой структуре;
- расхождения между DB и export фиксируются как ошибки синхронизации;
- повторная materialization детерминирована.
- формализованы измеримые `dual-write exit criteria`, которые будут пересмотрены в Sprint 7 перед cutover decision.

### S1-T6. Подготовить Docker foundation для API

Описание:
- собрать production-like image для API;
- вынести env-driven конфигурацию БД и storage;
- добавить health bootstrap для контейнера;
- зафиксировать базовый compose/deploy сценарий.

Артефакты:
- Dockerfile;
- `.dockerignore`;
- стартовый deployment note.

Критерии приемки:
- контейнер собирается без ручных шагов;
- миграции и запуск приложения выполнимы в контейнере;
- health endpoint проверяется оркестратором.

## Тесты спринта

### Для S1-T1

- Migration schema test: создание чистой БД поднимает все таблицы и внешние ключи без пропусков.
- Constraint test: попытка создать `workspace` без `organization_id` или `dialogue_message` без `session_id` завершается ошибкой схемы.
- Index presence test: smoke-проверка существования критичных индексов через introspection.
- Schema sync regression test: DDL содержит `workspace_version_id`, `question_class`, корректные tenant fields и согласованный тип `confidence_score`.

### Для S1-T2

- Upgrade/downgrade test: `upgrade head -> downgrade -1 -> upgrade head` не ломает схему.
- Config test: dev/test окружения читают DSN из env без хардкода.
- CI bootstrap test: тестовая БД поднимается с нуля в автоматическом сценарии.

### Для S1-T3

- Repository unit tests: CRUD для users, organizations, workspaces, claims и governance events.
- Transaction integrity test: при падении на записи claim relations транзакция откатывает весь aggregate.
- Read model parity test: repository возвращает те же данные, что и legacy reader на контрольном workspace.

### Для S1-T4

- Import integration test: импорт тестового workspace создает artifacts, claims, versions и governance events в ожидаемом количестве.
- Idempotency test: повторный импорт того же workspace не создает дубликаты.
- Fault reporting test: поврежденный файл не валит весь импорт, а попадает в import report как partial failure.

### Для S1-T5

- Dual-write integration test: создание нового workspace записывает canonical state в БД и materialized export на диск.
- Determinism test: повторная materialization без изменений не меняет export diff.
- Sync alarm test: искусственное расхождение DB/export приводит к диагностируемому error event.
- Exit criteria test: для dual-write зафиксированы измеримые показатели расхождения, полноты export и rollback readiness.

### Для S1-T6

- Docker build test: image собирается в CI.
- Container smoke test: контейнер стартует, видит БД и отвечает на `/health`.
- Startup migration test: контейнер в чистом окружении применяет миграции и поднимает API без ручных шагов.

## Codex Summary Path

reports/tests/sprint_01_foundation_codex_summary_attempt_1.md

## Codex Summary

Реализован Sprint 1 foundation: канонический DB-слой с первой миграцией и schema notes, env-driven bootstrap/migration workflow, repository layer с транзакциями, importer legacy workspace, dual-write materialization foundation, health API/Docker assets. Дополнительно исправлен разрыв между runbook и репозиторием: в Makefile добавлены рабочие `db-bootstrap`, `db-upgrade`, `db-downgrade`, `db-current-revision` и `import-legacy-workspace` targets. Обновлены implementation summary и test report в `reports/tests/`.

## Test Report Path

reports/tests/sprint_01_foundation_test_report_attempt_1.md

## Test Report

Запущен `python3 -m unittest tests.test_sprint_01_foundation` — 8/8 тестов пройдено, 0 failures, 0 errors. Дополнительно проверен bootstrap workflow через Makefile: `CANONICAL_DB_DSN=sqlite:////tmp/sprint01_make.sqlite3 make db-bootstrap` -> revision `20260322_0001`, `make db-current-revision` -> `20260322_0001`, `make db-downgrade` -> `base`. Попытка `docker build -t electronic-consultant-s1 .` не выполнена из-за окружения: Docker daemon недоступен (`Cannot connect to the Docker daemon`).

## Review Target Commit

not-created (Не удалось создать commit: sandbox запрещает запись в git index (`fatal: Unable to create '.git/index.lock': Operation not permitted`).)

## Diff Hint

No commit recorded yet
