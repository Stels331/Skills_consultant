# Electronic Consultant v3 — RECAP

Дата обновления: 2026-03-03

## 1) Текущий статус

- Проект: `electronic_consultant_v3/`
- База требований: `electronic_consultant_v3_FINAL_TZ.md`
- План работ: `Tasks_v3_FINAL/`

Спринты:
- Sprint 01: выполнен, доработан по замечаниям (включая principles + semantic judge).
- Sprint 02: выполнен, доработан по замечаниям (LLM-обвязка для layers/viewpoints + skills).
- Sprint 03: выполнен, доработан по замечаниям (убран хардкод characterization, unified skills, усилен problem-factory prompt).
- Sprint 04: выполнен (Solution Factory + Conflict Router + Selection + ADR/Runbook/Rollback).
- Sprint 05: выполнен (Evidence Graph + Assurance Engine + Valid-Until Refresh).
- Sprint 06: выполнен (Reporting Contracts + Validation Matrix + Feedback Loop).
- Sprint 07: выполнен (NFR + Observability + Performance + Integration Harness).
- Sprint 08: выполнен (Pilot + Hardening + Release Readiness + Handover).

## 2) Что уже реализовано (коротко)

### Sprint 01
- Artifact contract schema + validator.
- State machine для артефактов.
- Orchestrator skeleton + DecisionLog.
- Principles library loader.
- Semantic judge (`local/openai`) и интеграция в gate.

Ключевые файлы:
- `app/validation/artifact_contract_validator.py`
- `app/state/state_machine.py`
- `app/router/orchestrator.py`
- `app/principles/library.py`
- `app/validation/semantic_judge.py`

### Sprint 02
- Intake parser (`raw -> intake/parsed`).
- LLM-driven 4-layer builder (`local/openai`).
- LLM-driven viewpoint runner (6 viewpoints + conflicts index).
- Добавлены viewpoint skills `ec-vp-*` и `ec-layer-modeler`.

Ключевые файлы:
- `app/pipeline/intake_parser.py`
- `app/pipeline/layer_builder.py`
- `app/pipeline/viewpoint_runner.py`
- `app/llm/client.py`

### Sprint 03
- Characterization stage: Passport, IndicatorSet, ParityPlan, CharacteristicCards (через LLM-обвязку).
- Problem factory: Archive, Portfolio, SelectedProblemCard, ComparisonAcceptanceSpec.
- Stage guard: запрет входа в `solution_factory` без обязательных problem-артефактов.
- Удалены дубликаты skill-папок `*-v3`, оставлены canonical имена.
- Усилен `ec-problem-factory/SKILL.md` (Role-Method-Work, анти-психологизация).

Ключевые файлы:
- `app/pipeline/characterization.py`
- `app/pipeline/problem_factory.py`
- `app/router/orchestrator.py`
- `.agent/skills/ec-characterization/SKILL.md`
- `.agent/skills/ec-problem-factory/SKILL.md`

### Sprint 04
- Solution Portfolio Generator (>=3 альтернатив + обязательный `status_quo`) с валидациями разнообразия и `assurance_level`.
- Parity/Tradeoff engine (`ParityPlan.md`, `ParityReport.md`, `TradeoffTable.md`).
- Rule-based Conflict Router с controlled fallback для неподдержанных типов конфликтов.
- Selection Engine (строгие prerequisites parity+conflicts+acceptance spec, 1..3 selected), выпуск:
  - `solutions/SelectedSolutions.md`
  - `decisions/ADR-001.md`
  - `operation/Runbook.md`
  - `operation/RollbackPlan.md`
- Добавлены skills:
  - `.agent/skills/ec-solution-generator/SKILL.md`
  - `.agent/skills/ec-conflict-router/SKILL.md`
  - `.agent/skills/ec-solution-selector/SKILL.md`

Ключевые файлы:
- `app/pipeline/solution_portfolio.py`
- `app/pipeline/parity_tradeoff.py`
- `app/pipeline/conflict_router.py`
- `app/pipeline/selection_engine.py`
- `app/pipeline/solution_factory.py`
- `tests/test_solution_factory_pipeline.py`

