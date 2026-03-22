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
- `QuestionRouter`
- `RetrievalService`
- `TypedInputClassifier`
- `InputAcceptanceService`
- `PromptBuilder`
- `DialogueOrchestrator`
- `FPFResponseValidator`
- `ClarificationEngine`
- `ModelUpdateEngine`
- `ReentryPlanner`
- `ReentryWorker`
- `ExportMaterializer`
- `LLMProviderAdapter`
- `DeploymentHealthService`
- `QuotaEnforcementService`
- `EmbeddingLifecycleManager`
- `SectionContractGuard`

### 2.2. Обязанности компонентов

`DialogueOrchestrator`:

- принимает пользовательский вопрос;
- получает active workspace and session;
- вызывает `QuestionRouter`;
- направляет `clarification_provided` в `ModelUpdateEngine`, а не в ordinary retrieval path;
- инициирует retrieval только для ordinary Q&A classes;
- вызывает prompt builder;
- получает answer draft от LLM;
- запускает FPF validation;
- сохраняет ответ и связанные события.

`QuestionRouter`:

- классифицирует ввод в:
  - `constraint_query`
  - `problem_query`
  - `solution_query`
  - `report_query`
  - `evidence_query`
  - `clarification_needed`
  - `clarification_provided`;
- возвращает confidence и safe fallback route;
- при низкой уверенности предпочитает `evidence_query` или `clarification_needed`.

`RetrievalService`:

- использует typed graph retrieval как primary path;
- использует text retrieval только как supplementary layer;
- не должен строить answer-grade grounding из text-only retrieval при `0` typed claims;
- извлекает claims и chunks только текущего кейса;
- формирует ranked grounding bundle;
- учитывает signal types: facts, constraints, assumptions, open unknowns, conflicts.
- должен строить grounding bundle с явным разделением:
  - `typed_claims` (primary, verified)
  - `text_fragments` (secondary, supplementary only)
  - `graph_version`
  - `workspace_version`

`TypedInputClassifier`:

- классифицирует свободный пользовательский ввод в промежуточные user-origin types:
  - `user_asserted_fact`
  - `user_declared_constraint`
  - `user_hypothesis`
  - `user_normative_target`.

`InputAcceptanceService`:

- обеспечивает последовательность `classify -> accept_check -> write`;
- проверяет, что ввод:
  - не является вопросом в форме утверждения;
  - не является условной конструкцией, несовместимой с fact-grade записью;
  - не противоречит stable claims без explicit escalation path;
  - достаточно конкретен для typed node;
- при сомнении не пишет node в graph, а возвращает clarification.

`FPFResponseValidator`:

- проверяет epistemic separation;
- проверяет traceability;
- проверяет uncertainty routing;
- проверяет anti-cross-case contamination;
- определяет `pass`, `degrade`, `block`.

`Conflict/duplication handling`:

- true contradictions materialize as `conflict_case`;
- duplicate or adjacent epistemic restatements may materialize as `duplicate_claim_cluster`;
- `duplicate_claim_cluster` носит informational характер и не должен блокировать selection path.

`ClarificationEngine`:

- генерирует уточняющие вопросы;
- пишет их в `question_queue`;
- классифицирует тип недостающего знания;
- объясняет, почему вопрос нужен.

`ModelUpdateEngine`:

- принимает только accepted typed input;
- создает/обновляет claims;
- пишет промежуточные user-origin claims до lawful promotion;
- пишет governance event;
- обновляет projections;
- передает данные в re-entry planner.

`ReentryPlanner`:

- определяет affected stages через artifact lineage traversal:
  - updated node -> dependent projections -> dependent stages -> stale outputs;
- создает async re-entry tasks;
- логирует downgrade/block decisions.

`ReentryWorker`:

- исполняет queued re-entry jobs;
- берет workspace-level lock;
- обновляет reentry status и job state;
- публикует completion/failure events.

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

`QuotaEnforcementService`:

- выполняет preflight quota/budget checks;
- резервирует usage до внешнего provider call;
- закрывает reservation после завершения вызова;
- блокирует запросы при исчерпании лимитов.

`EmbeddingLifecycleManager`:

- создает embedding jobs;
- инвалидирует stale chunks;
- управляет source revisions и active retrieval set.

`StructuredArtifactBoundary`:

- обрабатывает raw LLM output для contract-sensitive stages;
- возвращает `ParseResult`, а не только parsed body;
- ведет field-level provenance через `FieldTrust` и `FieldTrustSource`;
- различает `clean`, `normalized`, `inferred`, `failed`;
- инициирует retry до fallback;
- записывает `parse_metadata` и `artifact_trust_level`.

`SectionContractGuard`:

- выполняет pre-gate contract validation до записи артефакта на диск;
- инициирует repair retry до orchestrator gate;
- снижает количество post-write `BLOCK` из-за structural contract violations.

## 3. Dialogue runtime flow

### 3.1. Ответ на вопрос пользователя

```text
UserQuestion
 -> load active workspace/session
 -> QuestionRouter.classify()
 -> if clarification_provided: ModelUpdateEngine path
 -> retrieve workspace-grounded context
 -> build prompt bundle
 -> run quota preflight
 -> call LLM
 -> validate answer against FPF rules
 -> optional escalation retry loop
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
 -> ReentryPlanner creates async job
 -> worker executes re-entry
 -> updated model becomes active after job completion
 -> pending version becomes published
```

### 3.2.1. Dialogue behavior during async re-entry

Если `reentry_status = in_progress`:

