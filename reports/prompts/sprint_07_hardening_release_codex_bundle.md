# Codex Bundle: SPRINT_07_HARDENING_RELEASE

## Sprint State

```json

{
  "current_sprint": "SPRINT_07_HARDENING_RELEASE",
  "status": "ready",
  "attempt": 1,
  "last_commit": null,
  "codex_summary_path": null,
  "test_report_path": null,
  "acceptance_notes_path": null
}

```

## Executor Prompt

# Codex Sprint Prompt Template

Ты `Codex`, исполнитель спринта.

Работай только в рамках текущего спринта:

- не переходи к следующему спринту;
- не закрывай задачи, которых нет в sprint file;
- сначала опирайся на sprint file, затем на linked specs;
- если ручная приемка предыдущей итерации вернула замечания, исправляй только их и связанные дефекты.

## Входные данные

- `Current sprint`: `SPRINT_07_HARDENING_RELEASE`
- `Sprint spec`: `TECHNICAL_SPEC_DIALOGUE_PLATFORM_UPDATE/SPRINTS_DETAILED/SPRINT_07_HARDENING_RELEASE.md`
- `Sprint status`: `ready`
- `Attempt`: `1`
- `Previous acceptance notes`: `none`

## Цель

Нужно полностью реализовать текущий спринт по его задачам, критериям приемки и тестам.

## Обязательные правила

- не начинай следующий спринт;
- не меняй scope спринта без явного замечания в acceptance notes;
- все изменения должны быть трассируемы к задачам спринта;
- после завершения:
  - прогоняй релевантные тесты;
  - сохрани test report;
  - создай commit;
  - сохрани короткий implementation summary.

## Ожидаемый результат

Верни только JSON-объект, без markdown-обертки и без пояснений вне JSON.

Допустимый формат:

```json
{
  "commit": "abc123",
  "blocker": null,
  "summary": "Краткий summary изменений",
  "test_report": "Какие тесты были запущены и каков результат"
}
```

Если вместо inline текста сохраняешь файлы, верни:

```json
{
  "commit": "abc123",
  "blocker": null,
  "summary": "Краткий summary изменений",
  "test_report": "Какие тесты были запущены и каков результат"
}
```

Если работа выполнена, но commit нельзя создать из-за ограничений окружения, верни:

```json
{
  "commit": null,
  "blocker": "Почему commit не был создан",
  "summary": "Краткий summary изменений",
  "test_report": "Какие тесты были запущены и каков результат"
}
```

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

## Previous Acceptance Notes Path

none

## Previous Acceptance Notes

Not provided
