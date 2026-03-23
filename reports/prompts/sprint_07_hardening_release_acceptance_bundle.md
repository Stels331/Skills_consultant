# Acceptance Bundle: SPRINT_07_HARDENING_RELEASE

## Sprint State

```json

{
  "current_sprint": "SPRINT_07_HARDENING_RELEASE",
  "status": "awaiting_acceptance",
  "attempt": 1,
  "last_commit": "not-created (local changes ready for manual review)",
  "codex_summary_path": "reports/tests/sprint_07_hardening_release_codex_summary_attempt_1.md",
  "test_report_path": "reports/tests/sprint_07_hardening_release_test_report_attempt_1.md",
  "acceptance_notes_path": null
}

```

## Acceptance Prompt

# Manual Acceptance Prompt

Ты выполняешь ручную приемку текущего спринта.

Проверь только текущий спринт:

- `Current sprint`: `SPRINT_07_HARDENING_RELEASE`
- `Sprint spec`: `TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_07_HARDENING_RELEASE.md`
- `Current status`: `awaiting_acceptance`
- `Attempt`: `1`
- `Codex summary`: `reports/tests/sprint_07_hardening_release_codex_summary_attempt_1.md`
- `Test report`: `reports/tests/sprint_07_hardening_release_test_report_attempt_1.md`

## Что проверить

- Все обязательные задачи спринта действительно выполнены.
- Критерии приемки закрыты без очевидных пробелов.
- Релевантные тесты запущены и отражены в test report.
- Нет явного выхода за scope спринта.
- Все ограничения, blocker'ы и допущения зафиксированы явно.

## Формат результата

Сохрани результат ручной проверки в markdown-файл в `reports/reviews/`.

Структура результата:

```md
# Acceptance Result: SPRINT_07_HARDENING_RELEASE

Decision: accept
```

или

```md
# Acceptance Result: SPRINT_07_HARDENING_RELEASE

Decision: changes requested

Findings:
- ...
- ...
```

После этого зафиксируй решение через `accept-sprint` или `request-changes`.

## Sprint Spec Path

TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_07_HARDENING_RELEASE.md

## Sprint Spec

# Sprint 7. Governance, Hardening, Pilot Readiness

## Цель

Довести платформу до pilot-ready состояния: наблюдаемость, устойчивость, deployment topology, provider diagnostics и release quality gates.

## Ожидаемый результат спринта

- governance trail и operational telemetry покрывают критические потоки;
- deployment в Docker/Railway воспроизводим для API и worker;
- health/readiness отражают реальное состояние зависимостей;
- provider diagnostics и fallback behavior прозрачны;
- собран release checklist для pilot rollout;
- decision-wave явно помечена как post-pilot scope с отдельным readiness gate.

## Задачи

### S7-T1. Завершить governance/event observability

Описание:
- унифицировать события dialogue, validation, promotion/degradation, re-entry, quota и auth security;
- обеспечить correlation ids между API request, LLM call, validator run и governance event;
- подготовить ленты событий для UI и ops.

Критерии приемки:
- по одному correlation id можно собрать всю цепочку запроса;
- ключевые события не теряются между API и worker;
- governance log пригоден для audit и разборов инцидентов.

### S7-T2. Реализовать metrics, logs и health/readiness

Описание:
- метрики latency, validation outcome rate, clarification rate, re-entry duration, quota denials, provider errors;
- структурированные логи;
- readiness учитывает БД, worker queue и критичные внешние зависимости.

Критерии приемки:
- health/readiness различают `alive` и `ready`;
- operational issues диагностируются без чтения сырых stack traces;
- критичные SLO/SLI можно наблюдать из метрик.

### S7-T3. Довести deployment topology для Railway и worker

Описание:
- разнести API и worker процессы;
- зафиксировать env matrix, secrets, queue/backend services;
- проверить startup/shutdown semantics и zero-downtime upgrade assumptions;
- зафиксировать assumption для future decision-wave: scheduled jobs для freshness/assurance recompute будут отдельным operational component.

Критерии приемки:
- API и worker разворачиваются как отдельные сервисы;
- worker получает доступ к очереди и БД без ручных правок;
- rollback deployment documented и воспроизводим.

### S7-T4. Реализовать provider diagnostics и fallback tests

Описание:
- диагностические endpoints или internal checks по configured providers;
- direct mode и gateway mode проверяются одинаковыми контрактами;
- fallback поведение прозрачно для ops и governance trail;
- optional OmniRoute/gateway integration рассматривается как post-pilot extension и не блокирует готовность спринта;
- зафиксировать known limitation для decision-wave: до отдельного gateway rollout decision-specific prompts работают в supported direct mode/routing mode текущей платформы.

Критерии приемки:
- проблемный provider локализуется без ручного дебага кода;
- fallback не нарушает quota policy и routing policy;
- direct/gateway mode можно включить/выключить конфигурацией, если gateway включен в текущий scope;
- отсутствие OmniRoute не блокирует закрытие Sprint 7.

### S7-T5. Собрать pilot readiness пакет

Описание:
- финальный acceptance checklist;
- smoke suite на happy path, degrade path, block path, clarification path, re-entry path и isolation path;
- formal review `dual-write exit criteria` и решение `keep dual-write / cut over / postpone cutover`;
- release notes и known limitations для пилота;
- явно зафиксировать dependency: decision-wave `Sprint 8-10` стартует только после выбранного режима `dual-write` и documented DB source-of-truth policy.

