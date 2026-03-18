# Техническое задание: Усиление FPF-дисциплины, изоляции кейсов и контрактов pipeline

## 1. Цель

Доработать проект так, чтобы pipeline:

- не переносил шаблоны и решения из одного кейса в другой;
- различал факт, интерпретацию, гипотезу, допущение, нормативную цель и hard constraint;
- поддерживал смешанные кейсы, где одновременно присутствуют стратегические, операционные, governance и market-задачи;
- соблюдал явные контракты входов и выходов между stages;
- проверял соблюдение ключевых FPF-принципов не только через prompt discipline, но и через машинные validators;
- включал отдельный market-viewpoint как first-class skill.


## 2. Основание

Текущее поведение системы показало несколько системных дефектов:

- cross-case contamination: в отчеты одного кейса попадают narrative fragments и решения из другого домена;
- promotion error: гипотезы и расчетные оценки повышаются до hard constraints;
- mixed-case collapse: кейс со стратегическим и операционным измерением схлопывается в один режим мышления;
- markdown-first drift: статус утверждения определяется не типом claim, а тем, как он оформлен в тексте;
- слабая contract discipline между stages.

Для исправления используется архитектурное усиление, опирающееся на FPF-Spec.


## 3. Ключевые FPF-принципы, которые должны быть превращены в проверки

### 3.1 Boundary and contract discipline

- `A.6 Signature Stack & Boundary Discipline`
- `A.6.B Boundary Norm Square`
- `A.6.5 RelationSlotDiscipline`
- `A.6.C Contract Unpacking for Boundaries`

Что должно проверяться:

- boundary statements не смешивают факты, admissibility gates, deontics и evidence-effects;
- hard constraints, normative targets, commitments и evidence claims хранятся раздельно;
- каждое boundary-утверждение имеет тип и provenance.

### 3.2 Evidence and traceability

- `A.10 Evidence Graph Referring`
- `B.3.4 Evidence Decay & Epistemic Debt`
- `G.6 Evidence Graph & Provenance Ledger`

Что должно проверяться:

- сильные claims имеют source anchor или явный epistemic marker;
- stale evidence понижает confidence и decision readiness;
- reporting и selection используют только traceable claims.

### 3.3 Characteristics, comparability and lawful selection

- `A.17 A.CHR-NORM`
- `A.18 A.CSLC-KERNEL`
- `A.19.CN CN-frame`
- `A.19.CPM Unified Comparison Mechanism`
- `A.19.SelectorMechanism`
- `G.9 Parity / Benchmark Harness`

Что должно проверяться:

- `CHR-*` трактуются как characteristics, а не как свободные “метрики”;
- target для характеристики хранится как `normative_target`, а не как `source_fact`;
- comparison and selection выполняются на lawful comparable basis;
- selection по умолчанию работает как set-returning portfolio selection, а не как скрытая scalarization.

### 3.4 Explore / exploit and portfolio generation

- `B.5.1 Explore -> Shape -> Evidence -> Operate`
- `B.5.2.1 Creative Abduction with NQD`
- `C.18 NQD-CAL`
- `C.19 E/E-LOG`
- `G.5 Multi-Method Dispatcher & MethodFamily Registry`

Что должно проверяться:

- stage не имитирует зрелость уровня `Operate`, если кейс еще на уровне `Explore/Shape/Evidence`;
- пространство решений сохраняет novelty / quality / diversity;
- router и selector не схлопывают кейс в один метод раньше времени.

### 3.5 Multi-view and cross-context discipline

- `E.17.0 U.MultiViewDescribing`
- `E.17.1 U.ViewpointBundleLibrary`
- `F.9 Alignment & Bridge across Contexts`
- `F.15 SCR/RSCR Harness`

Что должно проверяться:

- viewpoints остаются lawful projections, а не случайными “мнениями”;
- cross-domain reuse разрешен только через явный bridge;
- violation контракта или contamination становится предметом regression harness.


## 4. Целевое архитектурное решение

### 4.1 Новые first-class артефакты

Добавить в workspace следующие артефакты:

