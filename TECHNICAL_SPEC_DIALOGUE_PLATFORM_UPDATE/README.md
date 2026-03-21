# Technical Spec Package: Dialogue Platform Update

Этот каталог содержит полный пакет технических спецификаций для следующего обновления `Electronic Consultant v3`: перехода от файлового pipeline к централизованной FPF-aware платформе с диалогом поверх case model, multi-case isolation, audit-ready governance и централизованной базой данных.

Состав пакета:

- `01_MASTER_TECHNICAL_SPEC.md` — полное ТЗ верхнего уровня: идея, цели, scope, требования, архитектура, сценарии и критерии приемки.
- `02_DATABASE_SPEC.md` — целевая модель хранения данных, PostgreSQL schema, event model, retrieval layer и стратегия миграции.
- `03_BACKEND_DIALOGUE_ARCHITECTURE.md` — backend-архитектура диалогового слоя, orchestration, retrieval, FPF-validation, re-entry и API.
- `04_INTERFACE_AND_UX_SPEC.md` — спецификация интерфейсов, UX-сценариев, экранов, состояний и multi-case isolation в UI.
- `05_IMPLEMENTATION_ROADMAP.md` — этапы внедрения, спринты, зависимости, риски и definition of done.
- `06_LLM_ROUTING_POLICY_SPEC.md` — policy выбора моделей, routing tiers, budget profiles, fallback и optional OmniRoute integration.
- `07_MULTI_USER_TENANT_SPEC.md` — регистрация, аккаунты, организации, роли, tenant isolation, billing readiness и позиционирование `open-saas` как reference layer.
- `08_AUTH_BILLING_AND_TENANT_ER_MODEL.md` — точная ER-модель users/organizations/memberships/workspace permissions/subscriptions и их связь с case platform.

Назначение обновления:

- перевести проект от файлового-only режима к `database-first + file-exports`;
- сделать диалог с LLM управляемым и case-grounded;
- исключить пересечение контекстов между кейсами;
- привязать ответы модели к evidence и FPF-проверкам;
- дать пользователю возможность достраивать модель кейса через controlled clarification flow.
- зафиксировать contract-first parse boundary для LLM-generated artifacts с `parse_quality`, `FieldTrust`, retry-before-fallback и degraded-artifact blocking.
