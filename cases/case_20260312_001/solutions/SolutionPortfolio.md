---
id: case_20260312_001__solution_portfolio
artifact_type: solution_portfolio
stage: solution_factory
state: shaped
parent_refs: ["problems/SelectedProblemCard.md", "problems/ComparisonAcceptanceSpec.md"]
source_refs: ["problems/ComparisonAcceptanceSpec.md:L1"]
evidence_refs: ["problems/SelectedProblemCard.md:L1"]
viewpoints: []
epistemic_status: observed
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: degrade
violated_principles: []
next_expected_artifacts: ["solutions/ParityReport.md", "solutions/ConflictRecords.md"]
created_at: 2026-03-12T10:21:41.048211+00:00
updated_at: 2026-03-12T10:28:00.218161+00:00
---
## sol_00_status_quo
- type: policy
- assurance_level: high

## sol_01_nqd_explore_historical_proxy
- type: process
- assurance_level: medium

## sol_02_exploit_cpq_calculator
- type: it
- assurance_level: medium

## sol_03_radical_productization_and_presale_buffer
- type: architecture
- assurance_level: low
- presale: инженер забирает на себя всю техническую проработку, расчет себестоимости и подготовку спецификаций. ТД полностью исключается из процесса прямого общения с продажами и лишь асинхронно аппрувит готовые расчеты Presale-инженера (затраты времени ТД снижаются до 1-2 часов в неделю).