- `analysis/domain_profile.json`
- `analysis/claims_registry.json`
- `analysis/constraints_registry.json`
- `analysis/assumptions_registry.json`
- `analysis/decision_readiness.json`
- `governance/contract_audit.jsonl`

### 4.2 Назначение артефактов

`domain_profile.json`

- хранит multi-label профиль кейса;
- задает набор доменных осей, их веса и confidence;
- определяет разрешенные reasoning modes и запрещенные template markers.

`claims_registry.json`

- хранит атомарные утверждения с типом, источником и epistemic class;
- становится главным semantic source вместо произвольного markdown.

`constraints_registry.json`

- хранит только lawful decision constraints;
- constraint может быть создан только из `source_fact` или `confirmed_assumption`.

`assumptions_registry.json`

- хранит допущения, которые влияют на выбор;
- отделяет `assumption` от `constraint`.

`decision_readiness.json`

- отвечает, разрешено ли переходить к optimization/selection;
- фиксирует, какие доменные контуры готовы к решению, а какие нет.

`contract_audit.jsonl`

- фиксирует проверки контрактов на каждом stage;
- хранит нарушения, degradation events, sanitizer actions, version contracts.


## 5. Новая типизация claims

Ввести обязательную типизацию утверждений.

Минимальный набор:

- `source_fact`
- `derived_metric`
- `normative_target`
- `interpretation`
- `hypothesis`
- `assumption`
- `confirmed_assumption`
- `decision_constraint`
- `recommendation`

Правила:

- `source_fact` должен иметь `source_ref`;
- `derived_metric` должен иметь `derivation_basis`;
- `normative_target` не может автоматически считаться фактом кейса;
- `decision_constraint` разрешен только если источник:
  - `source_fact`, или
  - `confirmed_assumption`;
- `hypothesis` и `interpretation` не могут быть source для `decision_constraint`.


## 6. Domain Profile: mixed-case routing вместо single-mode routing

### 6.1 Требование

Система не должна классифицировать кейс в один exclusive domain mode.

Вместо этого используется `multi-label domain profile`.

Пример:

```json
{
  "workspace_id": "case_x",
  "domain_axes": [
    {"id": "industrial_transformation", "weight": 0.45, "confidence": 0.82},
    {"id": "governance_crisis", "weight": 0.25, "confidence": 0.74},
    {"id": "market_validation", "weight": 0.20, "confidence": 0.68},
    {"id": "operations_bottleneck", "weight": 0.10, "confidence": 0.71}
  ],
  "reasoning_modes": [
    "strategic_reframing",
    "market_proof",
    "operational_containment"
  ],
  "forbidden_template_markers": [
    "BANT",
    "Shadow Mode",
    "CPQ",
    "Technical Director quotation bottleneck"
  ]
}
```

### 6.2 Что это решает

- mixed-case не схлопывается в одну логику;
- downstream stages знают, какие solution classes обязательны;
- чужие case-templates можно отлавливать автоматически.

### 6.3 Что изменить в проекте

Добавить:

- `app/pipeline/domain_profiler.py`
- новый artifact contract для `domain_profile.json`

Интегрировать в:

- `orchestrator`
- `viewpoint_runner`
- `problem_factory`
- `solution_factory`
- `reporting`


## 7. Новый skill: `ec-vp-market`

### 7.1 Назначение

Добавить отдельный skill для анализа market-side логики кейса:

- продажи;
- воронка;
- клиенты;
- buyer/user/payer split;
- спрос;
- каналы;
- price realization;
- market proof;
- pipeline leakage;
- условия покупки и повторяемости спроса.

### 7.2 Почему отдельный skill нужен

Сейчас market-измерение размыто между `client` и `strategist`.

Это приводит к проблемам:

- слабая диагностика воронки и продаж;
- отсутствие first-class артефакта для market proof;
- недоразличение “клиентской ценности” и “рыночной доказанности спроса”.

### 7.3 Что должен делать skill

Skill должен анализировать:

