# Спецификация backend и диалоговой архитектуры

## 1. Цель

Реализовать диалоговый слой поверх case model так, чтобы:

- пользователь задавал вопросы по конкретному кейсу;
- LLM отвечала только на основе case-grounded data;
- ответы проверялись FPF-validator-ами;
- при нехватке данных система задавала controlled clarification questions;
- ответы пользователя достраивали модель и запускали partial re-entry.

## 2. Целевая backend-архитектура

### 2.1. Основные компоненты

- `CaseRepository`
- `ArtifactRepository`
- `ClaimRepository`
- `DialogueSessionRepository`
- `QuestionQueueRepository`
- `GovernanceEventRepository`
- `RetrievalService`
- `PromptBuilder`
- `DialogueOrchestrator`
- `FPFResponseValidator`
- `ClarificationEngine`
- `ModelUpdateEngine`
- `ReentryPlanner`
- `ExportMaterializer`
- `LLMProviderAdapter`
- `DeploymentHealthService`

### 2.2. Обязанности компонентов

`DialogueOrchestrator`:

- принимает пользовательский вопрос;
- получает active workspace and session;
- инициирует retrieval;
- вызывает prompt builder;
- получает answer draft от LLM;
- запускает FPF validation;
- сохраняет ответ и связанные события.

`RetrievalService`:

- извлекает claims и chunks только текущего кейса;
- формирует ranked grounding bundle;
- учитывает signal types: facts, constraints, assumptions, open unknowns, conflicts.

`FPFResponseValidator`:

- проверяет epistemic separation;
- проверяет traceability;
- проверяет uncertainty routing;
- проверяет anti-cross-case contamination;
- определяет `pass`, `degrade`, `block`.

`ClarificationEngine`:

- генерирует уточняющие вопросы;
- пишет их в `question_queue`;
- классифицирует тип недостающего знания;
- объясняет, почему вопрос нужен.

`ModelUpdateEngine`:

- принимает typed answer пользователя;
- создает/обновляет claims;
- пишет governance event;
- обновляет projections;
- передает данные в re-entry planner.

`ReentryPlanner`:

- определяет affected stages;
- запускает incremental checks;
- создает re-entry tasks;
- логирует downgrade/block decisions.

`LLMProviderAdapter`:

- инкапсулирует подключение к разным LLM providers;
- скрывает vendor-specific API differences;
- выбирает provider/model по runtime configuration;
- обеспечивает единый контракт для dialogue orchestrator.
- поддерживает direct-provider mode и optional OmniRoute gateway mode.

`DeploymentHealthService`:

- отдает `health` и `readiness` сигналы;
- проверяет доступность БД;
- проверяет готовность критических backend dependencies;
- используется Railway для health checks.

## 3. Dialogue runtime flow

### 3.1. Ответ на вопрос пользователя

```text
UserQuestion
 -> load active workspace/session
 -> retrieve workspace-grounded context
 -> build prompt bundle
 -> call LLM
 -> validate answer against FPF rules
 -> persist answer + validation + governance events
 -> return grounded answer package
```

### 3.2. Clarification flow

```text
Validator/Retrieval detects uncertainty
 -> ClarificationEngine creates question
 -> question saved to question_queue
 -> UI shows controlled clarification form
 -> user submits typed answer
 -> ModelUpdateEngine creates claims/events
 -> ReentryPlanner computes affected stages
 -> orchestrator runs incremental recheck
 -> updated model becomes active
```

## 4. Prompting model

### 4.1. Prompt composition

Prompt должен состоять из:

- system layer;
- FPF guardrails;
- workspace metadata;
- case summary;
- selected grounding claims;
- selected artifact excerpts;
- current question;
- response schema.

В prompt не должны попадать:

- диалоги другого кейса;
- артефакты другого кейса;
- retrieval chunks без `workspace_id = active_workspace_id`.

### 4.2. Required response schema

LLM должен возвращать структуру вида:

