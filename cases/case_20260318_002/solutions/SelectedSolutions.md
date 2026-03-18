---
id: case_20260318_002__selectedsolutions
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
created_at: 2026-03-18T13:25:02.312043+00:00
updated_at: 2026-03-18T13:25:02.312043+00:00
---
## Selected Solutions

- sol_00_status_quo
- sol_02_offtake_monetization

## Decision Status

- decision_ready_for_execution

## Recommendation Status

- confirmed_action: sol_00_status_quo
- confirmed_action: sol_02_offtake_monetization

## Selection Rationale

- Ниже представлены результаты работы Selection Engine. На основе жестких ограничений (Hard Constraints) из `ComparisonAcceptanceSpec.md` и анализа конфликтов, было принято решение использовать **гибридную (двухфазную) стратегию**, так как ни одно из решений по отдельности не способно одновременно остановить немедленный cash burn (счет на дни) и вернуть предприятие к целевой бизнес-модели (термодерево).
- Для удовлетворения жестких ограничений спецификации приемки выбрана двухфазная комбинация решений:
- 1. **Фаза 1 (Выживание): `sol_01_commodity_pivot
- **Обоснование:** Проблема имеет критический срок годности (счет на дни до банкротства или физической остановки). Данное решение немедленно обнуляет `CHR-01-ENERGY-OPEX` (остановка сушилок) и позволяет направить высвобожденные средства на вывоз отходов (`CHR-02-WASTE-ACCUM = 0`). Маржинальность на сырой доске составит >15%. Это покупает время для реализации Фазы 2.

## traceability
- sol_00_status_quo <- problems/ComparisonAcceptanceSpec.md:L1
- sol_02_offtake_monetization <- problems/ComparisonAcceptanceSpec.md:L1
- parity <- solutions/ParityReport.md:L1
- conflicts <- solutions/ConflictRecords.md:L1

