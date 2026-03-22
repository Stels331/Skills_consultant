# ER-модель auth, tenant и billing слоя

## 1. Цель

Зафиксировать точную модель данных для:

- пользователей;
- организаций;
- memberships и ролей;
- прав доступа к workspace;
- billing/subscription;
- связи account layer с case/dialogue/claim model.

Примечание по scope:

- auth/tenant model входит в core platform architecture;
- billing model на текущем этапе фиксируется как placeholder/readiness layer;
- детальная invoice lifecycle implementation не является частью MVP-critical scope.

## 2. Базовые сущности

### 2.1. users

Назначение:

- учетная запись пользователя платформы.

Поля:

- `id`
- `email`
- `password_hash`
- `display_name`
- `status`
- `email_verified_at`
- `last_login_at`
- `created_at`
- `updated_at`

### 2.2. user_profiles

Назначение:

- расширенные настройки и предпочтения пользователя.

Поля:

- `id`
- `user_id`
- `timezone`
- `locale`
- `avatar_url`
- `preferences_jsonb`
- `created_at`
- `updated_at`

### 2.3. organizations

Назначение:

- tenant boundary для workspaces и данных.

Поля:

- `id`
- `name`
- `slug`
- `owner_user_id`
- `status`
- `metadata_jsonb`
- `created_at`
- `updated_at`

### 2.4. memberships

Назначение:

- связь пользователя и организации.

Поля:

- `id`
- `organization_id`
- `user_id`
- `role`
- `status`
- `invited_by_user_id`
- `joined_at`
- `created_at`
- `updated_at`

### 2.5. workspace_permissions

Назначение:

- дополнительные права на конкретный workspace, если они отличаются от organization role.

Поля:

- `id`
- `workspace_id`
- `user_id`
- `permission_level`
- `granted_by_user_id`
- `created_at`
- `updated_at`

## 3. Workspace-related сущности

### 3.1. workspaces

Расширенная модель:

- `id`
- `organization_id`
- `workspace_key`
- `title`
- `case_type`
- `status`
- `current_stage`
- `active_model_version`
- `created_by_user_id`
- `metadata_jsonb`
- `created_at`
- `updated_at`

### 3.2. dialogue_sessions

Должны быть привязаны к:

- `organization_id`
- `workspace_id`
- `created_by_user_id`

### 3.3. dialogue_messages

Должны быть привязаны к:

- `organization_id`
- `workspace_id`
- `session_id`
- `actor_user_id` при user messages

### 3.4. claims / artifacts / governance_events

Все case-bound сущности должны включать:

- `organization_id`
- `workspace_id`

## 4. Billing сущности

### 4.1. plans

Назначение:

- описание тарифов.

Поля:

- `id`
- `plan_key`
- `name`
- `status`
- `monthly_price`
- `yearly_price`
- `currency`
- `limits_jsonb`
- `features_jsonb`
- `created_at`
- `updated_at`

### 4.2. subscriptions

Назначение:

- активная подписка организации.

Поля:

- `id`
- `organization_id`
- `plan_id`
- `status`
- `billing_customer_id`
- `billing_subscription_ref`
- `period_start_at`
- `period_end_at`
- `cancel_at_period_end`
- `created_at`
- `updated_at`

### 4.3. billing_customers

Назначение:

- маппинг организации на внешнюю billing-систему.

Поля:

- `id`
- `organization_id`
- `provider`
- `provider_customer_ref`
- `created_at`
- `updated_at`

### 4.4. usage_records

Назначение:

- учет потребления ресурсов.

Поля:

- `id`
- `organization_id`
- `workspace_id`
- `user_id`
- `metric_key`
- `quantity`
- `period_key`
- `metadata_jsonb`
- `created_at`

### 4.5. invoices

`invoices` остаются optional placeholder entity для post-MVP billing expansion.

Для первой версии достаточно зафиксировать:

- `id`
- `organization_id`
- `subscription_id`
- `provider_invoice_ref`
- `status`
- `created_at`

## 5. Связи между сущностями

### 5.1. User to Organization

- `users 1..N memberships`
- `organizations 1..N memberships`

Один пользователь может быть в нескольких организациях. Одна организация может иметь много пользователей.

### 5.2. Organization to Workspace

- `organizations 1..N workspaces`

Workspace обязан принадлежать одной организации.

### 5.3. Workspace to Dialogue

- `workspaces 1..N dialogue_sessions`
- `dialogue_sessions 1..N dialogue_messages`