- кто покупатель;
- кто пользователь;
- кто принимает решение;
- по какому каналу приходит спрос;
- где ломается воронка;
- чем подтверждены объем, цена и частота покупки;
- есть ли LOI, предконтракты, повторяемые заказы, pipeline discipline;
- есть ли product-market drift.

### 7.4 Ожидаемый выход

В `viewpoints/market.md` должны быть разделы:

- `market reality`
- `demand gaps`
- `funnel failure points`
- `proof requirements`
- `market-side risks`

### 7.5 Что добавить в проект

Добавить:

- `.agent/skills/ec-vp-market/SKILL.md`

Изменить:

- `app/pipeline/viewpoint_runner.py`
- проверки coverage в reporting
- `domain_profile` builder


## 8. Контракты между stages

### 8.1 Цель

Каждый stage должен иметь машиночитаемый input/output contract.

### 8.2 Структура contracts

Добавить папку:

- `contracts/`

Добавить schema/contracts минимум для:

- `domain_profile`
- `viewpoint_report`
- `characterization_passport`
- `indicator_set`
- `problem_portfolio`
- `selected_problem_card`
- `comparison_acceptance_spec`
- `solution_portfolio`
- `selected_solutions`
- `adr`
- `runbook`
- `rollback_plan`
- `analytical_full_report`
- `executive_summary`

### 8.3 Что должны проверять contracts

- required artifacts on input;
- required fields on output;
- allowed epistemic classes;
- mandatory `source_ref` for facts and constraints;
- prohibition of unlawful promotion:
  - `hypothesis -> decision_constraint`
  - `normative_target -> source_fact`
  - `interpretation -> hard constraint`
- allowed domain markers from `domain_profile`.

### 8.4 Новый validator stack

Нужны 3 слоя проверок:

- `schema validator`
- `epistemic validator`
- `FPF-principle validator`


## 9. FPF-principle validators

Добавить отдельные validators:

### 9.1 Boundary validator

Проверяет:

- boundary statements не смешивают law / admissibility / deontic / evidence;
- section `hard_constraints` не содержит assumptions без anchor.

Основание:

- `A.6`
- `A.6.B`

### 9.2 Evidence validator

Проверяет:

- source anchor обязателен для сильных claims;
- stale evidence снижает assurance level;
- reporting не поднимает unsupported strong claims.

Основание:

- `A.10`
- `B.3.4`
- `G.6`

### 9.3 Characteristic validator

Проверяет:

- `CHR-*` имеют scale/level/coordinate semantics;
- target values помечены как `normative_target`;
- metric language не подменяет lawful CHR semantics.

Основание:

- `A.17`
- `A.18`
- `C.16`

### 9.4 Comparison legality validator

Проверяет:

- comparability basis задан явно;
- parity не строится на скрытых assumptions;
- selection не выполняет hidden scalarization.

Основание:

- `A.19.CN`
- `A.19.CPM`
- `A.19.SelectorMechanism`
- `G.9`

### 9.5 Cross-case contamination validator

Проверяет:

- в кейсе не появляются markers чужого домена без разрешения `domain_profile`;
- reporting/client не вставляют narrative fragments из другого кейса.

Основание:

- `F.9`
- `E.17.0`
- `F.15`


## 10. Очистка case-specific логики

### 10.1 `reporting.py`

Нужно убрать:

- hardcoded presales-template;
- упоминания `BANT`, `Shadow Mode`, `L1 routing`, `Technical Director bottleneck` как встроенные narrative branches.

Нужно заменить на:

- synthesis from `domain_profile.json`
- synthesis from `claims_registry.json`
- synthesis from selected problem / selected solutions / assumptions / constraints

### 10.2 `client.py`

Нужно убрать:

- case-specific branches для TD/presales кейса;
- hardcoded portfolios и готовые решения доменного типа;
- hardcoded executive-summary narrative fragments.

Нужно заменить на:

- generic generators;
- dispatch by domain profile;
- contract-aware rendering from typed artifacts.


## 11. Перепись biased fragments в skills

### 11.1 Текущая проблема

Часть skills содержит examples, которые задают скрытый domain bias.

### 11.2 Что переписать

