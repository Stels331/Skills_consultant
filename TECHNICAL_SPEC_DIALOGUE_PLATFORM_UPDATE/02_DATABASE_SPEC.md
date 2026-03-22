# Спецификация базы данных и хранения данных

## 1. Цель

Перевести проект с файлового primary storage на централизованное хранение в PostgreSQL, сохранив файловые workspace как materialized exports и debug-compatible representation.

Рекомендуемый стек:

- `PostgreSQL` — canonical transactional store
- `JSONB` — для гибких артефактов и расширяемых полей
- `pgvector` — для retrieval по claims и артефактам
- filesystem / object storage — для экспортов Markdown, JSON, release packages
- `Alembic` — инструмент миграций схемы БД

## 1.1. Migration strategy

Миграции схемы должны выполняться через `Alembic`.

Правила:

- каждая миграция имеет revision id и зависимость от предыдущей;
- для risky schema changes применяется `expand -> migrate -> contract`;
- destructive changes не должны идти в одном релизе с кодом, который еще зависит от старой схемы;
- rollback path обязателен для reversible migrations;
- на Railway миграции выполняются отдельным deploy/release step;
- zero-downtime rollout требует backward-compatible schema step до переключения приложения.

## 2. Общая стратегия хранения

### 2.1. Canonical source of truth

В БД хранятся:

- users and organizations;
- memberships and permissions;
- workspace state;
- case model;
- artifacts metadata and versions;
- claims and claim relations;
- dialogue sessions and messages;
- question queue;
- validation runs;
- governance events;
- retrieval chunks and embeddings.

### 2.2. Secondary file layer

Файловая структура в `cases/<workspace_id>/` остается для:

- совместимости с текущим pipeline;
- ручного просмотра артефактов;
- export/debug;
- release package generation.

Правило: сначала запись в БД, потом materialization в файлы.

### 2.3. Storage policy for Docker/Railway deployment

При deployment в Railway файловая система контейнера не считается надежным persistent storage. Поэтому:

- PostgreSQL хранит canonical state;
- временные файлы допускаются внутри контейнера только как ephemeral cache;
- persistent exports должны либо пересоздаваться из БД, либо сохраняться во внешнем persistent layer;
- файловый workspace внутри контейнера не может считаться источником истины.

## 3. Основные сущности

### 3.1. workspaces

Хранит кейс как изолированный контур.

Поля:

- `id`
- `organization_id`
- `workspace_key`
- `title`
- `case_type`
- `status`
- `current_stage`
- `active_model_version`
- `reentry_status`
- `metadata_jsonb`
- `created_at`
- `updated_at`

### 3.0. users

Поля:

- `id`
- `email`
- `password_hash`
- `display_name`
- `status`
- `email_verified_at`
- `created_at`
- `updated_at`

### 3.0.1. organizations

Поля:

- `id`
- `name`
- `slug`
- `owner_user_id`
- `status`
- `metadata_jsonb`
- `created_at`
- `updated_at`

### 3.0.2. memberships

Поля:

- `id`
- `organization_id`
- `user_id`
- `role`
- `status`
- `created_at`
- `updated_at`

### 3.2. workspace_versions

Хранит версию case model.

Поля:

- `id`
- `organization_id`
- `workspace_id`
- `version_no`
- `version_label`
- `change_reason`
- `created_by`
- `created_at`

### 3.3. artifacts

Хранит артефакты pipeline и dialogue.

Поля:

- `id`
- `organization_id`
- `workspace_id`
- `workspace_version_id`
- `artifact_type`
- `stage_name`
- `artifact_key`
- `status`
- `format`
- `payload_jsonb`
- `parse_metadata_jsonb`
- `artifact_trust_level`
- `summary_text`
- `file_path`
- `created_at`
- `updated_at`

Для contract-sensitive artifacts canonical storage должен поддерживать:

- `parse_metadata_jsonb`
- `artifact_trust_level`
- field-level provenance / trust metadata inside payload or linked audit event

Это требуется для downstream handling degraded artifacts и для согласованности с file/frontmatter representation.