- диалог должен отвечать по `current_published_version`;
- ответ обязан содержать disclaimer о том, что пересчет еще идет;
- `pending_version` не должен silently использоваться как active model.

### 3.3. Embedding lifecycle flow

```text
Claim/Artifact change
 -> create embedding job
 -> mark old chunks stale by revision
 -> worker computes embeddings
 -> active retrieval set switches to fresh revision
```
```

## 4. Prompting model

### 4.1. Prompt composition

Prompt должен состоять из:

- system layer;
- FPF guardrails;
- workspace metadata;
- case summary;
- selected grounding claims;
- selected artifact excerpts, явно помеченные как supplementary, если они не claim-grade;
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

### 4.4. Structured artifact parse boundary

Для stages, где LLM генерирует machine-consumed artifact, backend обязан использовать parse boundary:

```text
raw llm output
 -> write debug raw file
 -> parse into ParseResult
 -> if clean or normalized(key_only): continue
 -> else retry with repair prompt
 -> if retry still inferred/failed: mark degraded and fallback explicitly
 -> write final artifact + parse_metadata + audit entry
```

Минимальные сущности:

- `ParseResult`
- `FieldTrust`
- `FieldTrustSource`
- `parse_metadata`
- `artifact_trust_level`

Правила:

- `key_only` normalization допустим как trusted normalization;
- `value_translated` не дает `decision_grade`;
- `inferred_text` дает максимум `hypothesis`;
- positional inference запрещен как trusted recovery path;
- failed audit entry обязан содержать `raw_output_path`, `missing_fields`, `retry_outcome`.

## 4.5. Model routing policy

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

### 5.2.1. Escalation retry loop

Если validator возвращает `block` по причине недостаточного reasoning quality, policy layer может инициировать escalation retry.

Правила:

- escalation допускается только если routing policy разрешает более сильный tier;
- максимальное число retries: 1 переход на следующий tier;
- repeated retry loops запрещены;
- `premium` failure не триггерит дальнейшую escalation;
- все retries логируются как governance/usage events.

### 5.2.2. Downstream handling of degraded artifacts

Если upstream stage записал `artifact_trust_level=degraded`, downstream не должен считать такой артефакт trusted contract input.

Минимальные правила:

- `contract_validator` обязан hard-fail degraded artifact там, где требуется trusted input;
- `selection_engine` обязан блокироваться на degraded `SolutionPortfolio`;
- degraded artifact допускается только как diagnostic/hypothesis-grade artifact;
- orchestrator получает этот сигнал через обычный contract route.

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

Пользовательский ответ сначала должен иметь промежуточный user-origin type:

- `user_asserted_fact`
- `user_declared_constraint`
- `user_hypothesis`
- `user_normative_target`

Только после acceptance + lawful validation допустимы promotion paths в:

- `source_fact`
- `confirmed_assumption`
- `normative_target`
- `decision_constraint`
- `interpretation`

### 6.3. Acceptance rules

- ответ не должен добавляться в модель без typing
- перед записью обязателен `input_acceptance_check`
- ответ должен иметь source or provenance
- если ответ создает hard constraint, validator должен проверить lawful promotion
- `classify -> accept_check -> write to graph` является обязательной последовательностью

## 7. Re-entry and model refresh

### 7.1. Re-entry targets

Обновление claims может затрагивать:

- `characterization`
- `problem_factory`
- `solution_factory`
- `reporting`

### 7.2. Triggering rules

`ReentryPlanner` не должен опираться только на hardcoded mapping по `node_type`.

Правильный порядок:

- найти projections, которые используют updated node;
- найти stages, зависящие от этих projections;
- найти materialized outputs, которые теперь stale;
- запланировать только затронутые recomputation targets.

### 7.3. Result handling

После re-entry система должна:

- обновить projections;
- обновить active published model version;
- записать governance events;
- показать diff пользователю.

Diff должен строиться из event types:

- `claim_created`
- `claim_updated`
- `claim_promoted`
- `claim_degraded`
- `projection_refreshed`
- `stage_recomputed`

### 7.4. Async execution model

Re-entry считается асинхронной операцией.

Требования:

- API возвращает `reentry_job_id`, а не ждет completion;
- UI показывает `reentry_in_progress`;
- worker исполняет re-entry вне request cycle;
- completion/failure отражается через polling или event update.

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

`POST /api/workspaces/{workspaceId}/reentry/execute` должен быть асинхронным endpoint.

Он обязан:

- создавать `reentry_job`;
- возвращать `reentry_job_id`, а не ждать completion;
- не блокировать request до завершения partial re-entry.

### 8.5.1. Re-entry job API

- `GET /api/workspaces/{workspaceId}/reentry-jobs`
- `GET /api/workspaces/{workspaceId}/reentry-jobs/{jobId}`

### 8.5.2. Workspace version state API

- `GET /api/workspaces/{workspaceId}/model-version-status`

Endpoint должен возвращать:

- `current_published_version`
- `pending_version`
- `reentry_status`
- `affected_stages`
- `reentry_started_at`

### 8.6. Operations API

- `GET /health`
- `GET /ready`

### 8.7. Provider diagnostics API

- `GET /api/llm/providers`
- `GET /api/llm/routing-policy`

### 8.8. Quota API

- `GET /api/account/quota`
- `GET /api/workspaces/{workspaceId}/usage`

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

### 11.4.1. Quota enforcement point

`QuotaEnforcementService` должен вызываться:

- перед `generate_response(...)`
- перед `embed(...)`

Проверка post-factum недостаточна и не допускается как единственный контроль.

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
- OmniRoute остается optional infrastructure layer и не является частью MVP-critical acceptance path.
