---
id: case_20260318_002__layer_3_functional_model
artifact_type: functional_model_layer
stage: layers
state: draft
parent_refs: ["intake/normalized_case.md"]
source_refs: ["intake/normalized_case.md:L1"]
evidence_refs: []
viewpoints: []
epistemic_status: observed
assurance_level: medium
valid_until: 2026-12-31
owner_role: analyst
gate_status: pending
violated_principles: []
next_expected_artifacts: ["viewpoints/strategist.md"]
created_at: 2026-03-18T13:07:50.598637+00:00
updated_at: 2026-03-18T13:07:50.598637+00:00
---
```markdown
---
id: layer_3_functional_model_case_20260318_002
artifact_type: layer_model
layer: 3
title: Layer 3 - Functional Model
status: draft
---

# Layer 3: Functional Model

## 1. Core System Functions

Based on the normalized case, the system is divided into distinct functional blocks representing the full cycle of wood processing and energy generation.

*   **SF.01: Raw Wood Processing (Sawing)**
    *   *Description:* Initial breakdown of round timber into sawn lumber.
    *   *Capacity:* 1500 m³ per month (22-24 shifts).
    *   *Traceability:* `[Source: TOM GEAR_input.md - "Лісопильний 1500 м куб в місяць"]`
*   **SF.02: Wood Drying and Treatment**
    *   *Description:* Moisture removal and chemical/thermal modification (vacuum press drying, thermo-wood processing, impregnation).
    *   *Capacity:* Up to 1000 m³ per month (30 calendar days).
    *   *Traceability:* `[Source: TOM GEAR_input.md - "Прес вакуумна сушка деревини, термодеревина, імпрегнація"]`
*   **SF.03: Finished Goods Manufacturing (Molding/Profiling)**
    *   *Description:* Production of clean moldings, lining, decking, floorboards, and planks.
    *   *Capacity:* Up to 500 m³ per month (22-24 shifts).
    *   *Traceability:* `[Source: TOM GEAR_input.md - "Чистий погонаж... До 500 м куб в місяць"]`
*   **SF.04: Waste-to-Energy Conversion (Gasification)**
    *   *Description:* Conversion of wood waste (chips) into gas via a gasification reactor, followed by electricity and heat generation.
    *   *Target Output:* 700 kW/h.
    *   *Status:* Currently postponed (implementation delayed).
    *   *Traceability:* `[Source: TOM GEAR_input.md - "ГАЗОГЕНЕРАЦІЙНА УСТАНОВКА", "Відмова від реалізації газогенерації. Перенос на пізніше"]`
*   **SF.05: Power and Heat Distribution**
    *   *Description:* Control node for the safe distribution of generated electricity and thermal energy to the production facilities.
    *   *Traceability:* `[Source: TOM GEAR_input.md - "Вузол управління електрогенерації та її безпечного розподілу"]`
*   **SF.06: Auxiliary Manufacturing (Small Mechanization)**
    *   *Description:* Production of secondary products (simple pallets, glued moldings) from dry and wet wood.
    *   *Traceability:* `[Source: TOM GEAR_input.md - "ДОДАТКОВІ ОПЦІЇ"]`

## 2. Functional Flows and Interactions

*   **Material Flow:**
    *   Raw Timber (1500 m³) $\rightarrow$ **[SF.01]** $\rightarrow$ Sawn Timber $\rightarrow$ **[SF.02]** $\rightarrow$ Treated/Dried Timber $\rightarrow$ **[SF.03]** $\rightarrow$ Finished Products.
*   **Waste Flow:**
    *   Wood Waste/Chips from **[SF.01]**, **[SF.03]**, and **[SF.06]** $\rightarrow$ **[SF.04]** Gasification Reactor.
*   **Energy Flow:**
    *   **[SF.04]** Generators $\rightarrow$ Electricity & Heat $\rightarrow$ **[SF.05]** Control Node $\rightarrow$ Power supply for **[SF.01]**, **[SF.02]**, **[SF.03]**, and **[SF.06]**.

## 3. Identified Functional Gaps

*   **GAP.F.01 (Waste Management Logic):** There is no functional description of how wood waste (chips) is collected, transported, and buffered between the production lines (SF.01, SF.03) and the gasification reactor (SF.04).
*   **GAP.F.02 (Hybrid Power Operation):** Since the gasification unit (SF.04) is postponed, the functional logic for operating the plant on external grid power (or hybrid mode) is missing. The control node (SF.05) lacks functional specifications for grid synchronization or failover.
*   **GAP.F.03 (Quality Control Functions):** The case mentions "Контрольований контроль якості" (Controlled quality control) as a future stage, but specific functional requirements for quality inspection stations within the material flow are not defined.
*   **GAP.F.04 (Thermal Energy Distribution):** The case mentions using thermal energy for production (likely for SF.02 Drying), but the functional flow and heat exchange mechanisms between the generators and the drying kilns are not specified.
```
