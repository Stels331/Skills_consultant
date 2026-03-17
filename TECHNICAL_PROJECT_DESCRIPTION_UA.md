# Технічний опис проєкту Electronic Consultant v3

## 1. Призначення системи

`Electronic Consultant v3` — це пайплайн аналітичної обробки кейсів, який перетворює неструктурований опис бізнес-ситуації на набір формалізованих артефактів для прийняття управлінських та архітектурних рішень.

Система орієнтована на такі задачі:

- прийом і нормалізація вхідного кейсу;
- побудова багатошарової моделі ситуації;
- запуск багаторакурсного аналізу через viewpoints;
- формування проблемного портфеля;
- генерація та порівняння альтернатив рішень;
- фіксація вибору в ADR, Runbook, Rollback Plan;
- побудова evidence graph та контроль доказовості;
- випуск підсумкової звітності для керівництва.

Фактично це rule-driven + LLM-assisted decision pipeline з сильним акцентом на трасованість, контроль якості артефактів та керований перезапуск етапів.

## 2. Поточна архітектурна модель

Система реалізована як локальний Python-застосунок без обов'язкової централізованої БД. Базова модель зберігання — файлова система з робочими просторами (`workspace`) у каталозі `cases/`.

Архітектурно проєкт складається з таких шарів:

### 2.1. Workspace layer

Відповідає за життєвий цикл робочого простору кейсу:

- створення `workspace_id` у форматі `case_YYYYMMDD_NNN`;
- підготовку стандартної директоріальної структури;
- зберігання метаданих, стану сесії, версіонування та базових JSON-артефактів.

Ключовий модуль:

- `app/state/workspace_manager.py`

### 2.2. Pipeline layer

Містить послідовність етапів обробки кейсу:

- `intake_parser`
- `layer_builder`
- `viewpoint_runner`
- `characterization`
- `problem_factory`
- `solution_portfolio`
- `parity_tradeoff`
- `conflict_router`
- `selection_engine`
- `reporting`

Ключові модулі:

- `app/pipeline/*.py`

### 2.3. Orchestration and gating layer

Керує переходами між етапами, валідацією артефактів, оцінкою assurance, freshness та semantic checks.

Функції:

- перевірка контрактів артефактів;
- визначення `pass / degrade / block`;
- логування рішень оркестратора;
- фіксація stage events;
- запуск refresh/re-entry логіки.

Ключові модулі:

- `app/router/orchestrator.py`
- `app/router/phase_controller.py`
- `app/router/transition_logic.py`

### 2.4. Validation and assurance layer

Цей шар контролює формальну якість артефактів і доказовість рішень.

Функції:

- schema validation;
- artifact contract validation;
- semantic judge;
- assurance engine;
- validation matrix;
- freshness policy.

Ключові модулі:

- `app/validation/artifact_contract_validator.py`
- `app/validation/schema_validator.py`
- `app/validation/semantic_judge.py`
- `app/validation/assurance_engine.py`
- `app/validation/validation_matrix.py`

### 2.5. Evidence and observability layer

Відповідає за прозорість, аудит та контроль походження висновків.

Функції:

- побудова `evidence_graph`;
- класифікація claim-ів;
- аудит проходження стадій;
- формування audit trail;
- фіксація operational signals та re-entry triggers.

Ключові модулі:

- `app/evidence/graph.py`
- `app/observability/audit.py`
- `app/refresh/orchestrator.py`

### 2.6. LLM integration layer

Система підтримує кілька режимів генерації:

- `local`
- `openai`
- `antigravity`

LLM використовується не як єдине джерело логіки, а як підсилювач окремих етапів: побудова шарів, viewpoints, characterization, solution artifacts, reporting.

Ключовий модуль:

- `app/llm/client.py`

### 2.7. Release and operations layer

Містить сценарії інтеграційного прогону, release readiness, pilot validation та операційні скрипти.

Ключові модулі та скрипти:

- `app/release/pilot.py`
- `app/release/release_package.py`
- `scripts/run_integration_suite.py`
- `scripts/run_pilot.py`
- `scripts/prepare_release_package.py`

## 3. Функціональний контур системи

Нижче наведений фактичний функціональний ланцюг обробки кейсу.

### 3.1. Intake

Система приймає вхідний текст кейсу з `raw/case_input.md` і формує нормалізоване представлення.

Результати:

- `intake/normalized_case.md`
- `parsed/*.md`
- `parsed/*.json`

