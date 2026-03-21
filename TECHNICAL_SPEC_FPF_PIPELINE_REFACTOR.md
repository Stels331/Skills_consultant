# Техническое задание: Рефакторинг FPF-aware pipeline

## 1. Цель

Перестроить pipeline проекта так, чтобы он:

- не переносил narrative fragments и решения из одного кейса в другой;
- различал факт, вывод, гипотезу, допущение, нормативную цель и decision constraint;
- поддерживал mixed-case, где одновременно присутствуют стратегические, операционные, governance и market-задачи;
- соблюдал явные контракты входов и выходов между stages;
- проверял соблюдение ключевых FPF-принципов машинно, а не только через prompt discipline;
- использовал отдельный market-viewpoint как first-class skill;
- был audit-ready: любая promotion/degradation claim должна быть восстановима по истории.


## 2. Основание

Текущее поведение системы показало несколько системных дефектов:

- `cross-case contamination`: в отчет одного кейса попадают narrative fragments и решения из другого домена;
- `unlawful promotion`: гипотезы и расчетные прикидки повышаются до hard constraints;
- `mixed-case collapse`: кейс со стратегическим и операционным измерением схлопывается в одну логику;
- `markdown-first drift`: статус утверждения определяется не типом claim, а формулировкой в markdown;
- `weak contract discipline`: stage принимает и отдает артефакты без строгой проверки допустимых переходов;
- `poor provenance`: после перезаписи файла трудно понять, кто и когда превратил hypothesis в confirmed assumption или constraint.

Для исправления используется архитектурное усиление, опирающееся на FPF-Spec.


## 3. Ключевые FPF-принципы, которые должны быть превращены в проверки

### 3.1 Boundary and contract discipline

- `A.6 Signature Stack & Boundary Discipline`
- `A.6.B Boundary Norm Square`
- `A.6.5 RelationSlotDiscipline`
- `A.6.C Contract Unpacking for Boundaries`

Что должно проверяться:

- boundary statements не смешивают факты, admissibility gates, deontics и evidence-effects;
- hard constraints, commitments, normative targets и evidence claims хранятся раздельно;
- каждое boundary-утверждение имеет тип, provenance и ownered route.

### 3.2 Evidence and traceability

- `A.10 Evidence Graph Referring`
- `B.3.4 Evidence Decay & Epistemic Debt`
- `G.6 Evidence Graph & Provenance Ledger`

Что должно проверяться:

- сильные claims имеют source anchor или явный epistemic marker;
- stale evidence понижает confidence и decision readiness;
- reporting и selection используют только traceable claims;
- любое изменение статуса claim сохраняется в append-only журнале.

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
- contamination и contract violations становятся предметом regression harness.


## 4. Целевая архитектура данных

### 4.1 Канонический источник истины: единый эпистемический граф

Вместо нескольких независимых registry-файлов каноническим source of truth должен стать:

- `analysis/epistemic_graph.json`

Структура:

- `nodes[]`: claims, targets, assumptions, constraints, recommendations, conflicts, artifacts, provenance events;
- `edges[]`: typed relations между узлами.

Базовые типы узлов:

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
- `artifact_ref`

Базовые типы связей:

- `DERIVED_FROM`
- `SUPPORTED_BY`
- `CONSTRAINS`
- `CONTRADICTS`
- `PROMOTED_FROM`
- `DEGRADED_FROM`
- `PROJECTED_INTO`
- `BLOCKS`
- `WAIVED_BY`

### 4.2 Materialized projections

Допускаются производные представления, но не как отдельные primary stores, а как materialized projections из графа:

- `analysis/claims_projection.json`
- `analysis/constraints_projection.json`
- `analysis/assumptions_projection.json`
- `analysis/decision_readiness.json`

Назначение:

- дать lightweight view для validator-ов и reporting;
- уменьшить связанность кода с сырым graph traversal;
- не потерять referential integrity.

### 4.3 Append-only provenance ledger

Для аудита и replay должен быть отдельный append-only журнал:

- `governance/epistemic_ledger.jsonl`