```json
{
  "answer_text": "string",
  "epistemic_status": "observed|inferred|hypothesis|needs_clarification",
  "confidence_score": 0.0,
  "used_claim_ids": ["..."],
  "used_artifact_ids": ["..."],
  "open_unknown_ids": ["..."],
  "needs_user_input": true,
  "clarification_candidates": [
    {
      "unknown_key": "string",
      "question": "string",
      "reason": "string"
    }
  ]
}
```

### 4.3. Prompt guardrails

LLM must be instructed to:

- not answer from general memory when case data is insufficient;
- explicitly mark uncertainty;
- avoid converting hypotheses into constraints;
- avoid referencing data outside the active case;
- prefer asking clarification over hallucinating.

## 4.4. Model routing policy

Система должна поддерживать policy-based выбор модели по типу задачи.

Минимальные routing tiers:

- `cheap`
- `balanced`
- `premium`

Рекомендуемая логика:

- `cheap` — clarification questions, low-risk rewrites, lightweight extraction;
- `balanced` — grounded case Q&A, routine synthesis, viewpoint follow-ups;
- `premium` — high-stakes synthesis, reporting, conflict-heavy reasoning, complex recommendation answers.

Источник policy:

- request type;
- workspace policy;
- environment defaults;
- budget rules;
- operator override.

## 5. FPF response validation

### 5.1. Validation checks

Минимальный набор checks:

- `CROSS_CASE_CONTAMINATION_GUARD`
- `EPISTEMIC_SEPARATION`
- `EVIDENCE_TRACEABILITY`
- `UNCERTAINTY_ROUTING`
- `BOUNDARY_DISCIPLINE`
- `COMPARABILITY_DISCIPLINE`
- `ANTI_GOODHART` для selection/recommendation answers

### 5.2. Validation outcomes

- `pass` — answer can be shown as grounded
- `degrade` — answer shown with warning and uncertainty marker
- `block` — answer is not shown as valid; user gets clarification path or error state

### 5.3. Validator output

```json
{
  "outcome": "pass",
  "issues": [],
  "used_principles": ["EPISTEMIC_SEPARATION", "EVIDENCE_TRACEABILITY"],
  "explanation": "string"
}
```

## 6. Clarification model

### 6.1. Question types

- `missing_fact`
- `missing_constraint`
- `missing_target`
- `source_verification`
- `conflict_resolution`
- `stale_evidence_refresh`

### 6.2. Answer typing

Пользовательский ответ должен иметь тип:

- `source_fact`
- `assumption`
- `confirmed_assumption`
- `normative_target`
- `decision_constraint`
- `interpretation`

### 6.3. Acceptance rules

- ответ не должен добавляться в модель без typing
- ответ должен иметь source or provenance
- если ответ создает hard constraint, validator должен проверить lawful promotion

## 7. Re-entry and model refresh

### 7.1. Re-entry targets

Обновление claims может затрагивать:

- `characterization`
- `problem_factory`
- `solution_factory`
- `reporting`

### 7.2. Triggering rules

Примеры:

- новый fact о бизнес-ограничении -> `characterization`, `problem_factory`, `solution_factory`
- новый target -> `characterization`, `solution_factory`, `reporting`
- resolved conflict -> `problem_factory`, `solution_factory`
- stale evidence refreshed -> affected stage + `reporting`

### 7.3. Result handling

После re-entry система должна:

- обновить projections;
- обновить active model version;
- записать governance events;
- показать diff пользователю.

## 8. API specification

### 8.1. Workspace API

- `GET /api/workspaces`
- `POST /api/workspaces`
- `GET /api/workspaces/{workspaceId}`
- `GET /api/workspaces/{workspaceId}/overview`

### 8.2. Dialogue API

- `GET /api/workspaces/{workspaceId}/sessions`
- `POST /api/workspaces/{workspaceId}/sessions`
- `GET /api/workspaces/{workspaceId}/sessions/{sessionId}/messages`
- `POST /api/workspaces/{workspaceId}/sessions/{sessionId}/messages`