### 3.2. Layer modeling

На основі нормалізованого кейсу будуються чотири шари:

- бізнес-модель;
- вимоги;
- функціональна модель;
- модель розподілу відповідальності.

Результати:

- `layers/layer_1_business_model.md`
- `layers/layer_2_requirements.md`
- `layers/layer_3_functional_model.md`
- `layers/layer_4_allocation_model.md`

### 3.3. Viewpoint analysis

Система генерує аналіз із шести перспектив:

- strategist
- analyst
- operator
- architect
- critic
- client

Додатково формується індекс конфліктів між perspectives.

Результати:

- `viewpoints/*.md`
- `viewpoints/conflicts_index.md`

### 3.4. Characterization

Система будує:

- Characterization Passport;
- Indicator Set;
- Parity Plan;
- characteristic cards для ключових індикаторів.

Результати:

- `characterization/CharacterizationPassport.md`
- `characterization/IndicatorSet.md`
- `characterization/ParityPlan.md`
- `characterization/CharacteristicCards/*.md`

### 3.5. Problem Factory

На основі попередніх етапів система виділяє портфель проблем, обирає ключову проблему і фіксує критерії прийнятності.

Результати:

- `problems/ProblemArchive.md`
- `problems/ProblemPortfolio.md`
- `problems/SelectedProblemCard.md`
- `problems/ComparisonAcceptanceSpec.md`

### 3.6. Solution Factory

Система генерує набір альтернатив, порівнює їх, маршрутизує конфлікти та обирає рішення.

Результати:

- `solutions/SolutionPortfolio.md`
- `solutions/ParityPlan.md`
- `solutions/ParityReport.md`
- `solutions/TradeoffTable.md`
- `solutions/ConflictRecords.md`
- `solutions/SelectedSolutions.md`

### 3.7. Decision and operations package

На основі обраних рішень формується пакет для впровадження.

Результати:

- `decisions/ADR-001.md`
- `operation/Runbook.md`
- `operation/RollbackPlan.md`

### 3.8. Evidence and reporting

Система формує доказову модель та підсумкові звіти.

Результати:

- `evidence/evidence_graph.md`
- `evidence/evidence_graph.json`
- `reports/Analytical_Full_Report.md`
- `reports/Executive_Summary.md`
- `reports/reporting_summary.json`

## 4. Модель зберігання даних

На поточному етапі проєкт працює без обов'язкової реляційної БД. Основне сховище — файлова система.

### 4.1. Основні характеристики storage-моделі

- кожен кейс ізольований у власному каталозі в `cases/`;
- артефакти зберігаються у Markdown та JSON;
- стан workflow зберігається локально в `state/` і `governance/`;
- трасування та evidence також матеріалізуються як файли.

### 4.2. Переваги поточної моделі

- просте локальне розгортання;
- прозорий доступ до всіх артефактів;
- зручність аудиту та ручної перевірки;
- відсутність обов'язкової інфраструктурної залежності на СУБД.

### 4.3. Обмеження поточної моделі

- низька придатність до паралельної багатокористувацької роботи;
- обмежений контроль конкурентного доступу;
- складніший централізований backup/restore у production-середовищі;
- ускладнена горизонтальна масштабованість.

## 5. Зовнішні залежності та інтеграційні точки

### 5.1. Обов'язкові залежності

- `Python 3`
- локальна файлова система з доступом на запис

### 5.2. Умовно-обов'язкові залежності

Залежать від режиму запуску:

- LLM provider API для режимів `openai` або `antigravity`;
- локальні skills у `.agent/skills/`;
- схеми в каталозі `schemas/`.

### 5.3. Потенційні інтеграції

Проєкт може бути інтегрований з:

- зовнішніми LLM API;
- CI/CD пайплайном;
- системами моніторингу;
- future storage layer на базі PostgreSQL / object storage / queue broker.

## 6. Поточний спосіб виконання

Проєкт наразі орієнтований на запуск через CLI-скрипти.

Основні сценарії:

- створення workspace;
- послідовний запуск окремих стадій;
- smoke run;
- integration suite;
- pilot run;
- валідація workspace;
- діагностика stage failures.

Приклади точок входу:

- `scripts/workspace_cli.py`
- `scripts/run_stage.py`
- `scripts/run_solution_factory.py`
- `scripts/run_reporting.py`
- `scripts/run_integration_suite.py`

