---
id: case_20260318_003__layer_2_requirements
artifact_type: requirements_layer
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
created_at: 2026-03-18T20:30:21.447873+00:00
updated_at: 2026-03-18T20:30:21.447873+00:00
---
```markdown
---
id: layer_2_requirements
artifact_type: layer_model
stage: analysis
state: draft
parent_refs: ["case_20260318_003__normalized_case"]
source_refs: ["raw/TOM GEAR_input.md"]
---

# Layer 2: Requirements Model

## 1. System Context & Scope
The system is a full-cycle wood processing complex designed to operate on a closed-loop energy model. It aims to process roundwood into finished wood products while utilizing its own wood waste (chips) to generate the electricity and heat required for the production processes via a gasification reactor. 
*Note: The gasification component is currently postponed, altering the immediate operational scope.*

## 2. Functional Requirements
*   **REQ-F-01 (Primary Processing):** The system must process roundwood into primary lumber. `[Source: TOM GEAR_input.md - "Лісопильний комплекс"]`
*   **REQ-F-02 (Wood Treatment):** The system must provide vacuum press drying, thermo-modification, and impregnation of wood. `[Source: TOM GEAR_input.md - "Прес вакуумна сушка деревини, термодеревина, імпрегнація"]`
*   **REQ-F-03 (Finished Goods Production):** The system must produce clean moldings (e.g., lining, clean blanks, planking, floorboards, decking). `[Source: TOM GEAR_input.md - "Чистий погонаж"]`
*   **REQ-F-04 (Energy Generation):** The system must convert wood waste (chips) into gas to fuel electrical generators for electricity and heat production. `[Source: TOM GEAR_input.md - "перетворюванні власних відходів... в газогенераційному реакторі"]`
*   **REQ-F-05 (Energy Management):** The system must safely manage and distribute the generated electricity across the complex. `[Source: TOM GEAR_input.md - "Вузол управління електрогенерації та її безпечного розподілу"]`
*   **REQ-F-06 (Secondary Production - Optional):** The system should support small mechanization for producing secondary products like simple pallets and glued moldings from dry/wet wood. `[Source: TOM GEAR_input.md - "ДОДАТКОВІ ОПЦІЇ"]`

## 3. Performance & Capacity Requirements
*   **REQ-P-01 (Power Generation Capacity):** The gasification and generation unit must produce 700 kW of electricity per hour. `[Source: TOM GEAR_input.md - "генерації 700 кВт електроенергії в годину"]`
*   **REQ-P-02 (Raw Material Input):** The system requires a minimum input of 1,500 m³ of wood per month to generate sufficient waste for the 700 kW/h power generation. `[Source: TOM GEAR_input.md - "кількість деревини на вході від 1500 м куб в місяць"]`
*   **REQ-P-03 (Sawmill Capacity):** The sawmill section must process 1,500 m³ of roundwood per month, operating over 22-24 shifts. `[Source: TOM GEAR_input.md - "Лісопильний 1500 м куб в місяць ( 22-24 робочих зміни)"]`
*   **REQ-P-04 (Treatment Capacity):** The drying and impregnation section must process up to 1,000 m³ per month, operating over 30 calendar days. `[Source: TOM GEAR_input.md - "до 1000 м куб в місяць ( 30 календарних дні)"]`
*   **REQ-P-05 (Moldings Capacity):** The clean moldings section must produce up to 500 m³ per month, operating over 22-24 shifts. `[Source: TOM GEAR_input.md - "До 500 м куб в місяць ( 22-24 робочих зміни)"]`

## 4. Constraints & Risks
*   **CON-01 (Energy Strategy Halted):** The implementation of the gasification unit is officially postponed, resulting in a loss of the core value proposition (energy independence). `[Source: TOM GEAR_input.md - "Відмова від реалізації газогенерації. Перенос на пізніше"]`
*   **CON-02 (Raw Material Supply):** Procurement is constrained by a transforming market, making it difficult to acquire high-quality raw materials at adequate prices. `[Source: TOM GEAR_input.md - "Труднощі з придбанням якісної сировино по адекватним цінам"]`
*   **CON-03 (Labor Shortage):** There is a critical constraint regarding the availability and qualification of labor resources. `[Source: TOM GEAR_input.md - "Питання трудових ресурсів, і їхньої кваліфікації"]`
*   **CON-04 (Financial Instability):** The project faces financial instability and the external investment strategy has failed. `[Source: TOM GEAR_input.md - "фінансова не стабільність", "Не спрацювала зовнішня інвестиційна стратегія"]`
*   **CON-05 (Governance & Team Dynamics):** Internal communication is broken, characterized by a loss of trust, internal competition among board members, and failure to honor agreements. `[Source: TOM GEAR_input.md - "Порушення внутрішньої комунікації", "Втрата довіри", "Внутрішня конкуренція"]`

## 5. Explicit Gaps
*   **GAP-01 (Energy Consumption Metrics):** The exact power consumption requirements for the sawmill, drying, and molding sections are not specified. It is unknown if the target 700 kW/h generation perfectly matches, exceeds, or falls short of the complex's operational needs.
*   **GAP-02 (Financial Requirements):** There are no specified budgetary constraints, target unit economics, ROI expectations, or break-even financial targets.
*   **GAP-03 (Quality Standards):** Specific quality standards, grades, or certifications required for the finished wood products (moldings, thermo-wood) are missing.
*   **GAP-04 (Alternative Energy Sourcing):** Since the gasification unit is postponed (CON-01), there are no requirements defining the alternative grid connection or external power sourcing needed to run the test launches and initial operations.
```