В следующих skills заменить кейсовые примеры на мета-принципы:

- `.agent/skills/ec-vp-strategist/SKILL.md`
- `.agent/skills/ec-vp-operator/SKILL.md`
- `.agent/skills/ec-vp-analyst/SKILL.md`
- `.agent/skills/ec-vp-client/SKILL.md`

### 11.3 Принцип замены

Вместо:

- “1500 кубов на входе, 500 на выходе”
- “кому продавать сухую доску”
- “500 кубов термодерева”

использовать:

- flow conservation;
- strategic drift after loss of key module;
- evidence sufficiency for market viability;
- buyer / payer / user decomposition;
- proof-of-demand requirements;
- operational buffer and throughput logic.


## 12. Изменения по модулям проекта

Добавить новые модули:

- `app/pipeline/domain_profiler.py`
- `app/pipeline/claims_registry.py`
- `app/pipeline/constraints_registry.py`
- `app/pipeline/assumptions_registry.py`
- `app/pipeline/decision_readiness.py`
- `app/validation/contract_validator.py`
- `app/validation/fpf_boundary_validator.py`
- `app/validation/fpf_characteristic_validator.py`
- `app/validation/fpf_comparison_validator.py`
- `app/validation/cross_case_contamination_validator.py`

Изменить существующие модули:

- `app/pipeline/viewpoint_runner.py`
- `app/pipeline/characterization.py`
- `app/pipeline/problem_factory.py`
- `app/pipeline/solution_portfolio.py`
- `app/pipeline/selection_engine.py`
- `app/pipeline/reporting.py`
- `app/llm/client.py`
- `app/router/orchestrator.py`


## 13. Порядок внедрения

### Фаза 1. Быстрое снижение contamination

Сделать:

- ввести `domain_profile.json`;
- убрать hardcoded presales-template из `reporting.py`;
- убрать case-specific ветки из `client.py`;
- добавить `ec-vp-market`.

Результат:

- снизится перетекание кейсов;
- появится market-viewpoint;
- reporting станет case-faithful.

### Фаза 2. Контрактная дисциплина

Сделать:

- добавить `contracts/`;
- реализовать `contract_validator`;
- ввести `claims_registry`, `constraints_registry`, `assumptions_registry`.

Результат:

- unlawful promotion станет машинно фиксируемой ошибкой;
- hard constraints перестанут рождаться из narrative drift.

### Фаза 3. FPF validators

Сделать:

- boundary validator;
- evidence validator extension;
- characteristic validator;
- comparison legality validator;
- cross-case contamination validator.

Результат:

- pipeline начнет проверяться в терминах FPF, а не только по форме markdown.

### Фаза 4. Regression harness

Сделать:

- integration tests for mixed-cases;
- negative tests for contamination;
- negative tests for unlawful constraints;
- regression checks for market coverage.

Результат:

- нарушения будут ловиться до попадания в пользовательский отчет.


## 14. Критерии приемки

Изменение считается принятым, если выполняются условия:

- кейс про один домен не подтягивает narrative fragments и решения из другого домена;
- mixed-case сохраняет несколько reasoning modes;
- `budget`, `time horizon`, `quality threshold`, `capacity limit` не становятся hard constraints без lawful anchor;
- `CHR target` отображается как `normative_target`, а не как факт кейса;
- reporting умеет явно отделять:
  - факты,
  - интерпретации,
  - гипотезы,
  - assumptions,
  - constraints,
  - normative targets;
- viewpoint coverage включает `market` там, где market-side logic релевантна;
- selector и parity не нарушают set-return / no hidden scalarization discipline;
- contract violations логируются в `contract_audit.jsonl`.


## 15. Ожидаемый результат для проекта

После внедрения проект должен перейти:

из

- цепочки генерации markdown-артефактов с локальными доменными шаблонами

в

- контрактно-валидируемый FPF-aware pipeline,
- где reasoning modes composable,
- evidence traceable,
- domain contamination ограничено,
- а market/governance/strategy/operations могут сосуществовать в одном кейсе без взаимного разрушения.

