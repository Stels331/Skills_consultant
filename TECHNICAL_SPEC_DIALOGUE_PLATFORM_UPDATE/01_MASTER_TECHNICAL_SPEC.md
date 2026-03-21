# Полное техническое задание: Dialogue Platform Update

## 1. Идея обновления

Следующее обновление `Electronic Consultant v3` должно превратить текущий FPF-aware pipeline в интерактивную аналитическую платформу, где:

- по входному кейсу строится формализованная case model;
- пользователь может вести диалог с LLM поверх этой модели;
- ответы LLM строятся только на основе текущего кейса и его доказательной базы;
- каждый ответ проходит проверку на соответствие FPF-принципам;
- при нехватке данных система задает пользователю уточняющие вопросы;
- ответы пользователя достраивают модель и могут запускать controlled re-entry затронутых стадий.

Обновление не должно превращать систему в обычный чат. Целевая модель — `case-grounded analytical dialogue`.

## 2. Цели

### 2.1. Бизнес-цели

- Повысить практическую полезность системы после первичного прогона кейса.
- Сделать возможным iterative reasoning без ручной пересборки всего кейса.
- Дать пользователю управляемый способ уточнять исходные данные и сразу видеть влияние на выводы.
- Сохранить auditability и FPF-дисциплину при переходе к интерактивному режиму.

### 2.2. Технические цели

- Ввести централизованную базу данных как canonical source of truth.
- Перевести файловую структуру из primary store в export/debug layer.
- Ввести dialogue layer с жесткой изоляцией кейсов.
- Ввести multi-user account and tenant isolation layer.
- Реализовать retrieval только по текущему workspace.
- Привязать ответы LLM к claims, evidence и governance trail.
- Поддержать partial re-entry и controlled model updates.
- Подготовить систему к воспроизводимому деплою в Railway через Docker-based packaging.
- Поддержать optional LLM gateway layer для policy-based model routing, включая OmniRoute.

## 3. Основание для обновления

Текущая система уже умеет:

- строить workspace по кейсу;
- проводить case через pipeline;
- генерировать viewpoints, characterization, problem/solution artifacts;
- строить evidence graph;
- выполнять orchestrator gating и validations;
- хранить governance trail в файловой модели.

Этого недостаточно для интерактивной работы, потому что:

- файловая структура плохо подходит для быстрого retrieval в диалоге;
- нет централизованной runtime-модели dialogue state;
- история уточнений пользователя не встроена в case model как first-class mechanism;
- при переключении между кейсами высок риск contamination без жесткой изоляции памяти и retrieval.

## 4. Product scope

### 4.1. In scope

- Централизованная БД на базе PostgreSQL.
- Регистрация, аутентификация и управление аккаунтами.
- Организации / tenant model и membership model.
- Dialogue layer поверх case model.
- Multi-case support с полной изоляцией памяти, retrieval и логики.
- Multi-user support с tenant-aware authorization и workspace ownership.
- FPF-aware validation of answers.
- Controlled clarification flow.
- Incremental re-entry затронутых частей модели.
- UI для выбора кейса, диалога, просмотра evidence, вопросов и изменений модели.
- API для работы фронтенда и диалогового оркестратора.
- Контейнеризация сервисов и deployment architecture для Railway.
- Optional gateway integration для multi-provider LLM routing.

### 4.2. Out of scope для первой версии обновления

- Совместная одновременная работа нескольких редакторов в одном кейсе в real-time.
- Полноценный external knowledge search поверх интернета.
- Автоматическая cross-case knowledge transfer.
- Полная замена всех legacy file readers/writers в один этап.

## 5. Ключевые продуктовые сценарии

### 5.1. Первичный анализ кейса

1. Пользователь загружает кейс.
2. Система создает workspace.
3. Pipeline строит базовую модель кейса.
4. Артефакты, claims, evidence и governance events сохраняются в БД.
5. Файловая структура materialize-ится как export layer.

### 5.2. Диалог по кейсу

1. Пользователь открывает конкретный кейс.
2. Задает вопрос по кейсу.
3. Dialogue engine формирует grounding bundle из case model.
4. LLM генерирует структурированный answer draft.
5. FPF response validator проверяет ответ.
6. Пользователь получает ответ, статус уверенности и ссылки на grounding.

### 5.3. Уточнение кейса пользователем

1. Система выявляет unknowns или epistemic gaps.
2. Формирует controlled clarification question.
3. Пользователь отвечает через typed input.
4. Ответ пользователя сохраняется как новый claim/event.
5. Trigger engine определяет, какие стадии надо пересчитать.
6. Выполняется incremental re-entry.
7. Обновленная модель становится доступной для следующих ответов.

### 5.4. Переключение между кейсами

