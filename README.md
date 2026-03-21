# Electronic Consultant v3

`Electronic Consultant v3` — это локальный Python-проект для структурированного разбора сложных бизнес-, операционных, управленческих и архитектурных кейсов. Система принимает неструктурированное описание ситуации, прогоняет его через FPF-aware pipeline и выпускает набор артефактов для принятия решений: от нормализованного кейса и evidence graph до problem portfolio, solution portfolio, ADR, runbook и итоговой отчетности.

Проект ушел от ранней версии "workspace manager + валидаторы" и стал полноценным аналитическим конвейером с оркестрацией стадий, контрактами артефактов, evidence-based governance и защитой от типовых ошибок вроде cross-case contamination, unlawful promotion гипотез в constraints и смешения стратегического, операционного и market-контекстов.

## Задача проекта

Система решает не задачу "суммаризации текста", а задачу воспроизводимого анализа кейса:

- выделить факты, интерпретации, гипотезы, ограничения и целевые нормативы;
- разложить ситуацию по системным слоям и viewpoints;
- отделить корневую проблему от симптомов;
- сформировать портфель альтернатив вместо одной преждевременной "лучшей идеи";
- провести controlled selection по ограничениям, trade-offs и acceptance criteria;
- сохранить трассировку от исходного текста до рекомендаций и управленческого решения.

Итоговая ценность для пользователя: на выходе появляется не ответ модели в свободной форме, а проверяемый пакет управленческих артефактов, который можно использовать для обсуждения, пилота, архитектурного проектирования и аудита.

## Workflow

Базовый пользовательский сценарий:

1. Пользователь подает кейс в виде `.md`, `.txt`, `.docx`, `.doc` или `.rtf`.
2. Для кейса создается отдельный workspace в `cases/case_YYYYMMDD_NNN`.
3. Pipeline поэтапно строит артефакты анализа.
4. Оркестратор проверяет stage gates, контракты, semantic/assurance сигналы и freshness.
5. Система сохраняет evidence, governance logs и итоговые отчеты.

Фактическая последовательность стадий:

1. `intake`  
   Нормализация исходного описания, разбор входа и подготовка структурированного представления кейса.
2. `layers`  
   Построение многослойной модели: бизнес-модель, требования, функциональная модель, allocation/responsibility model.
3. `viewpoints`  
   Анализ через отдельные перспективы: `strategist`, `analyst`, `operator`, `architect`, `critic`, `client`, а также `market` для market-heavy кейсов.
4. `characterization`  
   Формирование паспорта кейса, indicator set, parity plan и characteristic cards.
5. `problem_factory`  
   Построение problem portfolio, выбор ключевой проблемы и фиксация comparison acceptance criteria.
6. `solution_factory` / `solution_portfolio`  
   Генерация альтернатив, parity/trade-off анализ, фиксация конфликтов и выбор рекомендованных решений.
7. `reporting`  
   Формирование `Executive_Summary.md`, `Analytical_Full_Report.md` и машинно-читаемых summary/projection артефактов.

Дополнительные governance- и operations-результаты:

- `evidence/evidence_graph.json` и `.md`;
- `governance/epistemic_ledger.jsonl`, `decision_log.jsonl`, `stage_events.jsonl`, `contract_audit.jsonl`;
- `decisions/ADR-001.md`;
- `operation/Runbook.md` и `operation/RollbackPlan.md`.

## Архитектурные решения

### 1. Workspace-first storage

Проект работает без обязательной централизованной БД. Каждый кейс живет в собственном каталоге внутри `cases/`, что дает:

- изоляцию кейсов и защиту от cross-case contamination;
- воспроизводимость прогонов;
- простой аудит артефактов и промежуточных состояний;
- управляемый incremental recheck отдельных стадий.

### 2. FPF-aware epistemic model

Система различает типы утверждений и не позволяет смешивать:

- `source_fact`;
- `derived_metric`;
- `normative_target`;
- `interpretation`;
- `hypothesis`;
- `assumption` / `confirmed_assumption`;
- `decision_constraint`;
- `recommendation`;
- `conflict_case`.

Это принципиально важно для lawful promotion: гипотеза не должна автоматически становиться жестким ограничением, а selection должен опираться на traceable и валидированные claims.

### 3. Contract-first pipeline

У каждой стадии есть ожидаемые входы и выходы. Валидаторы и оркестратор проверяют:

- schema compliance;
- artifact contracts;
- stage input contracts;
- semantic consistency;
- assurance/freshness policy;
- validation matrix outcome.

Результат каждой стадии маршрутизируется как `pass`, `degrade` или `block`.

### 4. Orchestrated stage gating

Оркестрация собрана вокруг `StageOrchestrator`, который:

- определяет ключевой артефакт стадии;
- запускает contract и semantic проверки;
- собирает evidence graph;
- применяет transition logic и state machine;
- пишет decision log и stage events;
- поддерживает re-entry/recheck сценарии.

