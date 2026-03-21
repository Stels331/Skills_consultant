# Технічний опис проєкту Electronic Consultant v3

## 1. Призначення системи

`Electronic Consultant v3` — це локальна Python-система для структурованого розбору складних бізнесових, операційних, управлінських та архітектурних кейсів. Вона перетворює неструктурований опис ситуації на трасований набір аналітичних артефактів, придатних для прийняття рішень, запуску пілоту, архітектурного опрацювання та аудиту.

Система реалізує FPF-aware pipeline і навмисно уникає типових дефектів "вільного" LLM-аналізу:

- змішування фактів, інтерпретацій, гіпотез і обмежень;
- перенесення фрагментів між різними кейсами;
- передчасного схлопування mixed-case у одну логіку;
- неявного просування hypothesis до decision constraint;
- втрати походження висновків після перегенерації артефактів.

На практиці це rule-driven + LLM-assisted decision pipeline з акцентом на contract discipline, evidence traceability, stage gating та audit readiness.

## 2. Цільова задача системи

Система не просто "пише звіт". Її задача:

- нормалізувати вхідний кейс і побудувати його робочу модель;
- розділити claims за епістемічними типами;
- провести аналіз через кілька viewpoints;
- зібрати problem portfolio та solution portfolio;
- виконати selection на lawful comparable basis;
- зафіксувати рішення в ADR та операційному пакеті;
- зберегти evidence graph, governance logs і проміжні проєкції для перевірки.

Результатом є не одна відповідь моделі, а відтворюваний пакет артефактів, який можна перевіряти, повторно запускати, інкрементально оновлювати та використовувати як основу для подальшої деталізації рішення.

## 3. Архітектурна модель

### 3.1. Workspace-first storage

Система працює без обов'язкової централізованої БД. Базова модель зберігання — ізольовані workspace-каталоги в `cases/`.

Це дає:

- ізоляцію кожного кейсу;
- просту локальну експлуатацію;
- прозорий доступ до всіх артефактів;
- відтворюваність прогонів;
- зручний аудит і ручну діагностику.

Типовий ідентифікатор workspace:

- `case_YYYYMMDD_NNN`

Ключові модулі:

- `app/state/workspace_manager.py`
- `app/state/state_machine.py`
- `scripts/workspace_cli.py`

### 3.2. Pipeline layer

Функціональне ядро системи — послідовність стадій обробки кейсу:

- `intake`
- `layers`
- `viewpoints`
- `characterization`
- `problem_factory`
- `solution_factory`
- `reporting`

Ці стадії реалізовані як окремі модулі та CLI-скрипти, що дозволяє як повний end-to-end запуск, так і вибіркову ручну обробку.

Ключові модулі:

- `app/pipeline/intake_parser.py`
- `app/pipeline/layer_builder.py`
- `app/pipeline/viewpoint_runner.py`
- `app/pipeline/characterization.py`
- `app/pipeline/problem_factory.py`
- `app/pipeline/solution_factory.py`
- `app/pipeline/reporting.py`

### 3.3. Orchestration and gating layer

Оркестрація побудована навколо `StageOrchestrator`, який відповідає за контроль проходження стадій.

Функції цього шару:

- визначення ключового артефакту стадії;
- перевірка вхідних і вихідних контрактів;
- запуск semantic та assurance checks;
- побудова evidence graph;
- прийняття gate-рішення `pass`, `degrade` або `block`;
- запис decision log та stage events;
- підтримка re-entry та incremental recheck сценаріїв.

Ключові модулі:

- `app/router/orchestrator.py`
- `app/router/phase_controller.py`
- `app/router/transition_logic.py`
- `app/router/context_budget_enforcer.py`
- `scripts/run_stage.py`
- `scripts/run_incremental.py`

### 3.4. Validation and assurance layer

Окремий шар валідації не дає pipeline спиратися лише на prompt discipline.

Тут перевіряються:

- JSON schema compliance;
- artifact contracts;
- stage input contracts;
- semantic consistency;
- evidence sufficiency;
- freshness policy;
- validation matrix outcome;
- FPF-specific boundary, characteristic, comparison і conflict rules.

Ключові модулі:

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

### 3.5. Epistemic and evidence layer

Система працює з епістемічною моделлю, де різні види тверджень не змішуються між собою.

Ключові claim types:

- `source_fact`
- `derived_metric`
- `normative_target`
- `interpretation`
- `hypothesis`
- `assumption`
- `confirmed_assumption`
- `decision_constraint`
- `recommendation`
- `conflict_case`

Evidence layer відповідає за:

- побудову `evidence_graph`;
- трасування походження claims;
- матеріалізацію projections;
- збереження audit trail;
- append-only фіксацію epistemic events.

Ключові артефакти:

- `evidence/evidence_graph.json`
- `analysis/projections/*.json`
- `governance/epistemic_ledger.jsonl`
- `governance/decision_log.jsonl`
- `governance/stage_events.jsonl`
- `governance/contract_audit.jsonl`

### 3.6. Contracts, schemas and typing

