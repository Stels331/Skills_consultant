---
id: case_20260317_001__selectedsolutions
artifact_type: selected_solutions
stage: solution_factory
state: draft
parent_refs: ["solutions/SolutionPortfolio.md", "solutions/ParityReport.md", "solutions/ConflictRecords.md", "problems/ComparisonAcceptanceSpec.md"]
source_refs: ["solutions/ParityReport.md:L1"]
evidence_refs: ["solutions/ConflictRecords.md:L1"]
viewpoints: []
epistemic_status: decision_grade
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: ["decisions/ADR-001.md"]
created_at: 2026-03-18T12:56:52.862392+00:00
updated_at: 2026-03-18T12:56:52.862392+00:00
---
## Selected Solutions

- sol_02_shadow_mode_matrix
- sol_03_l1_estimator_gate

## Decision Status

- decision_ready_for_execution

## Recommendation Status

- confirmed_action: sol_02_shadow_mode_matrix
- confirmed_action: sol_03_l1_estimator_gate

## Rejected Alternatives

- sol_00_status_quo: dominated_or_constraint_failing
- reason: sol_00_status_quo (preserves bottleneck and hidden losses)
- sol_04_client_cpq_portal: rollout_relevant_not_primary
- reason: sol_04_client_cpq_portal (fails current budget and rollout discipline)
- sol_01_intake_brief_and_triage: rollout_relevant_not_primary
- reason: sol_01_intake_brief_and_triage (useful as a low-force step, but weaker than the selected staged path)

## traceability
- sol_02_shadow_mode_matrix <- problems/ComparisonAcceptanceSpec.md:L1
- sol_03_l1_estimator_gate <- problems/ComparisonAcceptanceSpec.md:L1
- parity <- solutions/ParityReport.md:L1
- conflicts <- solutions/ConflictRecords.md:L1

