---
id: case_20260317_001__solution_portfolio
artifact_type: solution_portfolio
stage: solution_factory
state: draft
parent_refs: ["problems/SelectedProblemCard.md", "problems/ComparisonAcceptanceSpec.md"]
source_refs: ["problems/ComparisonAcceptanceSpec.md:L1"]
evidence_refs: ["problems/SelectedProblemCard.md:L1"]
viewpoints: []
epistemic_status: observed
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: ["solutions/ParityReport.md", "solutions/ConflictRecords.md"]
created_at: 2026-03-18T12:56:52.855997+00:00
updated_at: 2026-03-18T12:56:52.855997+00:00
---
# Solution Space Meta-Model

## Weak Intervention Class
- principle: Класс weak-interventions описывает минимально достаточные и обратимые меры, которые меняют правила входа, фильтрацию, маршрутизацию или локальные роли без тяжелой перестройки архитектуры.
- purpose: represent a reusable intervention class, not a case-specific patch
- selection_rule: keep this class in the portfolio only if it adds a distinct pareto profile or a safer rollout path
- instances: sol_01_intake_brief_and_triage

## Medium Intervention Class
- principle: Класс medium-interventions описывает меры, которые частично отчуждают повторяемую экспертную функцию в метод, инструмент или отдельный операционный контур, но не требуют полной трансформации системы.
- purpose: represent a reusable intervention class, not a case-specific patch
- selection_rule: keep this class in the portfolio only if it adds a distinct pareto profile or a safer rollout path
- instances: sol_02_shadow_mode_matrix

## Strong Intervention Class
- principle: Класс strong-interventions описывает меры, которые меняют саму топологию системы, архитектурные границы, оргструктуру или бизнес-модель, когда локальные меры уже недостаточны.
- purpose: represent a reusable intervention class, not a case-specific patch
- selection_rule: keep this class in the portfolio only if it adds a distinct pareto profile or a safer rollout path
- instances: sol_03_l1_estimator_gate, sol_04_client_cpq_portal

## sol_00_status_quo
- type: baseline
- assurance_level: low
- anti_goodhart_risk: hidden cost stays invisible because no one changes the metric frame
- solves_which_problems: none
- assumptions: keep all quotations on the Technical Director
- expected_effects: preserves current bottleneck and hidden cost
- risks: continued queue growth, client loss, production distraction
- constraints: no structural change
- required_capabilities: existing only
- reversibility: n/a
- affected_viewpoints: strategist, operator, analyst
- evidence_refs: problems/SelectedProblemCard.md:L1

## sol_01_intake_brief_and_triage
- type: process
- assurance_level: high
- intervention_force: weak
- relevance_basis: rollout_relevant
- anti_goodhart_risk: team may optimize form completion while poor qualification logic remains hidden
- solves_which_problems: moderate
- assumptions: part of the noise can be removed before expert escalation
- expected_effects: reduces meaningless expert interruptions with minimal organizational force
- risks: cosmetic compliance without real filtering discipline
- constraints: requires clear qualification gate and owner enforcement
- required_capabilities: sales lead + operations owner
- reversibility: high
- affected_viewpoints: operator, analyst, client
- evidence_refs: problems/ComparisonAcceptanceSpec.md:L1

## sol_02_shadow_mode_matrix
- type: process
- assurance_level: medium
- intervention_force: medium
- relevance_basis: pareto_relevant
- anti_goodhart_risk: team may optimize matrix match score while ignoring real downstream profitability
- solves_which_problems: high
- assumptions: expert knowledge can be partially externalized and checked in shadow mode
- expected_effects: safer learning path toward later delegation of standard quotation work
- risks: slow initial effect and possible expert resistance
- constraints: requires disciplined dual-run pilot
- required_capabilities: analyst + Technical Director + sales lead
- reversibility: medium-high
- affected_viewpoints: operator, analyst, critic
- evidence_refs: problems/ComparisonAcceptanceSpec.md:L1

## sol_03_l1_estimator_gate
- type: process
- assurance_level: medium
- intervention_force: strong
- relevance_basis: pareto_relevant
- anti_goodhart_risk: managers may game qualification or force-fit complex work into standard categories for speed
- solves_which_problems: strong
- assumptions: standard requests can be separated from custom engineering work and delegated after calibration
- expected_effects: major reduction in response time and expert load
- risks: misclassification and margin error if delegated too early
- constraints: requires qualification gate and accuracy control
- required_capabilities: sales ops + L1 estimator + governance owner
- reversibility: medium
- affected_viewpoints: operator, client, strategist
- evidence_refs: problems/ComparisonAcceptanceSpec.md:L1

## sol_04_client_cpq_portal
- type: architecture
- assurance_level: low
- intervention_force: strong
- relevance_basis: pareto_relevant
- anti_goodhart_risk: portal may optimize throughput metrics while degrading deal quality and client fit
- solves_which_problems: medium
- assumptions: the request space is standardized enough for self-service
- expected_effects: radical acceleration for standard requests
- risks: high implementation cost and weak adoption fit
- constraints: integration burden is real; budget burden must be confirmed from actual business input before final rejection
- required_capabilities: architect + product owner + implementation team
- reversibility: low
- affected_viewpoints: architect, strategist, client
- evidence_refs: problems/ComparisonAcceptanceSpec.md:L1
- _generated_by_local: llm mode.