### 3.4. claims

Хранит типизированные утверждения.

Поля:

- `id`
- `organization_id`
- `workspace_id`
- `workspace_version_id`
- `claim_key`
- `claim_type`
- `statement`
- `epistemic_status`
- `confidence_score`
- `source_kind`
- `source_ref`
- `attributes_jsonb`
- `created_at`
- `updated_at`

Для `confidence_score` рекомендуется диапазон `0.0 .. 1.0`.

### 3.4.1. claim_versions

Хранит immutable history изменений claim.

Поля:

- `id`
- `organization_id`
- `workspace_id`
- `claim_id`
- `version_no`
- `claim_type`
- `statement`
- `epistemic_status`
- `confidence_score`
- `source_kind`
- `source_ref`
- `attributes_jsonb`
- `change_reason`
- `changed_by_actor`
- `created_at`

Правило:

- `claims` хранит только latest active projection;
- каждое изменение claim обязано порождать запись в `claim_versions`.

### 3.5. claim_relations

Хранит связи между claims.

Поля:

- `id`
- `organization_id`
- `workspace_id`
- `from_claim_id`
- `to_claim_id`
- `relation_type`
- `weight`
- `metadata_jsonb`
- `created_at`

### 3.6. dialogue_sessions

Хранит отдельные диалоговые сессии кейса.

Поля:

- `id`
- `organization_id`
- `workspace_id`
- `session_status`
- `session_title`
- `last_message_at`
- `created_at`
- `updated_at`

### 3.7. dialogue_messages

Хранит историю диалога.

Поля:

- `id`
- `organization_id`
- `workspace_id`
- `workspace_version_id`
- `session_id`
- `role`
- `message_type`
- `message_text`
- `grounding_jsonb`
- `fpf_validation_jsonb`
- `model_update_jsonb`
- `created_at`

### 3.8. question_queue

Хранит уточняющие вопросы.

Поля:

- `id`
- `organization_id`
- `workspace_id`
- `session_id`
- `unknown_key`
- `question_text`
- `question_type`
- `priority_score`
- `status`
- `rationale`
- `linked_claim_id`
- `created_at`
- `answered_at`

### 3.9. validation_runs

Хранит результаты validators/gates.

Поля:

- `id`
- `organization_id`
- `workspace_id`
- `session_id`
- `stage_name`
- `target_type`
- `target_id`
- `validator_name`
- `outcome`
- `result_jsonb`
- `created_at`

### 3.10. governance_events

Общий append-only журнал.

Поля:

- `id`
- `organization_id`
- `workspace_id`
- `session_id`
- `event_type`
- `actor_type`
- `actor_id`
- `target_type`
- `target_id`
- `payload_jsonb`
- `created_at`

### 3.11. retrieval_chunks

Хранит chunks для retrieval.

Политика dialogue retrieval должна быть двухслойной:

- typed graph retrieval — primary;
- section/BM25 text retrieval — supplementary only.

Правило:

- text retrieval не может быть единственным answer-grade grounding source при `0` typed claims;
- text retrieval используется только для contextual support, а не как замена claim-grade evidence.

Поля:

- `id`
- `organization_id`
- `workspace_id`
- `artifact_id`
- `claim_id`
- `chunk_type`
- `chunk_text`
- `token_count`
- `metadata_jsonb`
- `embedding`
- `created_at`

### 3.11.1. embedding_jobs

Хранит жизненный цикл embeddings.

Поля:

- `id`
- `organization_id`
- `workspace_id`
- `target_type`
- `target_id`
- `embedding_model`
- `job_status`
- `source_revision`
- `invalidates_revision`
- `created_at`
- `started_at`
- `finished_at`
- `error_message`

### 3.12. reentry_jobs

Хранит асинхронные задания re-entry.

Поля:

- `id`
- `organization_id`
- `workspace_id`
- `trigger_type`
- `trigger_ref`
- `job_status`
- `requested_by_actor`
- `target_stages_jsonb`
- `lock_key`
- `created_at`
- `started_at`
- `finished_at`
- `error_message`

