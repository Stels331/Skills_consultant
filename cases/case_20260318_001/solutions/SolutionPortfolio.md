---
id: case_20260318_001__solution_portfolio
artifact_type: solution_portfolio
stage: solution_factory
state: shaped
parent_refs: ["problems/SelectedProblemCard.md", "problems/ComparisonAcceptanceSpec.md"]
source_refs: ["problems/ComparisonAcceptanceSpec.md:L1"]
evidence_refs: ["problems/SelectedProblemCard.md:L1"]
viewpoints: []
epistemic_status: hypothesis
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pass
violated_principles: []
next_expected_artifacts: ["solutions/ParityReport.md", "solutions/ConflictRecords.md"]
created_at: 2026-03-18T12:27:39.997610+00:00
updated_at: 2026-03-18T12:32:03.122491+00:00
---
# Solution Space Meta-Model

## Weak Intervention Class
- principle: Класс weak-interventions описывает минимально достаточные и обратимые меры, которые меняют правила входа, фильтрацию, маршрутизацию или локальные роли без тяжелой перестройки архитектуры.
- purpose: represent a reusable intervention class, not a case-specific patch
- selection_rule: keep this class in the portfolio only if it adds a distinct pareto profile or a safer rollout path
- instances: sol_01_fix1

## Medium Intervention Class
- principle: Класс medium-interventions описывает меры, которые частично отчуждают повторяемую экспертную функцию в метод, инструмент или отдельный операционный контур, но не требуют полной трансформации системы.
- purpose: represent a reusable intervention class, not a case-specific patch
- selection_rule: keep this class in the portfolio only if it adds a distinct pareto profile or a safer rollout path
- instances: sol_02_fix2

## Strong Intervention Class
- principle: Класс strong-interventions описывает меры, которые меняют саму топологию системы, архитектурные границы, оргструктуру или бизнес-модель, когда локальные меры уже недостаточны.
- purpose: represent a reusable intervention class, not a case-specific patch
- selection_rule: keep this class in the portfolio only if it adds a distinct pareto profile or a safer rollout path
- instances: sol_03_fix3

## sol_00_status_quo
- type: baseline
- assurance_level: low
- anti_goodhart_risk: hidden structural waste remains unmeasured under status quo

## sol_01_fix1
- type: process
- assurance_level: medium
- intervention_force: weak
- relevance_basis: rollout_relevant
- anti_goodhart_risk: process speed can be gamed while quality drifts downstream

## sol_02_fix2
- type: architecture
- assurance_level: high
- intervention_force: medium
- relevance_basis: pareto_relevant
- anti_goodhart_risk: implementation velocity may be optimized at the expense of outcome quality

## sol_03_fix3
- type: hr
- assurance_level: medium
- intervention_force: strong
- relevance_basis: pareto_relevant
- anti_goodhart_risk: staffing metrics may improve without fixing the real bottleneck