1. Пользователь работал с кейсом `A`.
2. Переключается на кейс `B`.
3. Runtime context кейса `A` сбрасывается.
4. Загружается только dialogue session и retrieval namespace кейса `B`.
5. Ответы LLM строятся только на основании кейса `B`.

## 6. Основные архитектурные принципы

### 6.1. Database-first canonical state

Каноническое состояние кейса хранится в БД. Файлы используются как:

- экспорт;
- кеш;
- debug view;
- compatibility layer для текущих скриптов и артефактов.

### 6.2. Case isolation by design

Каждый кейс является отдельным контуром рассуждения. Между кейсами запрещено неявное смешение:

- prompt context;
- retrieval context;
- dialogue history;
- embeddings;
- unresolved unknowns;
- governance trail.

### 6.2.1. Tenant isolation before workspace isolation

Изоляция должна быть двухуровневой:

- сначала `organization/tenant boundary`;
- затем `workspace boundary` внутри tenant-а.

Пользователь не должен получать доступ к чужим данным даже при знании `workspace_id`.

### 6.3. FPF-aware answer generation

Каждый ответ LLM должен иметь:

- grounding bundle;
- epistemic status;
- used claims;
- unresolved uncertainties;
- результат FPF-проверок.

### 6.4. Controlled user input

Ответы пользователя не пишутся просто как свободный текст в историю. Они должны быть типизированы как:

- `source_fact`
- `assumption`
- `confirmed_assumption`
- `normative_target`
- `decision_constraint`
- `interpretation`

### 6.5. Re-entry only for affected stages

После изменения модели не требуется полный пересчет всего кейса. Система должна уметь вычислять:

- какие claims изменились;
- какие projections устарели;
- какие стадии должны быть rechecked;
- какие решения должны быть downgraded или blocked.

### 6.6. Provider abstraction before gateway dependence

Система должна быть спроектирована так, чтобы vendor routing не был захардкожен в бизнес-логике. Подключение внешнего gateway, включая OmniRoute, допускается только как optional transport/routing layer поверх внутреннего `LLMProviderAdapter`.

## 7. Целевая архитектура системы

Система должна состоять из следующих слоев:

### 7.1. Ingestion and pipeline layer

Отвечает за первичный разбор кейса и построение базовой модели:

- intake;
- layers;
- viewpoints;
- characterization;
- problem_factory;
- solution_factory;
- reporting.

### 7.2. Canonical data layer

Хранит:

- users;
- organizations;
- memberships;
- workspaces;
- artifacts;
- claims;
- claim relations;
- dialogue state;
- validation runs;
- governance events;
- embeddings и retrieval metadata.

### 7.3. Dialogue orchestration layer

Отвечает за:

- создание и ведение dialogue sessions;
- сбор grounding bundle;
- маршрутизацию вопроса;
- генерацию ответа;
- запуск FPF validation;
- формирование clarification requests;
- controlled model updates.

### 7.4. Retrieval layer

Отвечает за поиск релевантных claims и артефактов только в пределах текущего кейса.

### 7.5. Validation and governance layer

Проверяет:

- epistemic separation;
- evidence traceability;
- uncertainty routing;
- comparison discipline;
- anti-cross-case contamination;
- contract consistency;
- freshness / assurance.

### 7.6. Interface layer

Включает:

- workspace selector;
- case overview;
- dialogue console;
- evidence panel;
- open questions panel;
- model changes panel;
- governance log panel.
- auth/account settings;
- organization and membership management;
- billing-ready account administration views.

### 7.7. Deployment and operations layer

Включает:

- Docker packaging для сервисов приложения;
- Railway deployment topology;
- healthcheck/readiness endpoints;
- environment-based provider configuration;
- фоновые worker processes;
- observability, logging и operational configuration.

### 7.8. LLM routing and provider gateway layer

Включает:

- policy-based выбор модели по типу запроса;
- переключение между `cheap`, `balanced`, `premium` routing tiers;
- fallback при недоступности провайдера;
- optional integration с OmniRoute как centralized gateway;
- прямой direct-provider mode без обязательного gateway.

## 8. Функциональные требования

### 8.1. Case management

- Пользователь должен иметь возможность создать новый кейс.
- Пользователь должен иметь возможность открыть существующий кейс.
- Система должна поддерживать список кейсов и их метаданные.
- Каждый кейс должен иметь уникальный `workspace_id`.
- Каждый кейс должен принадлежать конкретной организации.

### 8.1.1. Account and organization management

- Пользователь должен иметь возможность зарегистрироваться.
- Пользователь должен иметь возможность войти и выйти из системы.
- Система должна поддерживать организации и memberships.
- Пользователь должен иметь возможность работать только в разрешенных ему организациях.
- Роли должны определять доступ к workspace и административным операциям.