### 3.13. quota_ledger

Хранит preflight reservation и consumed usage.

Поля:

- `id`
- `organization_id`
- `workspace_id`
- `user_id`
- `resource_type`
- `quota_window`
- `reserved_amount`
- `consumed_amount`
- `status`
- `created_at`
- `closed_at`

## 4. Рекомендуемая SQL-схема верхнего уровня

```sql
create table workspaces (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  workspace_key text not null,
  title text not null,
  case_type text not null,
  status text not null,
  current_stage text,
  active_model_version integer not null default 1,
  reentry_status text not null default 'idle',
  metadata_jsonb jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(organization_id, workspace_key)
);

create table users (
  id uuid primary key,
  email text unique not null,
  password_hash text not null,
  display_name text not null,
  status text not null,
  email_verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table organizations (
  id uuid primary key,
  name text not null,
  slug text unique not null,
  owner_user_id uuid not null references users(id),
  status text not null,
  metadata_jsonb jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table memberships (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  user_id uuid not null references users(id),
  role text not null,
  status text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(organization_id, user_id)
);

create table artifacts (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  workspace_id uuid not null references workspaces(id),
  workspace_version_id uuid,
  artifact_type text not null,
  stage_name text not null,
  artifact_key text not null,
  status text not null,
  format text not null,
  payload_jsonb jsonb not null default '{}'::jsonb,
  parse_metadata_jsonb jsonb not null default '{}'::jsonb,
  artifact_trust_level text not null default 'trusted',
  summary_text text not null default '',
  file_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(workspace_id, artifact_key)
);

create table claims (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  workspace_id uuid not null references workspaces(id),
  workspace_version_id uuid,
  claim_key text not null,
  claim_type text not null,
  statement text not null,
  epistemic_status text not null,
  confidence_score numeric(4,3),
  source_kind text,
  source_ref text,
  attributes_jsonb jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (confidence_score is null or (confidence_score >= 0 and confidence_score <= 1)),
  unique(workspace_id, claim_key)
);

create table claim_versions (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  workspace_id uuid not null references workspaces(id),
  claim_id uuid not null references claims(id),
  version_no integer not null,
  claim_type text not null,
  statement text not null,
  epistemic_status text not null,
  confidence_score numeric(4,3),
  source_kind text,
  source_ref text,
  attributes_jsonb jsonb not null default '{}'::jsonb,
  change_reason text not null default '',
  changed_by_actor text not null default '',
  created_at timestamptz not null default now(),
  check (confidence_score is null or (confidence_score >= 0 and confidence_score <= 1)),
  unique(claim_id, version_no)
);

create table claim_relations (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  workspace_id uuid not null references workspaces(id),
  from_claim_id uuid not null references claims(id),
  to_claim_id uuid not null references claims(id),
  relation_type text not null,
  weight numeric(8,4),
  metadata_jsonb jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table dialogue_sessions (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  workspace_id uuid not null references workspaces(id),
  session_status text not null,
  session_title text not null,
  last_message_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table dialogue_messages (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  workspace_id uuid not null references workspaces(id),
  workspace_version_id uuid references workspace_versions(id),
  session_id uuid not null references dialogue_sessions(id),
  role text not null,
  message_type text not null,
  message_text text not null,
  grounding_jsonb jsonb not null default '{}'::jsonb,
  fpf_validation_jsonb jsonb not null default '{}'::jsonb,
  model_update_jsonb jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table question_queue (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  workspace_id uuid not null references workspaces(id),
  session_id uuid references dialogue_sessions(id),
  unknown_key text not null,
  question_text text not null,
  question_type text not null,
  priority_score numeric(8,4) not null default 0,
  status text not null,
  rationale text not null default '',
  linked_claim_id uuid references claims(id),
  created_at timestamptz not null default now(),
  answered_at timestamptz
);

create table validation_runs (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  workspace_id uuid not null references workspaces(id),
  session_id uuid references dialogue_sessions(id),
  stage_name text,
  target_type text not null,
  target_id text not null,
  validator_name text not null,
  outcome text not null,
  result_jsonb jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table governance_events (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  workspace_id uuid not null references workspaces(id),
  session_id uuid references dialogue_sessions(id),
  event_type text not null,
  actor_type text not null,
  actor_id text,
  target_type text not null,
  target_id text not null,
  payload_jsonb jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  check (
    event_type in (
      'workspace_created',
      'artifact_created',
      'artifact_updated',
      'claim_created',
      'claim_updated',
      'claim_promoted',
      'claim_degraded',
      'claim_linked',
      'dialogue_started',
      'user_question_added',
      'assistant_answer_generated',
      'answer_blocked_by_validator',
      'clarification_requested',
      'clarification_accepted',
      'model_reentry_started',
      'model_reentry_finished',
      'projection_emitted',
      'projection_refreshed',
      'stage_recomputed',
      'workspace_exported'
    )
  )
);
```

