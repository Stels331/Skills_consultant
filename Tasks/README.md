# План реализации Electronic Consultant (v1 без БД)

## Контекст
План составлен на базе:
- `PROJECT_ARCHITECTURE_v2.md`
- `README.md`
- `kb/ec/*`
- `kb/fpf/*`
- `kb/templates/*`
- `prompts/system/*`
- `prompts/node/*`
- `build/SYSTEM_PROMPT_BUILT.md`
- `scripts/*`
- `agentfiles/agents.yaml`

## Ограничение v1 (обязательное)
- Никаких БД (PostgreSQL, Redis, Mongo и т.д.) в первом релизе.
- Хранение состояния кейса только в файловой структуре (`cases/<workspace_id>/...`).
- Запуск, отладка, тестирование и анализ качества полностью через IDE и локальные CLI-команды.

## Sprint map
1. Sprint 01: Foundation (локальная архитектурная база)
2. Sprint 02: Core Pipeline (ingest/extract/type/model)
3. Sprint 03: Diagnostics (epistemic + problem factory)
4. Sprint 04: Dialogue & Incremental (инкрементальные обновления)
5. Sprint 05: Solutions & Reporting (решения и отчеты)
6. Sprint 06: Hardening & Launch (надежность и запуск пилота)

## Определение готовности проекта v1
- Проект поднимается в IDE одной командой/сценарием.
- Любой кейс проходит полный цикл Analysis + Dialogue без БД.
- Все ключевые артефакты пишутся в файлы и валидируются схемами.
- Есть измеримый отчет успешности пилота (`quality_metrics.json` + итоговый markdown-отчет).