### Sprint 05
- Внедрен `Evidence Graph` и claim-классификация:
  - claim classes: `stated_by_user`, `observed`, `inferred`, `hypothesis`, `tested`, `decision_grade`, `operationally_confirmed`.
  - auto-classification claims из артефакта.
  - inheritance/degradation эпистемического статуса (комбинация с более слабым claim понижает общий статус).
  - экспорт:
    - `evidence/evidence_graph.md` (contract-valid markdown artifact)
    - `evidence/evidence_graph.json` (machine-readable index)
- Добавлен `Assurance Engine`:
  - уровни `low/medium/high`, score, policy issues.
  - правило: `high assurance` без `evidence_refs` -> `block`.
  - правило: `decision_grade` без `evidence_refs` -> `block`.
  - устаревший (`valid_until`) артефакт понижает/блокирует gate.
- Интеграция в `StageOrchestrator`:
  - checks: `evidence_graph`, `assurance_engine`, `freshness_policy`.
  - DecisionLog включает блоки `evidence_graph`, `assurance_engine`, `freshness`.
  - `recheck_trigger` вызывает refresh workflow и влияет на gate (`degrade`).
- Реализована `Refresh Orchestration`:
  - при истечении `valid_until` артефакт помечается как `expired`.
  - автоматически создаются:
    - `evidence/refresh_report.md` (contract-valid markdown artifact)
    - `evidence/refresh_index.json`
  - фиксируется `refresh_target_stage` (characterization/problem_factory/solution_factory) и причина recheck.

Ключевые файлы:
- `app/evidence/graph.py`
- `app/validation/assurance_engine.py`
- `app/refresh/orchestrator.py`
- `app/router/orchestrator.py`
- `app/state/state_machine.py`
- `tests/test_evidence_assurance_refresh.py`

### Sprint 06
- Реализован reporting pipeline:
  - `reports/Analytical_Full_Report.md` с 19 обязательными разделами (rule-based section mapping `section -> artifact`).
  - `reports/Executive_Summary.md` с 10 обязательными разделами.
  - Запрет raw reasoning/chain-of-thought в отчетах.
  - Частичные данные маркируются явными `GAP` блоками.
- Реализована Validation Matrix (hard fail / warning-degrade / waive):
  - hard fail блокирует переход;
  - degrade с waivable warnings может быть переведен в pass только при policy-controlled waive;
  - waive требует `waive_policy_id`, `waive_owner`, `waive_rationale`.
- Реализован feedback loop re-entry:
  - анализ `operation/ImpactMeasurement.json`;
  - при недостижении эффекта автоматически создается re-entry trigger;
  - orchestrator фиксирует это в DecisionLog и инициирует refresh event.
- Интеграция в orchestrator:
  - новый check `validation_matrix`;
  - логирование блока `validation_matrix` в DecisionLog;
  - поддержка перехода в `waived` state при policy-controlled waive.

Ключевые файлы:
- `app/pipeline/reporting.py`
- `app/validation/validation_matrix.py`
- `app/router/orchestrator.py`
- `scripts/run_reporting.py`
- `tests/test_reporting_gate_policy.py`

### Sprint 07
- Observability + audit trail:
  - structured stage events (`governance/stage_events.jsonl`) в orchestrator;
  - агрегатор аудита кейса с выгрузкой:
    - `reports/audit_trail.md`
    - `reports/audit_trail.json`
  - CLI диагностика stage:
    - `scripts/build_audit_trail.py`
    - `scripts/diagnose_stage.py`
- Performance/token discipline:
  - fast-path reuse в orchestrator для `accepted_for_next_stage` + fresh артефактов (`allow_reuse=true`);
  - измерение `duration_ms` на stage в structured events;
  - dependency graph и инкрементальный recheck:
    - `app/pipeline/dependencies.py`
    - `scripts/run_incremental.py`
- Integration harness + quality metrics:
  - fixtures минимум на 10 кейсов (`tests/integration/fixtures/*.md`);
  - автоматический suite:
    - `app/testing/integration_suite.py`
    - `scripts/run_integration_suite.py`
  - агрегированные отчеты:
    - `reports/integration_quality_report.md`
    - `reports/integration_quality_report.json`
  - метрики: completeness/coherence/evidence_strength/actionability + hard_fail_detection_rate.

