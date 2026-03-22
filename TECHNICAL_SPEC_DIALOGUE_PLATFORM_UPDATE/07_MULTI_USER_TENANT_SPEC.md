# Спецификация multi-user, tenant isolation и account layer

## 1. Цель

Добавить в платформу полноценный account/tenant layer, чтобы:

- несколько пользователей могли работать в системе под своими аккаунтами;
- каждый пользователь видел только разрешенные ему workspaces;
- диалоги, кейсы, артефакты и evidence не пересекались между аккаунтами и организациями;
- система была готова к SaaS-модели с billing и ролями доступа.

## 2. Основной принцип

Изоляция должна строиться не только на `workspace_id`, а на связке:

- `user_id`
- `tenant_id` / `organization_id`
- `workspace_id`

Любой доступ к кейсу, диалогу, claims, exports и governance logs должен проходить authorization check.

## 3. Целевая модель аккаунтов

### 3.1. Пользователь

Пользователь имеет:

- регистрацию;
- login/logout;
- восстановление пароля;
- подтверждение email;
- профиль и настройки.

### 3.2. Организация / tenant

Организация объединяет пользователей и их workspaces.

Рекомендуемая модель:

- один пользователь может состоять в нескольких организациях;
- у организации есть owner/admin/member roles;
- workspace принадлежит конкретной организации.

### 3.3. Membership

Связь пользователя и организации должна содержать:

- роль;
- статус приглашения;
- дату вступления;
- optional access policy.

## 4. Роли и права

Минимальный набор ролей:

- `platform_admin`
- `organization_owner`
- `organization_admin`
- `workspace_editor`
- `workspace_viewer`

### 4.1. organization_owner

Может:

- управлять организацией;
- приглашать и удалять пользователей;
- видеть все workspaces организации;
- управлять billing/subscription;
- назначать роли.

### 4.2. organization_admin

Может:

- управлять пользователями в пределах организации;
- создавать и редактировать workspaces;
- просматривать governance и usage.

### 4.3. workspace_editor

Может:

- создавать кейсы;
- вести диалог;
- отвечать на clarification questions;
- запускать re-entry;
- редактировать рабочие данные кейса.

### 4.4. workspace_viewer

Может:

- просматривать кейс, отчеты и evidence;
- не может менять модель.

## 5. Изоляция данных

### 5.1. Tenant isolation

Все tenant-bound сущности должны иметь `organization_id`.

Это относится к:

- `workspaces`
- `artifacts`
- `claims`
- `dialogue_sessions`
- `dialogue_messages`
- `question_queue`
- `validation_runs`
- `governance_events`
- `retrieval_chunks`

### 5.2. Authorization boundary

Запрос считается допустимым только если:

- пользователь аутентифицирован;
- пользователь состоит в организации;
- у пользователя есть право на конкретный workspace;
- policy не запрещает requested action.

### 5.3. Runtime isolation

При формировании dialogue context должны использоваться:

- `organization_id`
- `workspace_id`
- `session_id`

Запрещено:

- cross-tenant retrieval;
- cross-tenant dialogue history;
- cross-tenant evidence links;
- cross-tenant exports.

## 6. Требования к аутентификации

Система должна поддерживать:

- email/password auth;
- email verification;
- password reset;
- session management;
- optional social auth в будущем;
- secure cookie или token-based auth.

## 7. Требования к авторизации

Authorization должен проверяться на уровнях:

- API layer;
- repository/query layer;
- dialogue orchestration layer;
- export/download layer;
- admin/billing layer.

Нельзя полагаться только на скрытие элементов UI.

## 8. Требования к UI

Интерфейс должен поддерживать:

- регистрацию;
- логин;
- выбор активной организации;
- приглашение пользователей;
- список доступных workspaces только в рамках текущей организации;
- экран account settings;
- экран organization settings;
- экран members and roles;
- экран billing/subscription.

## 9. Billing readiness

Даже если billing не включен в первой версии, модель должна быть готова к нему.

Для MVP billing readiness означает placeholder-level readiness, а не обязательную реализацию полной invoice/subscription логики.

Минимальные сущности:

- `subscriptions`
- `plans`
- `usage_records`
- `billing_customers`

## 10. Open SaaS as reference

`open-saas` следует рассматривать как reference source для:

- auth patterns;
- user/session flows;
- organization/account UX;
- billing/subscription scaffolding;
- Railway-oriented SaaS deployment patterns.

`open-saas` не должен рассматриваться как замена domain core этого проекта.

Правильный подход:

- сохранить текущее доменное ядро проекта;
- заимствовать из `open-saas` SaaS shell patterns;
- не переписывать платформу целиком под чужой starter.

## 11. Acceptance criteria

- Пользователь может зарегистрироваться и войти в систему.
- Пользователь видит только свои организации и разрешенные workspaces.
- Данные разных организаций изолированы на уровне БД, API и runtime.
- Диалоги и retrieval не пересекаются между tenant-ами.
- Роли доступа реально влияют на операции, а не только на UI.
- Архитектура готова к billing/subscription layer.