### 8.2. Dialogue management

- Для каждого кейса может существовать одна или несколько dialogue sessions.
- История сообщений должна храниться отдельно по каждому кейсу.
- Переключение между кейсами не должно переносить историю или reasoning context.
- Диалог должен поддерживать system, user, assistant и validator events.

### 8.3. Grounded answer generation

- Ответ LLM должен формироваться только на основе данных текущего кейса.
- Ответ должен содержать ссылку на использованные claims и artifacts.
- Если evidence недостаточно, система должна возвращать `needs_clarification`.
- Ответ без grounding не должен маркироваться как reliable.
- Выбор модели для ответа должен поддерживать policy routing по классу задачи и бюджетному профилю.

### 8.4. Clarification flow

- Система должна уметь формировать очередь уточняющих вопросов.
- Каждый вопрос должен быть связан с unknown, conflict, stale evidence или violated principle.
- Ответ пользователя должен сохраняться как typed update.
- Ответ пользователя должен проходить базовую валидацию перед включением в модель.

### 8.5. Model update and re-entry

- Любое accepted clarification должно порождать governance event.
- Система должна вычислять affected artifacts/projections/stages.
- Для affected stages должен запускаться orchestrated recheck.
- После re-entry пользователь должен видеть, что изменилось.

### 8.6. Multi-case isolation

- Retrieval по умолчанию запрещен вне текущего workspace.
- Диалоговый prompt builder должен работать только с одним workspace.
- Cross-case entities в ответе должны ловиться validator-ом.
- Все caches должны быть namespace-scoped.

## 9. Нефункциональные требования

### 9.1. Auditability

- Все изменения модели должны быть восстановимы по append-only журналам.
- Для каждого ответа должно быть видно, на чем он основан.
- Для каждого model update должен быть известен actor, source и timestamp.

### 9.2. Performance

- Retrieval ответа по кейсу не должен требовать чтения всего workspace целиком.
- Средний ответ диалога должен собираться из ограниченного набора claims/artifacts.
- UI должен отображать ответ и grounding bundle без полной перезагрузки страницы.

### 9.3. Reliability

- Ошибка в диалоговом слое не должна повреждать canonical case model.
- Недоступность LLM не должна разрушать уже построенную модель кейса.
- Все write operations в БД должны быть transactional.

### 9.4. Security and isolation

- Каждая сессия должна быть привязана к кейсу.
- API не должен возвращать артефакты другого кейса при ошибочном запросе.
- Vector retrieval должен быть отфильтрован по `workspace_id`.

### 9.4.1. Tenant-aware security

- Все tenant-bound запросы должны проверять `organization_id`.
- `workspace_id` не может быть достаточным условием для доступа.
- Retrieval и exports должны быть отфильтрованы по `organization_id` и `workspace_id`.
- Аутентификация и авторизация не могут быть реализованы только на уровне UI.

### 9.5. Deployment portability

- Система должна запускаться локально и в Railway из одних и тех же Docker images.
- Сборка не должна зависеть от неявного platform auto-detection.
- Все runtime dependencies должны быть описаны в Docker image.
- Конфигурация LLM providers должна выполняться через environment variables и secrets.

### 9.6. LLM routing portability

- Система должна поддерживать как direct-provider mode, так и gateway mode.
- Подключение OmniRoute не должно быть обязательным для запуска платформы.
- Переключение между direct mode и OmniRoute mode должно выполняться конфигурацией.
- Policy routing не должен нарушать FPF validation или case isolation.

## 10. FPF-specific requirements

В диалоговом слое ответы должны проходить минимум следующие проверки:

- `EPISTEMIC_SEPARATION`
- `EVIDENCE_TRACEABILITY`
- `UNCERTAINTY_ROUTING`
- `BOUNDARY_DISCIPLINE`
- `ANTI_GOODHART` при рекомендациях и selection claims
- `COMPARABILITY_DISCIPLINE` для сравнительных ответов
- `CROSS_CASE_CONTAMINATION_GUARD`

Каждый answer package должен содержать:

- `answer_text`
- `used_claim_ids[]`
- `used_artifact_ids[]`
- `epistemic_status`
- `confidence_score`
- `open_unknown_ids[]`
- `fpf_checks`
- `needs_user_input`

## 11. Требования к данным

Каноническая модель кейса должна хранить:

- пользователей и организации;
- memberships и роли;
- метаданные workspace;
- версию модели кейса;
- артефакты стадий;
- эпистемические claims;
- relations между claims;
- evidence links;
- dialogue sessions/messages;
- question queue;
- validation history;
- governance ledger;
- materialized projections;
- retrieval index metadata.

## 12. Требования к интерфейсу