## 5. Индексы и retrieval

Обязательные индексы:

- `artifacts(workspace_id, stage_name)`
- `claims(workspace_id, claim_type)`
- `claims(workspace_id, epistemic_status)`
- `dialogue_messages(workspace_id, session_id, created_at)`
- `question_queue(workspace_id, status, priority_score desc)`
- `validation_runs(workspace_id, created_at desc)`
- `governance_events(workspace_id, created_at desc)`

Для vector retrieval:

```sql
create extension if not exists vector;

create table retrieval_chunks (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  workspace_id uuid not null references workspaces(id),
  artifact_id uuid references artifacts(id),
  claim_id uuid references claims(id),
  chunk_type text not null,
  chunk_text text not null,
  token_count integer not null,
  metadata_jsonb jsonb not null default '{}'::jsonb,
  embedding vector(1536),
  created_at timestamptz not null default now()
);

create index retrieval_chunks_workspace_idx
  on retrieval_chunks(workspace_id);
```

```sql
create table embedding_jobs (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  workspace_id uuid not null references workspaces(id),
  target_type text not null,
  target_id text not null,
  embedding_model text not null,
  job_status text not null,
  source_revision text not null,
  invalidates_revision text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  error_message text
);

create table reentry_jobs (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  workspace_id uuid not null references workspaces(id),
  trigger_type text not null,
  trigger_ref text not null,
  job_status text not null,
  requested_by_actor text not null default '',
  target_stages_jsonb jsonb not null default '[]'::jsonb,
  lock_key text not null,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz,
  error_message text
);
```

## 4.1. Denormalization rules

Дублирование `workspace_id` и `organization_id` в `dialogue_messages`, `validation_runs`, `governance_events` и похожих таблицах считается intentional denormalization.

Причины:

- дешевые workspace/tenant-scoped queries;
- упрощение audit trail;
- уменьшение join pressure в hot paths.

Обязательное условие:

- repository/service layer обязан проверять consistency между `session_id`, `workspace_id` и `organization_id`.

Критическое правило retrieval:

- каждый search request должен фильтроваться по `workspace_id`
- каждый search request должен фильтроваться по `organization_id`
- cross-workspace search по умолчанию запрещен

## 5.1. Embedding pipeline

Embeddings должны строиться асинхронно worker-ом.

Правила:

- при создании/изменении claim или artifact создается `embedding_job`;
- старые `retrieval_chunks` помечаются stale через revision model;
- retrieval использует только active chunks с актуальной source revision;
- partial re-entry обязан инвалидировать chunks затронутых stages;
- embedding model и стоимость вызова должны фиксироваться в job metadata и usage ledger.

## 6. Event model

Append-only события должны покрывать:

- `workspace_created`
- `artifact_created`
- `artifact_updated`
- `claim_created`
- `claim_promoted`
- `claim_degraded`
- `claim_linked`
- `dialogue_started`
- `user_question_added`
- `assistant_answer_generated`
- `answer_blocked_by_validator`
- `clarification_requested`
- `clarification_accepted`
- `model_reentry_started`
- `model_reentry_finished`
- `projection_emitted`
- `projection_refreshed`
- `stage_recomputed`
- `workspace_exported`