## 7. Варіанти розгортання

Нижче наведені рекомендовані моделі deployment для ІТ-фахівця.

### 7.1. Локальне розгортання на робочій станції

Підходить для:

- розробки;
- тестування;
- ручного прогону кейсів;
- відладки LLM prompts і артефактів.

Характеристики:

- один процес;
- локальний filesystem storage;
- запуск через CLI;
- мінімальні інфраструктурні вимоги.

Переваги:

- найпростіший запуск;
- мінімальна вартість;
- зручний дебаг.

Недоліки:

- відсутність multi-user режиму;
- слабка операційна ізоляція;
- обмежена автоматизація.

### 7.2. Single-node server / VM

Підходить для:

- внутрішнього корпоративного використання;
- невеликого навантаження;
- централізованого зберігання кейсів.

Характеристики:

- розгортання на одній VM або bare-metal host;
- запуск через `systemd`, `supervisor` або cron;
- дані зберігаються на локальному або змонтованому диску;
- доступ до LLM API назовні.

Переваги:

- простіша централізація;
- керований backup;
- не потребує складного orchestration stack.

Недоліки:

- single point of failure;
- обмежена масштабованість;
- складніше ізолювати паралельні job-и.

### 7.3. Контейнеризоване розгортання

Рекомендовано як базовий production-ready сценарій.

Склад:

- Docker image з Python runtime;
- mounted volume або persistent storage для `cases/`, `reports/`, `governance/`;
- environment variables для вибору LLM mode;
- окремий job runner для batch-етапів.

Переваги:

- повторюваність середовища;
- простіший CI/CD;
- зручніше переносити між серверами.

Умови:

- потрібно явно вирішити persistence для файлових артефактів;
- потрібно зафіксувати секрети для LLM provider;
- бажано додати healthcheck і audit log shipping.

### 7.4. Kubernetes / orchestrated deployment

Доцільно лише якщо проєкт буде розвиватися у сервісну багатокористувацьку платформу.

Потрібно додатково:

- винести stateful storage за межі pod filesystem;
- відокремити API layer, worker layer та scheduler;
- впровадити черги задач;
- централізувати logs, metrics, traces;
- додати object storage або БД для артефактів та індексів.

Без цих змін пряме перенесення поточної файлової архітектури в Kubernetes буде технічно можливим, але операційно слабким.

## 8. Рекомендації щодо способу розгортання

Для поточної версії системи рекомендовані такі сценарії:

### Варіант A. Development / R&D

- локальний запуск або Docker Compose;
- артефакти на локальному диску;
- зовнішній LLM provider за API;
- ручний або напівавтоматичний прогін pipeline.

### Варіант B. Internal production for analysts

- одна VM або один Docker host;
- persistent volume;
- регулярний backup каталогу `cases/`;
- job scheduler для запуску кейсів;
- окремий доступ до audit trail та reports.

### Варіант C. Масштабований сервіс

Потребує архітектурної еволюції:

- API service;
- worker queue;
- централізована БД для metadata/state;
- object storage для артефактів;
- окремий evidence index;
- observability stack;
- механізм блокування конкурентних змін одного workspace.

На поточному стані кодової бази цей сценарій ще не є оптимальним без доробки storage та execution model.

## 9. Технічні ризики для deployment

При виборі способу розгортання слід врахувати такі ризики:

- файлова модель зберігання ускладнює горизонтальне масштабування;
- частина логіки залежить від зовнішніх LLM-викликів;
- відсутня повноцінна server-side API-обгортка як основний інтерфейс;
- необхідно контролювати цілісність `cases/` при паралельних запусках;
- необхідно визначити політику зберігання секретів та audit logs.

## 10. Висновок для ІТ-спеціаліста

`Electronic Consultant v3` у поточному вигляді є pipeline-oriented Python-системою з файловим state management, rule-based orchestration та інтегрованим LLM-шаром.

Для поточного стану проєкту найраціональніші способи розгортання:

- локальна машина для розробки та тестів;
- одна VM або один контейнерний вузол для внутрішнього використання;
- контейнеризація з persistent volume як базовий production-контур.

Якщо планується перехід до багатокористувацького сервісу або до концепції "цифрового двійника бізнесу", потрібно окремо закладати:

- централізоване state/storage;
- queue-based execution;
- API layer;
- розширену observability;
- механізми конкурентного доступу;
- knowledge store поза файловою системою.