Критерии приемки:
- pilot scope и ограничения сформулированы письменно;
- критический smoke suite зеленый;
- есть решение о go/no-go на основе измеримых критериев.
- есть формальное решение по `dual-write` с зафиксированными метриками и rollback условиями.

### S7-T6. Подготовить readiness contract для decision-wave

Описание:
- определить отдельный go/no-go checklist для `Sprint 8-10`;
- включить known limitations: provider mode, performance assumptions, historical reuse policy, assurance scheduler dependency, data retention/purge gap;
- явно зафиксировать performance baseline assumptions для decision-wave:
  - interactive read path;
  - bounded similarity-search latency;
  - async-only heavy recompute path;
- зафиксировать release-blocking gates для decision-wave regression suites.

Критерии приемки:
- у decision-wave есть отдельный readiness пакет, а не implicit continuation pilot checklist;
- CI gates для assurance floor violations и cross-tenant historical reuse определены как release-blocking;
- dependencies на canonical source-of-truth, provider mode и background scheduling зафиксированы письменно;
- retention/purge policy явно отмечена как post-pilot known gap.

## Тесты спринта

### Для S7-T1

- Correlation trace test: один dialogue request связывается с session event, provider call, validator outcome и governance records.
- Event completeness test: clarification, promotion, degradation и re-entry публикуют обязательные события.
- Audit retrieval test: governance UI/API возвращает события в корректном порядке и с фильтрацией по workspace.

### Для S7-T2

- Metrics smoke test: ключевые счетчики и latency histograms обновляются после dialogue request.
- Readiness degradation test: недоступность БД или очереди переводит `/readiness` в fail state.
- Structured logging test: error log содержит correlation id, workspace id, provider and failure reason.

### Для S7-T3

- Deployment smoke test: API и worker стартуют в целевой topology и подключаются к БД/очереди.
- Restart resilience test: перезапуск worker не теряет незавершенные re-entry jobs.
- Rollback drill test: documented rollback steps реально возвращают систему к рабочему состоянию.

### Для S7-T4

- Provider diagnostics test: endpoint/check отражает статус direct provider и gateway provider отдельно.
- Fallback integration test: сбой primary provider запускает разрешенный fallback без обхода quota checks.
- Config toggling test: переключение direct/gateway mode не требует изменений orchestration code.

### Для S7-T5

- Full pilot smoke suite: пройти happy, degrade, block, clarification, re-entry и isolation сценарии.
- Checklist validation test: каждый пункт acceptance checklist привязан к измеримому тесту или артефакту.
- Go/no-go review test: перед пилотом собран отчет по рискам, open issues и residual limitations.

### Для S7-T6

- Decision-wave readiness checklist test: каждый пункт future-wave checklist привязан к артефакту или regression suite.
- Release gate definition test: assurance floor violation и cross-tenant reuse tests отмечены как blocking gates.

## Codex Summary Path

reports/tests/sprint_07_hardening_release_codex_summary_attempt_1.md

## Codex Summary

# Sprint 07 Hardening Release Summary

- Added operational observability layer in `app/observability/runtime_monitor.py` with counters, latency samples, and structured logs.
- Extended canonical dialogue/runtime stack to emit correlation-linked governance events, metrics, provider diagnostics, and governance feed APIs.
- Added `/readiness`, `/metrics`, `/worker/health`, `/worker/readiness`, and provider/governance ops endpoints in the API surface.
- Added `WorkerRuntimeService` for queue/readiness checks and queued re-entry execution.
- Added `app/release/hardening.py` to produce deployment topology, dual-write cutover review, decision-wave readiness contract, and bundled pilot readiness artifacts.
- Added `tests/test_sprint_07_hardening_release.py` covering correlation trace, metrics/readiness, provider fallback diagnostics, worker runtime, and readiness package generation.

## Test Report Path

reports/tests/sprint_07_hardening_release_test_report_attempt_1.md

## Test Report

# Sprint 07 Hardening Release Test Report

## Commands

```bash
python3 -m py_compile app/api_server.py app/dialogue_api.py app/canonical_db/dialogue_backend.py app/worker_service.py app/observability/runtime_monitor.py app/release/hardening.py tests/test_sprint_07_hardening_release.py
python3 -m unittest tests.test_sprint_07_hardening_release
python3 -m unittest tests.test_sprint_05_model_updates_reentry tests.test_sprint_06_isolation tests.test_sprint_07_hardening_release
```

## Result

- `tests.test_sprint_07_hardening_release`: `5 tests`, `OK`
- Regression `tests.test_sprint_05_model_updates_reentry tests.test_sprint_06_isolation tests.test_sprint_07_hardening_release`: `21 tests`, `OK`

## Commit / Diff Context

not-created (local changes ready for manual review)

## Diff Hint

No commit recorded yet

## Acceptance Checklist

- Все обязательные задачи спринта закрыты.

- Критерии приемки спринта выполнены.

- Релевантные тесты запущены и результаты зафиксированы.

- Нет очевидного scope creep вне спринта.

- Оставшиеся ограничения и blockers описаны явно.
