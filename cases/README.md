# Cases Directory

Каталог `cases/` используется как рабочее пространство для конкретных кейсов.

В репозитории должна оставаться только структура и описание формата. Реальные кейсы вида `case_YYYYMMDD_NNN` в git не хранятся и исключаются через `.gitignore`.

## Именование workspace

- `case_YYYYMMDD_NNN`

Примеры:

- `case_20260321_001`
- `case_20260321_002`

## Типовая структура кейса

```text
cases/
  case_YYYYMMDD_NNN/
    raw/
    parsed/
    intake/
    layers/
    viewpoints/
    characterization/
    problems/
    solutions/
    analysis/
    analysis/projections/
    evidence/
    governance/
    dialogue/
    model/
    decisions/
    operation/
    reports/
    quality/
    state/
    versions/
```

## Назначение основных подпапок

- `raw/` — исходные материалы кейса
- `parsed/`, `intake/` — нормализованный вход и parsed artifacts
- `layers/` — слойная модель кейса
- `viewpoints/` — viewpoint artifacts
- `characterization/` — characterization passport, indicator set, cards
- `problems/` — problem portfolio и selected problem
- `solutions/` — solution portfolio, trade-offs, selected solutions
- `analysis/` — внутренние аналитические артефакты и projections
- `evidence/` — evidence graph, refresh artifacts
- `governance/` — logs, ledger, audits, decisions
- `dialogue/` — question queue, dialogue artifacts, session-related exports
- `model/` — case model snapshots and versions
- `decisions/` — ADR и decision artifacts
- `operation/` — runbook, rollback plan
- `reports/` — executive и analytical reports
- `quality/` — quality metrics and acceptance signals
- `state/`, `versions/` — session state и version history

## Правило хранения

- структура каталога остается в репозитории;
- реальные кейсы и их содержимое не коммитятся;
- для примеров и тестов следует использовать `tests/fixtures/`, а не реальные `cases/case_*`.
