# Детализация спринтов Dialogue Platform Update

Этот каталог содержит декомпозицию `TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE` в 7 исполнимых спринтов.

Принципы разбиения:

- сохранен порядок внедрения из `05_IMPLEMENTATION_ROADMAP.md`;
- зависимости между БД, tenant layer, retrieval, validation, UI и re-entry не разорваны;
- каждая задача привязана к конкретному результату и проверяется тестами;
- тесты включают unit, integration, contract, security и e2e сценарии там, где это критично.
- SQL/DDl план синхронизирован с требованиями файлов `09-11`, чтобы Sprint 1 не стартовал с устаревшей схемой.

Источники требований:

- `01_MASTER_TECHNICAL_SPEC.md`
- `02_DATABASE_SPEC.md`
- `03_BACKEND_DIALOGUE_ARCHITECTURE.md`
- `04_INTERFACE_AND_UX_SPEC.md`
- `05_IMPLEMENTATION_ROADMAP.md`
- `06_LLM_ROUTING_POLICY_SPEC.md`
- `07_MULTI_USER_TENANT_SPEC.md`
- `08_AUTH_BILLING_AND_TENANT_ER_MODEL.md`
- `09_DIALOGUE_RETRIEVAL_ARCHITECTURE.md`
- `10_DIALOGUE_LAYER_IMPLEMENTATION_PLAN.md`
- `11_DIALOGUE_MODEL_UPDATE_AND_REENTRY_SPEC.md`

Состав:

- `SPRINT_01_FOUNDATION.md` — canonical DB, importer, dual-write, Docker foundation
- `SPRINT_02_AUTH_GRAPH.md` — auth/tenant layer, graph model, projections, embeddings
- `SPRINT_03_DIALOGUE_CORE.md` — dialogue backend MVP, retrieval, routing, quota, provider abstraction
- `SPRINT_04_VALIDATION_UI.md` — FPF validation, dialogue API, single-case UI
- `SPRINT_05_MODEL_UPDATES_REENTRY.md` — clarification flow, model updates, async partial re-entry
- `SPRINT_06_ISOLATION.md` — multi-case and tenant isolation, workspace switching safeguards
- `SPRINT_07_HARDENING_RELEASE.md` — governance, observability, deployment hardening, pilot readiness

Рекомендуемый порядок исполнения:

1. Сначала закрыть Sprint 1-2, потому что без canonical storage и tenant-aware authorization диалоговый слой нельзя безопасно запускать.
2. Затем реализовать Sprint 3-5 как непрерывную цепочку `question -> grounded answer -> clarification -> re-entry`.
3. После этого зафиксировать изоляцию Sprint 6 и довести систему до pilot-ready состояния в Sprint 7.

Уточнения после ревизии плана:

- `ProjectionRegistry` и `MaterializedArtifactIndex` добавлены как deliverables слоя projections до запуска `ReentryPlanner`.
- `SectionContractGuard` включен в roadmap как pre-gate слой для contract-sensitive pipeline runners.
- `GET /api/workspaces/{workspaceId}/version-state` вынесен в API contracts до полной реализации re-entry.
- `embedding lifecycle` перенесен ближе к retrieval sprint, чтобы не опережать первую BM25 реализацию.
- `dual-write` теперь имеет не только критерии входа, но и formal exit review/cutover decision в финальном спринте.