### 5.4. Organization to Billing

- `organizations 1..N subscriptions`
- `organizations 1..N billing_customers`
- `organizations 1..N usage_records`

### 5.5. Subscription to Plan

- `plans 1..N subscriptions`

## 6. Рекомендуемые ключи и ограничения

### 6.1. Уникальности

- `users.email` unique
- `organizations.slug` unique
- `memberships (organization_id, user_id)` unique
- `workspaces (organization_id, workspace_key)` unique
- `workspace_permissions (workspace_id, user_id)` unique
- `plans.plan_key` unique

### 6.2. Обязательные foreign keys

- `organizations.owner_user_id -> users.id`
- `memberships.organization_id -> organizations.id`
- `memberships.user_id -> users.id`
- `workspaces.organization_id -> organizations.id`
- `workspaces.created_by_user_id -> users.id`
- `workspace_permissions.workspace_id -> workspaces.id`
- `workspace_permissions.user_id -> users.id`
- `subscriptions.organization_id -> organizations.id`
- `subscriptions.plan_id -> plans.id`
- `billing_customers.organization_id -> organizations.id`

### 6.3. Status enums

Рекомендуемые статусы:

- users: `active`, `invited`, `disabled`
- organizations: `active`, `suspended`, `archived`
- memberships: `invited`, `active`, `revoked`
- subscriptions: `trialing`, `active`, `past_due`, `canceled`, `expired`

## 7. Authorization model

### 7.1. Organization-level authorization

Базовый доступ определяется membership role.

### 7.2. Workspace-level authorization

Если задан `workspace_permissions`, он уточняет доступ внутри организации.

Пример:

- organization admin видит все workspaces
- обычный member видит только явно разрешенные workspaces

### 7.3. Authorization resolution order

```text
is_platform_admin?
 -> yes: allow
 -> no:
    is_org_member?
    -> no: deny
    -> yes:
       apply org role
       apply workspace-specific overrides
       evaluate requested action
```

## 8. Billing and feature gating

Feature gating должно строиться по связке:

- `organization.plan`
- `subscription.status`
- `usage_records`
- optional `organization overrides`

Примеры gated capabilities:

- количество workspaces;
- количество активных пользователей;
- доступ к premium models;
- доступ к OmniRoute routing;
- доступ к advanced reporting;
- retention period для governance logs.

## 9. Связь с dialogue и LLM routing

Billing и plan могут влиять на:

- allowed routing tier;
- доступность `premium` моделей;
- разрешение на gateway mode / OmniRoute;
- лимиты на количество dialogue turns;
- лимиты на embeddings / retrieval volume.

Но billing не должен нарушать:

- tenant isolation;
- FPF validation;
- grounded answer policy.

## 10. SQL skeleton

```sql
create table users (
  id uuid primary key,
  email text unique not null,
  password_hash text not null,
  display_name text not null,
  status text not null,
  email_verified_at timestamptz,
  last_login_at timestamptz,
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
  invited_by_user_id uuid references users(id),
  joined_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, user_id)
);

create table workspace_permissions (
  id uuid primary key,
  workspace_id uuid not null references workspaces(id),
  user_id uuid not null references users(id),
  permission_level text not null,
  granted_by_user_id uuid references users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, user_id)
);

create table plans (
  id uuid primary key,
  plan_key text unique not null,
  name text not null,
  status text not null,
  monthly_price numeric(12,2),
  yearly_price numeric(12,2),
  currency text not null,
  limits_jsonb jsonb not null default '{}'::jsonb,
  features_jsonb jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table subscriptions (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  plan_id uuid not null references plans(id),
  status text not null,
  billing_customer_id text,
  billing_subscription_ref text,
  period_start_at timestamptz,
  period_end_at timestamptz,
  cancel_at_period_end boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table usage_records (
  id uuid primary key,
  organization_id uuid not null references organizations(id),
  workspace_id uuid references workspaces(id),
  user_id uuid references users(id),
  metric_key text not null,
  quantity numeric(18,4) not null,
  period_key text not null,
  metadata_jsonb jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
```

## 11. Acceptance criteria

- У account layer есть формальная ER-модель.
- Workspace ownership связан с organization boundary.
- Memberships и роли позволяют построить tenant-aware authorization.
- Billing layer связан с organization, а не с отдельным workspace.
- Plan/usage model можно использовать для feature gating LLM routing и workspace limits.