UI должен поддерживать:

- регистрацию и login flow;
- account settings;
- organization switcher;
- members/roles management;
- список кейсов;
- создание нового кейса;
- выбор активного кейса;
- отдельный диалог по каждому кейсу;
- отображение grounded answer;
- просмотр evidence и claims;
- просмотр open questions;
- просмотр model changes;
- просмотр governance log.

При переключении кейса UI обязан:

- явно менять active workspace;
- скрывать историю предыдущего кейса;
- инициировать hard reset dialogue runtime;
- подгружать только данные нового кейса.

При переключении организации UI обязан:

- полностью обновлять список доступных workspaces;
- очищать case-bound state от предыдущей организации;
- не показывать артефакты, claims и диалоги другой организации.

## 13. Требования к упаковке и выкладке

### 13.1. Общий подход

Для production deployment система должна поставляться как набор Docker-контейнеров. Railway должен использовать Docker-based deployment, а не неявную auto-build схему как основной способ упаковки.

### 13.2. Обязательная сервисная схема

Минимальная целевая схема развертывания:

- `api` service — HTTP API, orchestration, dialogue endpoints, UI serving;
- `worker` service — фоновые задачи, re-entry, embeddings, долгие pipeline jobs;
- `postgres` service — canonical database;
- `redis` service — опционально для queues, task coordination и short-lived cache.

### 13.3. Правила контейнеризации

- У приложения должен быть production Dockerfile.
- Для worker допускается отдельный Dockerfile или отдельный build target.
- Контейнер не должен использовать локальную файловую систему как primary persistent storage.
- Контейнер должен читать порт из переменной `PORT`.
- Контейнер должен иметь HTTP health endpoint.
- Все системные зависимости должны устанавливаться в образе явно.

### 13.4. Правила для Railway

- Railway deployment должен использовать отдельные сервисы для `api`, `worker` и `postgres`.
- Межсервисное общение должно быть настроено через private networking.
- Секреты и ключи LLM providers должны храниться в Railway Variables/Secrets.
- Приложение должно корректно переживать redeploy без потери canonical state.

### 13.5. Подключение разных LLM

Система должна поддерживать подключение нескольких LLM providers через единый adapter layer.

Обязательные требования:

- выбор провайдера через environment configuration;
- независимые credentials для каждого провайдера;
- runtime switching provider/model per workspace or per request policy;
- отсутствие привязки к одному vendor на уровне deployment.

Дополнительно:

- допускается использование OmniRoute как внешнего LLM gateway для multi-provider routing;
- OmniRoute не должен заменять внутренние FPF checks, case isolation или grounding logic;
- решение о routing tier (`cheap`, `balanced`, `premium`) должно приниматься policy layer приложения.

### 13.6. Минимальный набор runtime variables

- `PORT`
- `DATABASE_URL`
- `REDIS_URL` при использовании очередей
- `LLM_PROVIDER`
- `LLM_MODEL`
- `LLM_GATEWAY_MODE`
- `LLM_ROUTING_TIER`
- `OMNIROUTE_BASE_URL`
- `OMNIROUTE_API_KEY`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- `OPENROUTER_API_KEY`
- `LOG_LEVEL`
- `APP_ENV`

## 14. Критерии приемки

Обновление считается реализованным, если:

1. Система хранит canonical case state в PostgreSQL.
2. Система поддерживает регистрацию, login и organization-bound access control.
3. Для одного кейса доступен интерактивный диалог поверх case model.
4. Для нескольких кейсов диалоги полностью изолированы.
5. Для нескольких пользователей и организаций данные полностью изолированы.
6. Каждый ответ LLM имеет grounding и FPF validation result.
7. Пользователь может ответить на clarification question, и модель кейса корректно достраивается.
8. После изменения модели выполняется partial re-entry affected stages.
9. Все изменения логируются в governance/event tables.
10. Файловые артефакты остаются доступны как export layer.
11. Приложение собирается и запускается через Docker.
12. Production deployment в Railway не требует ручной настройки окружения внутри контейнера.
13. Подключение разных LLM providers выполняется через конфигурацию, без пересборки приложения.
14. Optional integration с OmniRoute не нарушает direct mode и не является обязательной для базового запуска.

## 15. Основные deliverables

- База данных PostgreSQL и миграции.
- Data access layer.
- Auth/account/tenant layer.
- Dialogue orchestration backend.
- Retrieval subsystem.
- FPF response validator.
- Clarification/update engine.
- Multi-case safe API.
- Web UI аналитического диалога.
- Migration scripts file-store -> DB.
- Обновленный acceptance и regression harness.
- Docker packaging для `api` и `worker`.
- Railway deployment configuration и operational runbook.
- Membership, roles и organization management.