Допускается существование информационного graph-native класса:

- `duplicate_claim_cluster`

`duplicate_claim_cluster` фиксирует дублирование или adjacent epistemic restatement и не считается unresolved contradiction для selection path.

## 7. Data rules

### 7.1. Epistemic rules

- `claim_type` не может быть пустым
- `decision_constraint` не должен компилироваться из `hypothesis`
- `normative_target` не должен смешиваться с `source_fact`
- promotion/degradation claim type должен логироваться событием

### 7.2. Multi-case rules

- все case-bound таблицы обязаны содержать `workspace_id`
- все запросы dialogue/retrieval должны принимать `workspace_id`
- все уникальности должны быть как минимум workspace-scoped

### 7.2.1. Multi-user and tenant rules

- все tenant-bound таблицы обязаны содержать `organization_id`
- все workspace-bound записи должны быть связаны с organization boundary
- доступ к данным должен проверяться по membership, а не только по знанию идентификатора
- retrieval queries должны фильтроваться по `organization_id` и `workspace_id`

### 7.3. Transaction rules

Следующие операции выполняются в одной транзакции:

- запись user clarification
- создание/обновление claims
- создание claim_versions
- запись governance event
- создание re-entry task

## 7.4. Concurrency and locking rules

- для одного workspace одновременно может быть только один active `reentry_job` в статусе `running`;
- повторный trigger создает queued job или coalesced update;
- write path для re-entry-sensitive updates должен брать advisory lock на workspace scope;
- UI и API должны видеть `reentry_status` и не считать refresh synchronous.

## 7.5. Archived workspace policy

- `archived` workspace доступен только для read-only просмотра;
- новые clarification answers в archived workspace запрещены;
- новые re-entry jobs для archived workspace не создаются;
- governance events о read access допустимы, но mutation events запрещены.

## 7.6. Quota enforcement rules

- quota/budget check выполняется до LLM/embedding call, а не пост-фактум;
- provider call без successful preflight reservation запрещен;
- reservation переводится в consumed usage после завершения вызова;
- failed call освобождает reservation или помечает ее canceled.

## 8. Материализация в файлы

После изменения canonical state система должна уметь экспортировать:

- stage artifacts в `cases/<workspace_id>/...`
- governance logs в jsonl
- report artifacts в markdown
- projections в JSON

Экспорт должен быть идемпотентным и воспроизводимым.

Для deployment в Docker/Railway export layer должен считаться secondary representation, которую можно восстановить из БД после redeploy.

## 9. Миграция с файловой модели

Этапы миграции:

1. Ввести БД и таблицы.
2. Написать importer текущих workspace-файлов в БД.
3. На время миграции поддерживать dual-write.
4. Перевести orchestrator/read-model на чтение из БД.
5. Оставить file exports как secondary layer.

### 9.1. Dual-write exit criteria

Dual-write должен быть временным режимом.

Его можно отключать только если одновременно выполнены условия:

- DB read model используется всеми runtime-critical services;
- file exports подтверждены как reconstructable from DB;
- regression suite подтверждает parity DB-first vs export-materialized outputs на согласованном наборе кейсов;
- governance/events больше не зависят от file-first write path.

## 10. Почему PostgreSQL

`PostgreSQL` выбран потому что:

- достаточно строг для canonical workflow state;
- поддерживает JSONB для гибких артефактов;
- поддерживает транзакции и append-only event patterns;
- поддерживает `pgvector` для retrieval;
- позволяет строить materialized projections и аналитические запросы без смены хранилища.

## 11. Deployment implications

Для Railway схема хранения должна учитывать следующее:

- контейнеры приложения stateless относительно canonical data;
- PostgreSQL развернут как отдельный managed service;
- connection string приходит через `DATABASE_URL`;
- миграции БД должны выполняться как отдельный deployment step или release command;
- storage design не должен требовать локального shared filesystem между `api` и `worker`.
- auth/session state не должен храниться только в памяти одного контейнера.
- zero-downtime rollout требует expand/migrate/contract discipline для destructive schema changes.