### 8.3. Clarification API

- `GET /api/workspaces/{workspaceId}/questions`
- `POST /api/workspaces/{workspaceId}/questions/{questionId}/answer`

### 8.4. Evidence/Claims API

- `GET /api/workspaces/{workspaceId}/claims`
- `GET /api/workspaces/{workspaceId}/claims/{claimId}`
- `GET /api/workspaces/{workspaceId}/evidence`
- `GET /api/workspaces/{workspaceId}/governance-events`

### 8.5. Re-entry API

- `POST /api/workspaces/{workspaceId}/reentry/plan`
- `POST /api/workspaces/{workspaceId}/reentry/execute`

### 8.6. Operations API

- `GET /health`
- `GET /ready`

### 8.7. Provider diagnostics API

- `GET /api/llm/providers`
- `GET /api/llm/routing-policy`

## 9. Multi-case runtime isolation

### 9.1. Required runtime rules

- active prompt state must be workspace-scoped
- in-memory cache keys must include `workspace_id`
- retrieval namespace must be workspace-scoped
- session messages must be filtered by both `workspace_id` and `session_id`

### 9.2. Switch-case algorithm

```text
switch_case(new_workspace_id):
  flush active prompt context
  flush session-local cache
  clear retrieval result cache
  load sessions for new_workspace_id
  load overview and unresolved questions
  activate new workspace namespace
```

### 9.3. Anti-contamination controls

- validator scans for foreign case entities in assistant response
- grounding bundle fingerprint must reference a single workspace only
- cross-case retrieval is blocked at repository level

## 10. Error handling

Возможные error states:

- `workspace_not_found`
- `session_not_found`
- `cross_case_access_denied`
- `llm_unavailable`
- `answer_blocked_by_fpf_validator`
- `clarification_answer_invalid`
- `reentry_failed`

Каждый error state должен:

- логироваться;
- иметь user-safe explanation;
- не повреждать canonical model.

## 11. Deployment architecture

### 11.1. Docker packaging

Backend должен поставляться как Dockerized services:

- `api` container
- `worker` container

Требования:

- одинаковая кодовая база и конфигурационная модель;
- production dependencies baked into image;
- запуск через command/entrypoint, не зависящий от ручной подготовки окружения;
- поддержка `PORT` для web service.

### 11.2. Railway topology

Целевая deployment topology:

- `api` Railway service
- `worker` Railway service
- `postgres` Railway service
- `redis` Railway service при необходимости очередей

### 11.3. Environment configuration

Backend должен конфигурироваться через environment variables:

- `DATABASE_URL`
- `REDIS_URL`
- `PORT`
- `APP_ENV`
- `LOG_LEVEL`
- `LLM_PROVIDER`
- `LLM_MODEL`
- `LLM_GATEWAY_MODE`
- `LLM_ROUTING_TIER`
- `OMNIROUTE_BASE_URL`
- `OMNIROUTE_API_KEY`
- provider-specific API keys

### 11.4. LLM provider abstraction

Поддержка нескольких LLM должна быть реализована через adapter interface, а не через прямые вызовы vendor SDK из бизнес-логики.

Минимальные требования:

- единый интерфейс `generate_response(...)`
- единый интерфейс `embed(...)`, если embeddings делает тот же провайдер
- provider selection без пересборки контейнера
- graceful failure при недоступности конкретного провайдера

### 11.5. OmniRoute integration

OmniRoute допускается как optional centralized gateway для:

- cost-aware routing;
- provider failover;
- unified OpenAI-compatible endpoint;
- централизованного переключения между провайдерами.

Правила интеграции:

- OmniRoute не является mandatory dependency;
- backend должен уметь работать без OmniRoute;
- routing decision первично принадлежит policy layer приложения;
- OmniRoute используется как transport/router, а не как замена grounding, validation или case isolation;
- provider diagnostics должны различать direct mode и gateway mode.
