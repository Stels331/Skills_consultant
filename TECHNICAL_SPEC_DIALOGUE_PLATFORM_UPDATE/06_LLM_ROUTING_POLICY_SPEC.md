# Спецификация LLM routing policy

## 1. Цель

Определить, как платформа выбирает LLM model/provider для разных типов задач так, чтобы:

- не переплачивать за рутинные операции;
- использовать более сильные модели там, где цена ошибки выше;
- поддерживать fallback и provider switching;
- не нарушать FPF validation, grounding и case isolation;
- опционально использовать OmniRoute как centralized gateway.

## 2. Основной принцип

Routing policy относится только к выбору transport/model layer. Она не управляет:

- case grounding;
- retrieval scope;
- FPF validation;
- governance logging;
- multi-case isolation.

Иными словами, routing policy может выбрать модель, но не может ослабить требования к качеству и безопасности ответа.

## 3. Режимы подключения

Поддерживаются два режима:

### 3.1. Direct mode

Backend обращается напрямую к провайдерам:

- OpenAI
- Anthropic
- Google
- OpenRouter
- локальный provider

### 3.2. Gateway mode

Backend обращается к единому gateway endpoint, например OmniRoute, который уже маршрутизирует запрос к целевой модели.

Требование:

- direct mode и gateway mode должны быть взаимозаменяемыми через конфигурацию.

## 4. Routing tiers

Минимальный набор tiers:

- `cheap`
- `balanced`
- `premium`

### 4.1. Cheap

Назначение:

- дешевые, быстрые, низкорисковые операции.

Подходит для:

- генерации clarification questions;
- rewrite/cleanup without semantic invention;
- simple extraction;
- lightweight classification;
- summary of already grounded claims;
- service/system helper tasks.

Не подходит для:

- final recommendations;
- conflict-heavy reasoning;
- high-stakes synthesis;
- key reporting artifacts.

### 4.2. Balanced

Назначение:

- основной рабочий tier для большинства диалоговых операций.

Подходит для:

- grounded Q&A по кейсу;
- explainability answers;
- viewpoint follow-up questions;
- moderate synthesis;
- structured problem/solution discussion;
- обычные clarification-dependent ответы.

### 4.3. Premium

Назначение:

- дорогие, но более сильные модели для high-stakes reasoning.

Подходит для:

- final reporting synthesis;
- recommendation answers с высокой ценой ошибки;
- conflict resolution при высокой сложности;
- mixed-case reasoning;
- selection/trade-off narratives;
- ответы, которые могут существенно повлиять на decision path.

## 5. Routing by task type

### 5.1. Dialogue question classes

Каждый вопрос должен быть отнесен к одному из классов:

- `clarification_generation`
- `fact_extraction`
- `grounded_case_qa`
- `explainability`
- `problem_analysis`
- `solution_analysis`
- `conflict_resolution`
- `selection_support`
- `report_synthesis`
- `artifact_rewrite`

### 5.2. Recommended tier mapping

- `clarification_generation` -> `cheap`
- `fact_extraction` -> `cheap` или `balanced`
- `grounded_case_qa` -> `balanced`
- `explainability` -> `balanced`
- `problem_analysis` -> `balanced`
- `solution_analysis` -> `balanced`
- `conflict_resolution` -> `premium`
- `selection_support` -> `premium`
- `report_synthesis` -> `premium`
- `artifact_rewrite` -> `cheap`

## 6. Routing by workflow stage

### 6.1. Intake

Рекомендуемый tier:

- `cheap` для extraction/classification
- `balanced` для ambiguous structuring

### 6.2. Layers / Viewpoints

Рекомендуемый tier:

- `balanced`

### 6.3. Characterization

Рекомендуемый tier:

- `balanced`
- `premium`, если высокий конфликт или критичные decision constraints

### 6.4. Problem Factory

Рекомендуемый tier:

- `balanced`
- `premium` при mixed-case и сложном problem framing

### 6.5. Solution Factory / Selection

Рекомендуемый tier:

- `balanced` для промежуточных сравнений
- `premium` для final recommendation, trade-off resolution и selection rationale

### 6.6. Reporting

Рекомендуемый tier:

- `premium` для executive summary и analytical full report

## 7. Routing by risk level

Помимо task/stage, policy должна учитывать риск:

- `low_risk`
- `medium_risk`
- `high_risk`

### 7.1. Примеры low risk

- переформулировка already grounded answer;
- генерация уточняющего вопроса;
- легкая категоризация.

