# Sprint 02 Codex Summary

- Добавлена ревизия БД `20260322_0002_auth_graph` с таблицами `user_profiles`, `auth_sessions`, `projection_snapshots`, `materialized_artifact_index_entries`.
- Расширены доменные модели и sqlite-репозитории для profile/session/membership, claim version history, projection snapshots и materialized artifact index.
- Реализованы сервисы `AuthService`, `OrganizationService`, `TenantAuthorizationService`, `ClaimGraphService`, `ProjectionRegistry`, `ProjectionService`, `MaterializedArtifactIndex`.
- Добавлен интеграционный тестовый набор `tests/test_sprint_02_auth_graph.py` под Sprint 2.
- Актуализированы foundation-тесты под наличие второй alembic revision без поломки Sprint 1.