Ключевые файлы:
- `app/observability/audit.py`
- `app/router/orchestrator.py`
- `app/pipeline/dependencies.py`
- `app/testing/integration_suite.py`
- `tests/test_nfr_observability.py`

### Sprint 08
- Pilot run + gap register:
  - пилотный прогон по целевым workspace;
  - case-level `reports/pilot_report.md`;
  - общий реестр разрывов:
    - `governance/pilot_gap_register.md`
    - `governance/pilot_gap_register.json`
  - классификация gap: functional / quality / process / documentation, с owner/priority.
- Hardening + risk closure:
  - сбор и фиксация risk register из pilot gaps:
    - `governance/risk_register.md`
    - `governance/risk_register.json`
  - статусы mitigations по high/medium рискам.
- Release package + operational handover:
  - формальный go/no-go decision:
    - `governance/GO_NO_GO_DECISION.json`
  - release/handover документы:
    - `RELEASE_NOTES_v3.md`
    - `OPERATIONS_RUNBOOK.md`
    - `GO_NO_GO_CHECKLIST.md`
    - `POST_RELEASE_IMPROVEMENTS.md`
  - dry-run release сценария автоматизирован скриптами.

Ключевые файлы:
- `app/release/pilot.py`
- `app/release/release_package.py`
- `scripts/run_pilot.py`
- `scripts/close_risks.py`
- `scripts/prepare_release_package.py`
- `tests/test_pilot_release_hardening.py`

## 3) Актуальные canonical skills

- `.agent/skills/ec-orchestrator/SKILL.md`
- `.agent/skills/ec-extraction/SKILL.md`
- `.agent/skills/ec-layer-modeler/SKILL.md`
- `.agent/skills/ec-characterization/SKILL.md`
- `.agent/skills/ec-problem-factory/SKILL.md`
- `.agent/skills/ec-solution-factory/SKILL.md`
- `.agent/skills/ec-vp-strategist/SKILL.md`
- `.agent/skills/ec-vp-analyst/SKILL.md`
- `.agent/skills/ec-vp-operator/SKILL.md`
- `.agent/skills/ec-vp-architect/SKILL.md`
- `.agent/skills/ec-vp-critic/SKILL.md`
- `.agent/skills/ec-vp-client/SKILL.md`

## 4) CLI точки входа

- `python3 scripts/run_intake.py <workspace_id>`
- `python3 scripts/run_layers.py <workspace_id> --mode local|openai`
- `python3 scripts/run_viewpoints.py <workspace_id> --mode local|openai`
- `python3 scripts/run_characterization.py <workspace_id> --mode local|openai`
- `python3 scripts/run_problem_factory.py <workspace_id> --mode local|openai`
- `python3 scripts/run_solution_portfolio.py <workspace_id> --mode local|openai`
- `python3 scripts/run_parity_tradeoff.py <workspace_id> --mode local|openai`
- `python3 scripts/run_conflict_router.py <workspace_id> --mode local|openai`
- `python3 scripts/run_selection.py <workspace_id> --mode local|openai`
- `python3 scripts/run_solution_factory.py <workspace_id> --mode local|openai`
- `python3 scripts/run_reporting.py <workspace_id>`
- `python3 scripts/build_audit_trail.py <workspace_id>`
- `python3 scripts/diagnose_stage.py <workspace_id> <stage_name>`
- `python3 scripts/run_incremental.py <workspace_id> <changed_stage>`
- `python3 scripts/run_integration_suite.py`
- `python3 scripts/run_pilot.py [workspace_id ...]`
- `python3 scripts/close_risks.py`
- `python3 scripts/prepare_release_package.py`
- `python3 scripts/run_stage.py <workspace_id> <stage>`
- `python3 scripts/validate_workspace.py <workspace_id>`

## 5) Тестовый статус

Последний полный прогон:
- `python3 -m unittest discover -s tests -p 'test_*.py'`
- Результат: `60/60 OK`

## 6) Что делать дальше

Следующий этап: релизная эксплуатация и post-release цикл улучшений.

## 7) Минимальный контекст для продолжения

Для новой сессии достаточно:
- `electronic_consultant_v3_FINAL_TZ.md`
- `Tasks_v3_FINAL/Sprint_0X...` (текущий спринт)
- `electronic_consultant_v3/RECAP.md`