### 5. Evidence and auditability by design

Проект целенаправленно сделан audit-ready. Для этого:

- evidence graph хранит связи между claims, источниками и выводами;
- epistemic ledger фиксирует события создания, продвижения, деградации и валидации claims;
- governance-логи сохраняются append-only;
- projections позволяют строить lightweight views без потери трассируемости.

### 6. Rule-driven + LLM-assisted approach

LLM используется как усилитель отдельных стадий, но не как единственный источник логики. Архитектура сочетает:

- файловую модель workspace;
- Python-оркестрацию;
- формальные схемы и контракты;
- FPF-валидаторы и conflict detection;
- LLM modes для генерации аналитических артефактов.

## Основные блоки проекта

### Ядро исполнения

- `run_case.py` — полный end-to-end запуск кейса.
- `scripts/run_stage.py` — ручной прогон stage gate для выбранной стадии.
- `scripts/run_incremental.py` — инкрементальная перепроверка затронутых стадий.

### Управление workspace и состоянием

- `app/state/workspace_manager.py`
- `app/state/state_machine.py`
- `scripts/workspace_cli.py`

### Оркестрация и маршрутизация

- `app/router/orchestrator.py`
- `app/router/phase_controller.py`
- `app/router/transition_logic.py`
- `app/router/context_budget_enforcer.py`

### Pipeline-стадии

- `app/pipeline/intake_parser.py`
- `app/pipeline/layer_builder.py`
- `app/pipeline/viewpoint_runner.py`
- `app/pipeline/characterization.py`
- `app/pipeline/problem_factory.py`
- `app/pipeline/solution_factory.py`
- `app/pipeline/reporting.py`

### Валидация и FPF-контроль

- `app/validation/schema_validator.py`
- `app/validation/artifact_contract_validator.py`
- `app/validation/contract_validator.py`
- `app/validation/semantic_judge.py`
- `app/validation/assurance_engine.py`
- `app/validation/fpf_boundary_validator.py`
- `app/validation/fpf_characteristic_validator.py`
- `app/validation/fpf_comparison_validator.py`
- `app/validation/conflict_validator.py`
- `app/validation/cross_case_contamination_validator.py`

### Типизация и эпистемика

- `app/typization/typization_engine.py`
- `app/typization/type_registry.py`
- `contracts/epistemic_graph.contract.json`
- `schemas/*.json`

### Governance, release и quality

- `scripts/build_audit_trail.py`
- `scripts/run_integration_suite.py`
- `scripts/run_acceptance_checklist.py`
- `scripts/run_pilot.py`
- `scripts/prepare_release_package.py`
- `tests/`

## Структура артефактов кейса

Типовой workspace в `cases/<workspace_id>/` содержит:

- `raw/` — исходный текст кейса;
- `parsed/`, `intake/` — нормализованный вход и parsed artifacts;
- `layers/` — многослойная модель;
- `viewpoints/` — viewpoint reports и conflict index;
- `characterization/` — passport, indicators, cards;
- `problems/` — problem portfolio и selected problem;
- `solutions/` — solution portfolio, parity, tradeoffs, selected solutions;
- `analysis/` и `analysis/projections/` — промежуточные модели и projections;
- `evidence/` — evidence graph;
- `governance/` — ledger, decision log, contract audit, stage events;
- `decisions/`, `operation/` — ADR, runbook, rollback;
- `reports/` — управленческие и аналитические финальные документы.

## Быстрый старт

Полный прогон кейса:

```bash
python3 run_case.py "/путь/к/файлу_кейса.docx"
```

Создать workspace вручную:

```bash
python3 scripts/workspace_cli.py --project-root . create
```

Проверить валидность workspace:

```bash
python3 scripts/validate_workspace.py case_YYYYMMDD_NNN
```

Проверить одну стадию через оркестратор:

```bash
python3 scripts/run_stage.py case_YYYYMMDD_NNN reporting
```

Инкрементально перепроверить downstream-стадии после изменения:

```bash
python3 scripts/run_incremental.py case_YYYYMMDD_NNN problem_factory
```

Запустить типизацию:

```bash
python3 scripts/run_typization.py case_YYYYMMDD_NNN
```

Запустить тесты:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Через `make`:

```bash
make test
make create-workspace WORKSPACE_ID=case_YYYYMMDD_NNN
make validate-workspace WORKSPACE_ID=case_YYYYMMDD_NNN
make run-typization WORKSPACE_ID=case_YYYYMMDD_NNN
```

## Текущее позиционирование проекта

`Electronic Consultant v3` — это не чат-бот и не генератор "советов по тексту". Это файловая, audit-ready, FPF-aware аналитическая система поддержки решений, которая превращает сложный кейс в воспроизводимый набор артефактов для анализа, выбора решений, внедрения и последующего контроля.
