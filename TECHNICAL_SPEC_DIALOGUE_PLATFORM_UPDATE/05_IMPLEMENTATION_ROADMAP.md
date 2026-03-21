# План реализации и roadmap

## 1. Стратегия внедрения

Обновление должно внедряться поэтапно. Полный одномоментный переход с файловой архитектуры на dialogue platform слишком рискован, потому что затрагивает:

- auth/account model;
- tenant isolation;
- canonical storage;
- runtime orchestration;
- validators;
- retrieval;
- UI;
- migration of existing workspaces.

Поэтому рекомендуется staged rollout.

## 2. Этапы

### Этап 1. Canonical database foundation

Цель:

- ввести PostgreSQL как новый canonical store.

Работы:

- создать users/organizations/memberships schema;
- создать базовую схему таблиц;
- внедрить Alembic migration workflow;
- реализовать repositories;
- написать importer из файловых workspace;
- добавить dual-write для новых кейсов;
- настроить event tables и governance writes.
- подготовить Docker packaging foundation.

Definition of done:

- пользователи и организации живут в БД;
- новые кейсы создаются в БД;
- existing workspace можно импортировать;
- artifacts/claims/events читаются из БД;
- file exports остаются рабочими.
- приложение собирается в базовый production image.
- есть documented migration and rollback policy.

### Этап 1.5. Auth and tenant foundation

Цель:

- ввести account layer и tenant-aware authorization.

Работы:

- registration/login flows;
- session management;
- organization switcher;
- membership and roles model;
- tenant-aware API guards.

Definition of done:

- пользователь может зарегистрироваться и войти;
- пользователь видит только доступные организации;
- workspace access защищен tenant-aware authorization.

### Этап 2. Claim graph and projections

Цель:

- перевести case model на centralized claims/projections.

Работы:

- нормализовать claim types;
- ввести immutable claim version history;
- реализовать claim relations;
- materialize projections из БД;
- адаптировать validators к БД read model;
- добавить anti-cross-case retrieval guards.
- описать и реализовать embedding lifecycle.

Definition of done:

- claims and relations живут в БД;
- claim updates не затирают историю;
- projections собираются без файлового graph traversal;
- validators работают на canonical model.

### Этап 3. Dialogue backend MVP

Цель:

- реализовать диалог по одному кейсу.

Работы:

- dialogue sessions/messages;
- retrieval service;
- quota preflight checks;
- prompt builder;
- answer schema;
- FPF response validator;
- базовый dialogue API.
- LLM adapter layer для нескольких провайдеров.
- базовый policy routing tier model.

Definition of done:

- пользователь может задать вопрос по кейсу;
- ответ LLM привязан к claims/artifacts;
- ответ проходит validation;
- результат сохраняется в dialogue history.
- direct mode и routing tier selection работают через конфигурацию.
- provider call без quota reservation невозможен.

### Этап 4. Clarification and model updates

Цель:

- сделать пользовательские уточнения частью case model.

Работы:

- question queue;
- clarification UI/API;
- typed answer ingestion;
- model update engine;
- re-entry planner;
- async re-entry jobs and worker flow;
- diff visualization.

Definition of done:

- система умеет задавать уточняющий вопрос;
- пользователь отвечает типизированно;
- модель обновляется;
- affected stages rechecked без полного rerun;
- re-entry выполняется асинхронно и наблюдаем через job status.

### Этап 5. Multi-case isolation

Цель:

- безопасная работа с несколькими кейсами.

Работы:

- workspace-scoped runtime context;
- organization-scoped runtime context;
- workspace-scoped retrieval namespaces;
- anti-contamination validator;
- session switch hard reset;
- regression tests на isolation.

Definition of done:

- вопросы и ответы по разным кейсам не смешиваются;
- retrieval не пересекает case boundaries;
- история и grounding полностью изолированы.

### Этап 6. Full UI and operational hardening

Цель:

- довести решение до production-like usability.

Работы:

- case list and overview;
- dialogue console;
- evidence panel;
- open questions panel;
- governance log;
- observability and monitoring;
- release packaging.
- Railway deployment configuration;
- healthcheck/readiness endpoints;
- worker deployment and queue integration.
- optional OmniRoute integration and diagnostics.

Definition of done:

- полный UX покрывает весь диалоговый сценарий;
- есть метрики, логи и error handling;
- система готова к pilot rollout.

## 3. Предлагаемая разбивка по спринтам

### Sprint 1

- users/organizations/memberships schema
- PostgreSQL schema
- repositories
- workspace importer
- dual-write foundation
- base Dockerfile for api

### Sprint 2

- auth/session foundation
- organization switcher basics
- claims/relations canonicalization
- claim versioning
- projections
- embedding lifecycle
- validator migration to DB read model

### Sprint 3

- dialogue sessions/messages
- retrieval MVP
- answer grounding schema
- LLM provider adapter
- routing policy tiers
- quota enforcement preflight

### Sprint 4

- FPF response validator
- dialogue API
- basic single-case UI

### Sprint 5

- question queue
- clarification flow
- model update engine
- re-entry planner
- re-entry worker and job status API

### Sprint 6

- multi-case isolation
- anti-contamination tests
- workspace switch UX

### Sprint 7

- governance/event observability
- hardening
- pilot readiness
- Railway deployment hardening
- worker/service topology validation
- optional OmniRoute integration
- provider diagnostics and fallback tests

## 4. Основные риски

### 4.1. Data migration risk

Риск:

- старые workspace будут импортированы неполно или неконсистентно.

Снижение риска:

- importer с dry-run mode;
- validation after import;
- сравнение file artifacts с DB projections.

### 4.2. Dialogue hallucination risk

Риск:

- LLM будет отвечать вне case grounding.

Снижение риска:

- strict prompt schema;
- retrieval scoped by workspace;
- FPF validator;
- blocked answer path.

### 4.3. Cross-case contamination risk

Риск:

- при переключении кейсов часть контекста останется в runtime cache.

Снижение риска:

- hard reset on switch;
- namespace-scoped caches;
- contamination regression tests.

### 4.4. Over-complex schema risk

Риск:

- слишком ранняя полная нормализация усложнит разработку.

Снижение риска:

- core entities in relational tables;
- flexible payloads in JSONB;
- iterative normalization.

### 4.5. Retrieval staleness risk

Риск:

- outdated embeddings/chunks отравляют grounding после claim updates и re-entry.

Снижение риска:

- embedding jobs;
- revisioned chunks;
- active/stale separation;
- worker-driven rebuild.

## 5. Тестовая стратегия

Обязательные тесты:

- migration upgrade/rollback tests
- claim version history tests
- embedding invalidation tests
- quota enforcement tests
- auth tests
- membership/role tests
- tenant boundary tests
- migration tests file -> DB
- repository tests
- retrieval scope tests
- dialogue API tests
- FPF validator tests on answers
- clarification update tests
- incremental re-entry tests
- async re-entry job tests
- multi-case contamination tests
- archived workspace policy tests
- UI workflow smoke tests
- Docker image build tests
- Railway smoke deployment tests
- health/readiness tests
- routing policy tests
- direct mode vs OmniRoute mode compatibility tests
- provider fallback tests

## 6. Acceptance checklist

- Canonical model хранится в БД.
- Пользователи и организации изолированы.
- Файлы работают как exports, а не как primary store.
- Один кейс поддерживает grounded dialogue.
- Несколько кейсов поддерживают полную изоляцию.
- Clarification flow меняет модель, а не только историю чата.
- Ответы проходят FPF validation.
- Governance trail хранит весь lifecycle изменений.
- Regression harness покрывает contamination, unlawful promotion и bad grounding.
- API и worker запускаются в Docker без ручных правок образа.
- Railway deployment повторяем и документирован.
- Подключение разных LLM работает через env configuration.
- Optional OmniRoute integration не ломает direct-provider execution path.
- Tenant-aware authorization защищает API, retrieval и dialogue runtime.
- Embedding pipeline и claim history auditability формально покрыты.

## 7. Рекомендуемый порядок практической реализации

1. БД и importer.
2. Auth and tenant foundation.
3. Docker packaging foundation.
4. Canonical claims/projections.
5. Dialogue backend.
6. Validation of answers.
7. Clarification and re-entry.
8. Multi-case and multi-tenant isolation.
9. UI and Railway hardening.
10. Optional OmniRoute integration and provider routing hardening.