Окремий набір схем і контрактів задає формальні межі між стадіями.

Це потрібно для того, щоб:

- не приймати некоректні артефакти як валідні;
- виявляти порушення меж і структури якомога раніше;
- забезпечувати машинну перевірку переходів;
- підтримувати інкрементальні перевірки без втрати узгодженості.

Ключові каталоги:

- `schemas/`
- `contracts/`
- `Type/`

Ключові модулі:

- `app/typization/typization_engine.py`
- `app/typization/type_registry.py`

### 3.7. Rule-driven + LLM-assisted execution

LLM у проєкті використовується як підсилювач окремих стадій, а не як єдине джерело логіки. Реальне рішення формується комбінацією:

- файлової моделі workspace;
- Python orchestration;
- явних schema/contract checks;
- FPF validator-ів;
- viewpoint decomposition;
- evidence/governance layer;
- LLM mode для генерації текстових артефактів.

Підтримувані режими задаються через середовище:

- `LLM_MODE`
- `SEMANTIC_JUDGE_MODE`

## 4. Функціональний workflow

### 4.1. Intake

Система приймає кейс у вигляді `.md`, `.txt`, `.docx`, `.doc` або `.rtf`, читає вміст і формує нормалізоване представлення.

Результати:

- `raw/*`
- `parsed/*.md`
- `parsed/*.json`
- `intake/normalized_case.md`

### 4.2. Layer modeling

Після intake кейс декомпонується на системні шари:

- бізнес-модель;
- вимоги;
- функціональна модель;
- allocation / responsibility model.

Результати:

- `layers/layer_1_business_model.md`
- `layers/layer_2_requirements.md`
- `layers/layer_3_functional_model.md`
- `layers/layer_4_allocation_model.md`

### 4.3. Viewpoint analysis

Система генерує аналіз через viewpoints:

- `strategist`
- `analyst`
- `operator`
- `architect`
- `critic`
- `client`
- `market` для market-heavy контекстів

Також формується `conflicts_index`.

Результати:

- `viewpoints/*.md`

### 4.4. Characterization

На цьому етапі система формує:

- `CharacterizationPassport.md`
- `IndicatorSet.md`
- `ParityPlan.md`
- `CharacteristicCards/*.md`

### 4.5. Problem Factory

Стадія перетворює попередній аналіз на problem portfolio, виділяє ключову проблему і фіксує умови порівняння.

Результати:

- `ProblemArchive.md`
- `ProblemPortfolio.md`
- `SelectedProblemCard.md`
- `ComparisonAcceptanceSpec.md`

### 4.6. Solution Factory

Система генерує альтернативи, проводить parity/trade-off аналіз, маршрутизує конфлікти і формує рекомендований набір рішень.

Результати:

- `SolutionPortfolio.md`
- `ParityPlan.md`
- `ParityReport.md`
- `TradeoffTable.md`
- `ConflictRecords.md`
- `SelectedSolutions.md`

### 4.7. Decision and operations package

Після selection система формує артефакти впровадження:

- `decisions/ADR-001.md`
- `operation/Runbook.md`
- `operation/RollbackPlan.md`

### 4.8. Reporting and governance

Фінальний пакет містить:

- `reports/Executive_Summary.md`
- `reports/Analytical_Full_Report.md`
- `reports/reporting_summary.json`
- evidence graph;
- governance logs;
- projections для downstream-перевірок і звітності.

## 5. Модель виконання

### 5.1. Повний запуск

Основна точка входу:

```bash
python3 run_case.py "/шлях/до/файлу_кейса.docx"
```

### 5.2. Керований запуск

Для ручної роботи з workspace і стадіями використовуються:

- `scripts/workspace_cli.py`
- `scripts/run_stage.py`
- `scripts/run_incremental.py`
- `scripts/validate_workspace.py`
- `scripts/run_typization.py`

### 5.3. Quality and release

Для перевірки якості та release readiness є окремі сценарії:

- `scripts/run_integration_suite.py`
- `scripts/run_acceptance_checklist.py`
- `scripts/run_pilot.py`
- `scripts/prepare_release_package.py`
- `tests/`

## 6. Ключові архітектурні переваги

- Ізоляція кейсів на рівні workspace.
- Відтворюваний pipeline замість одноразової відповіді моделі.
- Machine-checkable contracts між стадіями.
- FPF-aware валідація замість довіри до формулювань у markdown.
- Evidence-based selection і audit-ready governance trail.
- Можливість інкрементального recheck без повного перезапуску всього кейсу.

## 7. Обмеження поточної реалізації

- Основне сховище файлове, тому система не оптимізована під паралельну багатокористувацьку роботу.
- Частина цінності залежить від якості LLM-mode та вхідного опису кейсу.
- Деякі артефакти досі зберігаються як materialized files, тому цілісність підтримується через contracts і validators, а не через централізовану БД.

## 8. Коротко

`Electronic Consultant v3` — це файловий, FPF-aware, audit-ready pipeline підтримки рішень, який перетворює складний кейс на набір формалізованих артефактів для аналізу, selection, впровадження та контролю результату.