### 7.2. Примеры medium risk

- ответ по кейсу с достаточным evidence;
- объяснение existing recommendation;
- обычная problem discussion.

### 7.3. Примеры high risk

- выбор решения;
- ответы, влияющие на constraints;
- high-stakes reporting;
- conflict-heavy cross-view synthesis.

Rule:

- если risk = `high_risk`, tier не может быть ниже `balanced`;
- для `selection_support` и `report_synthesis` по умолчанию используется `premium`.

## 8. Routing by budget profile

Система должна поддерживать budget profiles:

- `economy`
- `standard`
- `premium`
- `strict_cap`

### 8.1. Economy

- cheap by default
- balanced only for medium/high risk
- premium only by explicit policy or operator override

### 8.2. Standard

- balanced by default
- cheap for helper tasks
- premium for high-risk reasoning

### 8.3. Premium

- balanced/premium by default
- cheap только для service tasks

### 8.4. Strict cap

- cheap максимально часто
- balanced только при validator-driven escalation
- premium только по explicit approval/policy

## 9. Escalation and fallback

### 9.1. Escalation rules

Запрос должен быть эскалирован на более дорогой tier, если:

- answer blocked by validator due to insufficient reasoning quality;
- ambiguity remains after balanced attempt;
- high-stakes answer requested;
- mixed-case complexity detected;
- unresolved conflicts exceed threshold.

### 9.2. Fallback rules

Fallback на альтернативный provider/model допускается, если:

- timeout;
- rate limit;
- provider unavailable;
- gateway routing failure.

Fallback не допускается, если:

- новая модель не соответствует minimum required tier;
- новая модель не проходит policy constraints по risk class.

## 10. OmniRoute policy

### 10.1. Когда использовать OmniRoute

OmniRoute целесообразен, если нужны:

- unified endpoint;
- provider failover;
- cost-aware routing;
- централизованное управление несколькими моделями.

### 10.2. Когда не использовать OmniRoute

Не делать OmniRoute обязательным, если:

- у системы только один-два провайдера;
- нет реальной потребности в automated routing;
- operational complexity gateway превышает выигрыш.

### 10.3. OmniRoute integration rules

- приложение определяет routing tier;
- приложение определяет risk class;
- приложение определяет, допускается ли gateway usage;
- OmniRoute получает уже выбранный policy envelope, а не сам решает бизнес-логику.

## 11. Policy envelope

Перед вызовом provider/gateway backend должен сформировать структуру:

```json
{
  "workspace_id": "case_20260321_001",
  "task_class": "grounded_case_qa",
  "workflow_stage": "dialogue",
  "risk_class": "medium_risk",
  "budget_profile": "standard",
  "required_tier": "balanced",
  "allow_gateway": true,
  "allow_fallback": true,
  "requires_strict_json": true
}
```

## 12. Policy decision examples

### 12.1. Пользователь спрашивает: "Какие основные ограничения в кейсе?"

- task class: `grounded_case_qa`
- risk: `medium_risk`
- tier: `balanced`

### 12.2. Система формирует уточняющий вопрос

- task class: `clarification_generation`
- risk: `low_risk`
- tier: `cheap`

### 12.3. Система пишет финальный executive summary

- task class: `report_synthesis`
- risk: `high_risk`
- tier: `premium`

### 12.4. Система выбирает между конфликтующими решениями

- task class: `selection_support`
- risk: `high_risk`
- tier: `premium`

## 13. Ограничения policy

- routing tier не может понижать требования FPF validation;
- provider selection не может открывать cross-case retrieval;
- fallback не может использовать модель ниже минимально допустимого tier;
- gateway mode не может обходить internal policy envelope.

## 14. Рекомендуемые runtime variables

- `LLM_GATEWAY_MODE=direct|omniroute`
- `LLM_ROUTING_DEFAULT_TIER=balanced`
- `LLM_BUDGET_PROFILE=standard`
- `LLM_ALLOW_PREMIUM=true|false`
- `LLM_ALLOW_FALLBACK=true|false`
- `OMNIROUTE_BASE_URL`
- `OMNIROUTE_API_KEY`

## 15. Acceptance criteria

- Для каждого task class есть определенный default tier.
- Система умеет выбирать tier по task/risk/budget policy.
- Direct mode и OmniRoute mode работают через один и тот же policy layer.
- Fallback не нарушает minimum tier constraints.
- Validator может инициировать escalation на более сильную модель.
- Routing policy не ломает FPF checks и case isolation.