Каждое событие фиксирует:

- `event_id`
- `timestamp`
- `stage`
- `actor`
- `action`
- `target_id`
- `old_type`
- `new_type`
- `reason`
- `source_refs`

Примеры событий:

- `claim_created`
- `claim_promoted`
- `claim_degraded`
- `constraint_compiled`
- `conflict_marked`
- `conflict_resolved`
- `projection_emitted`
- `validator_failed`

### 4.4 Почему chosen architecture именно такая

Нужно совместить два свойства:

- удобство runtime access;
- полноценную auditability.

Поэтому:

- `epistemic_graph.json` хранит текущее canonical state;
- `epistemic_ledger.jsonl` хранит историю изменений;
- projections дают компактные срезы для stages.


## 5. Типизация claims и правила lawful promotion

### 5.1 Минимальный набор claim types

- `source_fact`
- `derived_metric`
- `normative_target`
- `interpretation`
- `hypothesis`
- `assumption`
- `confirmed_assumption`
- `decision_constraint`
- `recommendation`
- `disputed_claim`

### 5.2 Обязательные поля

Для `source_fact`:

- `id`
- `claim_type`
- `statement`
- `source_ref`
- `source_anchor_type=explicit_source`

Для `derived_metric`:

- `id`
- `claim_type`
- `statement`
- `derivation_basis`
- `source_ref[]`

Для `normative_target`:

- `id`
- `claim_type`
- `statement`
- `target_of`
- `justification`

Для `decision_constraint`:

- `id`
- `claim_type`
- `statement`
- `compiled_from[]`
- `constraint_class`
- `admissibility_status`

### 5.3 Правила lawful promotion

- `normative_target` не может автоматически считаться фактом кейса;
- `decision_constraint` может быть скомпилирован только из:
  - `source_fact`, или
  - `confirmed_assumption`;
- `hypothesis` и `interpretation` не могут быть source для `decision_constraint`;
- `derived_metric` может участвовать в constraint compilation только если:
  - derivation explicit,
  - source chain замкнута,
  - validator подтвердил lawful derivation;
- `disputed_claim` не может участвовать в selection и parity, пока не получит status:
  - `resolved`, или
  - `waived_with_note`.


## 6. Модель конфликтов и противоречий

### 6.1 Проблема

Разные viewpoints могут дать противоречащие claims по одному и тому же вопросу.

Это нельзя оставлять как обычный markdown noise.

### 6.2 Решение

Добавить formal conflict layer в graph.

Новые сущности:

- `conflict_case`
- `disputed_claim`
- `resolution_status`
- `resolution_basis`

Новые связи:

- `CONTRADICTS`
- `RESOLVED_BY`
- `WAIVED_BY`

### 6.3 Правило pipeline

Если в graph есть contradiction между claims, relevant to readiness or selection:

- orchestrator не имеет права silently компилировать это в constraint;
- должен быть запущен conflict resolution path:
  - либо аналитическое разрешение;
  - либо запрос к пользователю;
  - либо явная waiver-пометка.


## 7. Domain Profile: mixed-case routing вместо single-mode routing

### 7.1 Требование

Система не должна классифицировать кейс в один exclusive domain mode.

Вместо этого используется `multi-label domain profile`.

Новый first-class artifact:

- `analysis/domain_profile.json`

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
  "allowed_ontological_domains": [
    "industrial_plant",
    "governance",
    "market_demand"
  ],
  "forbidden_template_markers": [
    "BANT",
    "Shadow Mode",
    "CPQ",
    "Technical Director quotation bottleneck"
  ]
}
```

### 7.2 Что это решает

- mixed-case не схлопывается в одну логику;
- downstream stages знают, какие reasoning modes и solution classes обязательны;
- contamination можно ловить не только по blacklist, но и по ontological mismatch.

### 7.3 Whitelist + blacklist + semantic drift check

Контроль contamination не должен опираться только на blacklist.

Нужна комбинация:

- `allowed_ontological_domains`
- `forbidden_template_markers`
- `semantic drift validator`

`semantic drift validator` выполняет soft-check:

- слишком ли используемые термины и решения удалены от allowed domains текущего кейса.


## 8. Projection layer для защиты контекстного окна

### 8.1 Проблема

LLM не должна получать целиком `epistemic_graph.json`, если он содержит сотни nodes и edges.

### 8.2 Решение

Перед каждым skill invocation orchestrator должен строить typed projection.

Примеры projections:

- `problem_factory_projection.json`
  - facts
  - unresolved contradictions
  - admissible assumptions
  - domain profile

- `selection_projection.json`
  - lawful constraints
  - admissible alternatives
  - unresolved assumptions
  - parity inputs

- `reporting_projection.json`
  - human-facing facts
  - interpretations
  - hypotheses
  - assumptions
  - chosen recommendations

### 8.3 Правило

LLM stage работает только с projection, а не с raw graph.

Это должно быть обязательным системным свойством, а не оптимизацией “по возможности”.


## 9. Новый skill: `ec-vp-market`

### 9.1 Назначение

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
- условия покупки и повторяемости спроса;
- альтернативы на рынке;
- status quo defense.

### 9.2 Почему отдельный skill нужен

Сейчас market-измерение размыто между `client` и `strategist`.

Это приводит к проблемам:

- слабая диагностика воронки и продаж;
- отсутствие first-class артефакта для market proof;
- недоразличение “клиентской ценности” и “рыночной доказанности спроса”;
- отсутствие явного анализа substitutes и switching friction.

### 9.3 Что должен делать skill

Skill должен анализировать:

- кто покупатель;
- кто пользователь;
- кто принимает решение;
- по какому каналу приходит спрос;
- где ломается воронка;
- чем подтверждены объем, цена и частота покупки;
- есть ли LOI, предконтракты, повторяемые заказы, pipeline discipline;
- есть ли product-market drift;
- какие существуют `next best alternatives`;
- как выглядит `status quo defense`;
- что мешает пользователю/покупателю переключиться.

### 9.4 Ожидаемый выход

В `viewpoints/market.md` должны быть разделы:

- `market reality`
- `demand gaps`
- `funnel failure points`
- `current alternatives`
- `status quo defense`
- `proof requirements`
- `market-side risks`

### 9.5 Что добавить в проект

Добавить:

- `.agent/skills/ec-vp-market/SKILL.md`

Изменить:

- `app/pipeline/viewpoint_runner.py`
- coverage checks в reporting
- `domain_profile` builder
- `viewpoints/conflicts_index.md` synthesis


## 10. Контракты между stages

### 10.1 Цель

Каждый stage должен иметь машиночитаемый input/output contract.

### 10.2 Структура contracts

Добавить папку:

- `contracts/`

Добавить schema/contracts минимум для:

- `domain_profile`
- `epistemic_graph`
- `projection`
- `viewpoint_report`
- `market_viewpoint_report`
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

### 10.3 Что должны проверять contracts

- required artifacts on input;
- required fields on output;
- allowed epistemic classes;
- mandatory `source_ref` for facts and constraints;
- prohibition of unlawful promotion:
  - `hypothesis -> decision_constraint`
  - `normative_target -> source_fact`
  - `interpretation -> hard constraint`;
- allowed domain markers from `domain_profile`;
- отсутствие unresolved contradictions в selection-critical paths.

Для contract-sensitive LLM artifacts дополнительно должно проверяться:

- сохранен ли raw output до любой обработки;
- зафиксирован ли `parse_quality`;
- записан ли field-level provenance для non-explicit полей;
- отмечен ли `artifact_trust_level`;
- запрещено ли прохождение degraded artifact в trusted downstream stages.


## 11. Validator stack

Нужны 4 слоя проверок:

- `schema validator`
- `epistemic validator`
- `FPF-principle validator`
- `semantic drift / contamination validator`

### 11.1 Boundary validator

Проверяет:

- boundary statements не смешивают law / admissibility / deontic / evidence;
- section `hard_constraints` не содержит assumptions без lawful anchor.

Основание:

- `A.6`
- `A.6.B`

### 11.2 Evidence validator

Проверяет:

- source anchor обязателен для сильных claims;
- stale evidence снижает assurance level;
- reporting не поднимает unsupported strong claims.

Основание:

- `A.10`
- `B.3.4`
- `G.6`

### 11.3 Characteristic validator

Проверяет:

- `CHR-*` имеют scale/level/coordinate semantics;
- target values помечены как `normative_target`;
- metric language не подменяет lawful CHR semantics.

Основание:

- `A.17`
- `A.18`
- `C.16`

### 11.4 Comparison legality validator

Проверяет:

- comparability basis задан явно;
- parity не строится на скрытых assumptions;
- selection не выполняет hidden scalarization.

Основание:

- `A.19.CN`
- `A.19.CPM`
- `A.19.SelectorMechanism`
- `G.9`

### 11.5 Cross-case contamination validator

Проверяет:

- в кейсе не появляются markers чужого домена без разрешения `domain_profile`;
- reporting/client не вставляют narrative fragments из другого кейса;
- текст не уходит семантически за пределы `allowed_ontological_domains`.

Основание:

- `F.9`
- `E.17.0`
- `F.15`

### 11.6 Structured parse boundary validator

Проверяет:

- различаются ли `clean`, `normalized`, `inferred`, `failed`;
- key alias normalization не смешивается с value reinterpretation;
- retry выполняется до fallback;
- failed parse оставляет audit trail с `raw_output_path`, `missing_fields`, `retry_outcome`;
- `SolutionPortfolio` с `artifact_trust_level=degraded` блокируется до selection.

Основание:

- `A.6`
- `A.10`
- `G.6`


## 12. Очистка case-specific логики

### 12.1 `reporting.py`

Нужно убрать:

- hardcoded presales-template;
- упоминания `BANT`, `Shadow Mode`, `L1 routing`, `Technical Director bottleneck` как встроенные narrative branches.

Нужно заменить на:

- synthesis from `domain_profile.json`
- synthesis from `epistemic_graph.json`
- synthesis from projections

### 12.2 `client.py`

Нужно убрать:

- case-specific branches для TD/presales кейса;
- hardcoded portfolios и готовые решения доменного типа;
- hardcoded executive-summary narrative fragments.

Нужно заменить на:

- generic generators;
- dispatch by domain profile;
- contract-aware rendering from graph projections.


## 13. Перепись biased fragments в skills

### 13.1 Текущая проблема

Часть skills содержит examples, которые задают скрытый domain bias.

### 13.2 Что переписать

В следующих skills заменить кейсовые примеры на мета-принципы:

- `.agent/skills/ec-vp-strategist/SKILL.md`
- `.agent/skills/ec-vp-operator/SKILL.md`
- `.agent/skills/ec-vp-analyst/SKILL.md`
- `.agent/skills/ec-vp-client/SKILL.md`

### 13.3 Принцип замены

Вместо частных примеров использовать:

- flow conservation;
- strategic drift after loss of key module;
- evidence sufficiency for market viability;
- buyer / payer / user decomposition;
- substitutes and switching friction;
- operational buffer and throughput logic.


## 14. Изменения по модулям проекта

Добавить новые модули:

- `app/pipeline/domain_profiler.py`
- `app/pipeline/epistemic_graph.py`
- `app/pipeline/epistemic_projection.py`
- `app/pipeline/decision_readiness.py`
- `app/validation/contract_validator.py`
- `app/validation/fpf_boundary_validator.py`
- `app/validation/fpf_characteristic_validator.py`
- `app/validation/fpf_comparison_validator.py`
- `app/validation/cross_case_contamination_validator.py`
- `app/validation/conflict_validator.py`

Добавить журналы и projections:

- `analysis/epistemic_graph.json`
- `analysis/claims_projection.json`
- `analysis/constraints_projection.json`
- `analysis/assumptions_projection.json`
- `governance/epistemic_ledger.jsonl`
- `governance/contract_audit.jsonl`
- `analysis/debug/llm_raw/*.raw.md`

Изменить существующие модули:

- `app/pipeline/viewpoint_runner.py`
- `app/pipeline/characterization.py`
- `app/pipeline/problem_factory.py`
- `app/pipeline/solution_portfolio.py`
- `app/pipeline/selection_engine.py`
- `app/pipeline/reporting.py`
- `app/llm/client.py`
- `app/router/orchestrator.py`

Ключевое изменение для `solution_portfolio.py`:

- ввести `ParseResult`, `FieldTrust`, `FieldTrustSource`;
- писать `parse_metadata` во frontmatter артефакта;
- различать `trusted` и `degraded` artifact trust level;
- выполнять repair retry до canonical fallback;
- не поднимать inferred/value-translated поля до trusted decision-grade качества.


## 15. Порядок внедрения

### Фаза 1. Быстрое снижение contamination

Сделать:

- ввести `domain_profile.json`;
- добавить `ec-vp-market`;
- убрать hardcoded presales-template из `reporting.py`;
- убрать case-specific ветки из `client.py`.

Результат:

- снизится cross-case contamination;
- появится market-viewpoint;
- reporting станет case-faithful.

### Фаза 2. Граф и ledger

Сделать:

- ввести `epistemic_graph.json`;
- ввести `epistemic_ledger.jsonl`;
- перевести ключевые claims в graph model.

Результат:

- появится referential integrity;
- сохранится история promotion/degradation;
- станет возможен graph-based validation.

### Фаза 3. Projection layer

Сделать:

- реализовать stage-specific projections;
- ограничить LLM contexts только projections.

Результат:

- снизится перегрузка контекстного окна;
- reasoning станет более stage-specific.

### Фаза 4. Контрактная дисциплина

Сделать:

- добавить `contracts/`;
- реализовать `contract_validator`;
- внедрить stage gates.
- внедрить structured parse boundary для `solution_portfolio`;
- блокировать degraded portfolio в `selection_engine`.

Результат:

- unlawful promotion станет машинно фиксируемой ошибкой;
- hard constraints перестанут рождаться из narrative drift.

### Фаза 5. FPF validators и conflict model

Сделать:

- boundary validator;
- evidence validator extension;
- characteristic validator;
- comparison legality validator;
- contamination validator;
- conflict validator.

Результат:

- pipeline начнет проверяться в терминах FPF, а не только по форме markdown.

### Фаза 6. Regression harness

Сделать:

- integration tests for mixed-cases;
- negative tests for contamination;
- negative tests for unlawful constraints;
- negative tests for unresolved contradictions;
- regression checks for market coverage.


## 16. Критерии приемки

Изменение считается принятым, если выполняются условия:

- кейс про один домен не подтягивает narrative fragments и решения из другого домена;
- mixed-case сохраняет несколько reasoning modes;
- `budget`, `time horizon`, `quality threshold`, `capacity limit` не становятся hard constraints без lawful anchor;
- `CHR target` отображается как `normative_target`, а не как факт кейса;
- contradictory claims не протаскиваются в selection как resolved facts;
- reporting умеет явно отделять:
  - факты,
  - интерпретации,
  - гипотезы,
  - assumptions,
  - constraints,
  - normative targets;
- viewpoint coverage включает `market`, если market-side logic релевантна;
- selector и parity не нарушают set-return / no hidden scalarization discipline;
- contract violations логируются в `contract_audit.jsonl`;
- promotion/degradation history восстанавливается по `epistemic_ledger.jsonl`.


## 17. Ожидаемый результат для проекта

После внедрения проект должен перейти:

из

- цепочки генерации markdown-артефактов с локальными доменными шаблонами

в

- контрактно-валидируемый FPF-aware pipeline,
- где reasoning modes composable,
- evidence traceable,
- domain contamination ограничено,
- market/governance/strategy/operations могут сосуществовать в одном кейсе без взаимного разрушения,
- а любой сильный вывод можно разложить назад до lawful chain:
  `source -> graph -> projection -> decision`.
