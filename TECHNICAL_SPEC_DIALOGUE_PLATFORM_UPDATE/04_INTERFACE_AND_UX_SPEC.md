# Спецификация интерфейсов и UX

## 1. Цель интерфейса

Интерфейс должен поддерживать не обычный чат, а аналитический диалог поверх конкретного кейса. Пользователь должен всегда понимать:

- по какому кейсу он сейчас работает;
- на чем основан ответ системы;
- что в ответе является фактом, а что выводом;
- какие вопросы еще не закрыты;
- как пользовательский ответ изменит модель.

## 2. Основные UX-принципы

- `case-first`, а не `chat-first`
- явная видимость активного кейса
- прозрачность grounding и confidence
- явная маркировка неопределенности
- controlled clarification вместо свободной догадки
- отсутствие смешения истории разных кейсов

## 3. Основные экраны

### 3.0. Auth and organization screens

Функции:

- регистрация;
- login/logout;
- password reset;
- account settings;
- organization switcher;
- members and roles management;
- billing-ready organization settings.

### 3.1. Case List / Workspace Selector

Функции:

- список кейсов;
- поиск и фильтрация;
- создание нового кейса;
- отображение статуса кейса;
- переход к конкретному workspace.

Каждый элемент списка должен показывать:

- название кейса;
- `workspace_id`;
- текущую стадию;
- дату последнего обновления;
- количество unresolved questions;
- статус модели: `pass/degrade/block`.

### 3.2. Case Overview

Функции:

- краткая сводка по кейсу;
- выбранная проблема;
- выбранные решения;
- ключевые ограничения;
- количество active claims / conflicts / open questions.

### 3.3. Dialogue Console

Центральный экран работы с кейсом.

Содержит:

- историю сообщений текущей сессии;
- поле ввода вопроса;
- режим ответа;
- маркеры FPF-status;
- переход к evidence/claims.

### 3.4. Evidence / Claims Panel

Отображает:

- claims, использованные в последнем ответе;
- artifact references;
- epistemic status;
- conflicts;
- traceability links.

### 3.5. Open Questions Panel

Показывает:

- unresolved unknowns;
- очередь уточняющих вопросов;
- причину появления вопроса;
- предполагаемое влияние на модель.

### 3.6. Model Changes Panel

Показывает:

- какие claims будут добавлены/изменены;
- какие стадии будут пересчитаны;
- какие решения/ограничения могут измениться;
- diff между предыдущей и текущей моделью.

### 3.7. Governance Log Panel

Показывает:

- dialogue events;
- validation events;
- promotion/degradation events;
- re-entry events.

## 4. Целевая компоновка основного экрана

### 4.1. Левая колонка

- organization switcher;
- список кейсов;
- переключатель active workspace;
- список сессий текущего кейса.

### 4.2. Центральная область

- dialogue timeline;
- composer для вопроса;
- answer cards;
- system clarification cards.

### 4.3. Правая колонка

- grounding panel;
- used claims;
- unresolved unknowns;
- impact preview;
- governance summary.

### 4.4. Верхняя плашка

Обязательно показывает:

- активную организацию;
- название кейса;
- `workspace_id`;
- current stage;
- model status;
- last updated;
- indicator `You are working in case X`.

## 5. Типы сообщений в диалоге

### 5.1. User question

Свободный вопрос пользователя по активному кейсу.

### 5.2. Assistant grounded answer

Ответ с:

- confidence marker;
- epistemic status;
- FPF validation status;
- ссылками на grounding.

### 5.3. Clarification request

Отдельная карточка вопроса от системы с объяснением:

- зачем нужен вопрос;
- что именно не хватает;
- какая часть модели зависит от ответа.

### 5.4. Model update result

Карточка после принятия clarification answer:

- что обновилось;
- какие stages rechecked;
- изменились ли conclusions/recommendations.

## 6. Требования к ответу в UI

Каждый ответ ассистента должен показывать:

- основной текст ответа;
- `epistemic_status`
- `confidence_score`
- `FPF: pass/degrade/block`
- `used claims`
- `used artifacts`
- `open unknowns`

Если answer outcome = `block`, UI не должен показывать ответ как нормальный completed answer. Вместо этого должен отображаться:

- reason of block;
- safe fallback;
- clarification path.

## 7. Clarification UX

### 7.1. Форма ответа

Пользователь должен отвечать не только текстом, но и через типизацию:

- тип ответа;
- текст ответа;
- источник/основание;
- optional confidence;
- optional note.

### 7.2. Impact preview

Перед сохранением ответа UI должен показывать:

- какие claims будут добавлены;
- какой epistemic type будет создан;
- какие stages потенциально затронутся;
- есть ли риск block/degrade.

### 7.3. Confirmation flow

После сохранения:

- показывается progress re-entry;
- потом diff updated model;
- затем ответ в диалоге помечается как refreshed.

## 8. Multi-case isolation в UI

### 8.1. Базовые правила

- один активный кейс на один видимый dialogue view
- отдельная история сообщений для каждого кейса
- при переключении кейса history pane полностью перерисовывается
- composer должен быть привязан к active workspace

### 8.2. UX safeguards

- цветовая/текстовая плашка активного кейса
- confirmation при отправке сообщения, если кейс только что переключен
- нулевая видимость чужих claims/messages в новом кейсе

### 8.3. Ошибки, которые UI должен предотвращать

- вопрос отправлен не в тот кейс;
- визуально остался ответ старого кейса после переключения;
- grounding panel показывает артефакты другого кейса;
- open questions смешаны между кейсами.

## 8.4. Multi-user and tenant isolation в UI

- пользователь после login видит только доступные ему организации;
- после выбора организации UI показывает только workspaces этой организации;
- при переключении организации должны сбрасываться case list, dialogue state и evidence panel;
- UI не должен отображать чужие workspaces даже временно во время загрузки.

## 9. Режимы ответа

UI должен поддерживать три режима запроса:

- `Спросить по кейсу`
- `Пояснить на основе модели`
- `Уточнить и обновить модель`

Это позволяет отделить:

- обычный вопрос;
- запрос на explainability;
- controlled clarification/update flow.

## 10. Состояния интерфейса

Минимальные состояния:

- `empty`
- `loading_case`
- `ready`
- `waiting_for_answer`
- `needs_clarification`
- `reentry_in_progress`
- `degraded_answer`
- `blocked_answer`
- `error`

## 11. Компонентная модель фронтенда

Рекомендуемая структура:

- `AuthShell`
- `OrganizationSwitcher`
- `MembersManagementPage`
- `AccountSettingsPage`
- `WorkspaceList`
- `WorkspaceHeader`
- `CaseOverviewCard`
- `DialogueTimeline`
- `MessageComposer`
- `AssistantAnswerCard`
- `ClarificationCard`
- `GroundingPanel`
- `ClaimsList`
- `OpenQuestionsList`
- `ImpactPreviewPanel`
- `GovernanceEventsPanel`

## 12. Accessibility and usability

- все критические статусы должны дублироваться текстом, а не только цветом;
- длинные ответы должны быть сворачиваемыми;
- grounding panel должен поддерживать быстрый переход к claim/artifact;
- переключение кейса должно быть быстрым и визуально однозначным.
- переключение организации должно быть еще более явно маркировано, чем переключение кейса.
