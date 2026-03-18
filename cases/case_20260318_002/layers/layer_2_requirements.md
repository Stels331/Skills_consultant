---
id: case_20260318_002__layer_2_requirements
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
created_at: 2026-03-18T13:07:28.508944+00:00
updated_at: 2026-03-18T13:07:28.508944+00:00
---
```markdown
---
id: layer_2_requirements_case_20260318_002
artifact_type: layer_2_requirements
stage: analysis
state: draft
parent_refs: ["case_20260318_002__normalized_case"]
source_refs: ["raw/TOM GEAR_input.md"]
---

# Layer 2: Requirements Model

## 1. Business Requirements (BR)
*   **BR-01: Full-Cycle Processing:** Establish a full-cycle wood processing complex utilizing its own waste for energy generation. `[Source: TOM GEAR_input.md: "Лісопереробний комплекс повного циклу переробки деревини..."]`
*   **BR-02: Energy Independence (Postponed):** Generate electricity and heat for the complex's production processes by converting wood waste (chips) into gas via a gas generation reactor. *Note: Currently postponed, resulting in a loss of the initial value proposition.* `[Source: TOM GEAR_input.md: "Відмова від реалізації газогенерації. Перенос на пізніше..."]`
*   **BR-03: Financial Viability:** Reach the break-even point, stabilize production, and enable future scaling and development. `[Source: TOM GEAR_input.md: "Вихід на точку беззбитковості. Масштабування та розвиток."]`

## 2. Functional Requirements (FR)
*   **FR-01: Sawmill Operations:** The sawmill section must be capable of processing 1500 m³ of roundwood per month. `[Source: TOM GEAR_input.md: "Лісопильний комплекс робочою потужністю 1500 м куб кругляка в місяць"]`
*   **FR-02: Wood Drying and Treatment:** The drying section must perform vacuum press drying, thermo-wood processing, and impregnation for up to 1000 m³ of wood per month. `[Source: TOM GEAR_input.md: "Прес вакуумна сушка деревини, термодеревина, імпрегнація деревини до 1000 м куб в місяць"]`
*   **FR-03: Finished Moldings Production:** The molding section must produce up to 500 m³ of clean moldings (lining, decking, floorboards, etc.) per month. `[Source: TOM GEAR_input.md: "Чистий погонаж... До 500 м куб в місяць"]`
*   **FR-04: Auxiliary Production:** The facility must support the production of additional products (e.g., simple pallets, glued moldings) from dry and wet wood via small mechanization. `[Source: TOM GEAR_input.md: "Можливість виробництва іншої продукції... шляхом малої механізації"]`
*   **FR-05: Power Generation & Distribution (Postponed):** The system must include a gas generation unit and a control node for safe electricity distribution. `[Source: TOM GEAR_input.md: "ГАЗОГЕНЕРАЦІЙНА УСТАНОВКА... Вузол управління електрогенерації та її безпечного розподілу."]`

## 3. Non-Functional Requirements (NFR)
*   **NFR-01: Operational Schedule (Sawmill & Moldings):** The sawmill and molding sections must operate on a schedule of 22-24 shifts per month. `[Source: TOM GEAR_input.md: "( 22-24 робочих зміни)"]`
*   **NFR-02: Operational Schedule (Drying):** The drying and treatment section must operate continuously for 30 calendar days a month. `[Source: TOM GEAR_input.md: "( 30 календарних дні)"]`
*   **NFR-03: Energy Output Capacity:** The gas generation unit must be capable of generating 700 kW of electricity per hour. `[Source: TOM GEAR_input.md: "Для забезпечення генерації 700 кВт електроенергії в годину"]`
*   **NFR-04: Waste Input Capacity:** The system requires a minimum input of 1500 m³ of wood waste per month to sustain the 700 kW/h energy generation. `[Source: TOM GEAR_input.md: "розрахована потрібна кількість відходів, тобто кількість деревини на вході від 1500 м куб в місяць"]`

## 4. Constraints (C)
*   **C-01: Financial Instability:** The project suffers from financial instability and the failure of the external investment strategy. `[Source: TOM GEAR_input.md: "фінансова не стабільність", "Не спрацювала зовнішня інвестиційна стратегія"]`
*   **C-02: Raw Material Market:** There are significant difficulties in acquiring high-quality raw materials at adequate prices due to market transformation and redistribution. `[Source: TOM GEAR_input.md: "Труднощі з придбанням якісної сировино по адекватним цінам."]`
*   **C-03: Labor Shortage:** There is a lack of available labor resources and qualified personnel. `[Source: TOM GEAR_input.md: "Питання трудових ресурсів, і їхньої кваліфікації."]`
*   **C-04: Organizational/Governance Issues:** Internal communication is broken, there is internal competition for decision-making among board members, and a general loss of trust in the implementation team. `[Source: TOM GEAR_input.md: "Порушення внутрішньої комунікації", "Внутрішня конкуренція за останнє слово", "Втрата довіри і віри в команду"]`

## 5. Gaps & Missing Information
*   **GAP-01: Alternative Energy Source:** Since the gas generation unit is postponed, there is no requirement or specification defining the alternative power source (e.g., grid connection capacity, diesel generators) to run the sawmill and drying sections.
*   **GAP-02: Financial Targets:** Specific financial requirements (e.g., total budget, target ROI, break-even timeline) are missing.
*   **GAP-03: Labor Requirements:** The exact headcount and specific qualifications required to operate the 22-24 shifts and continuous drying processes are not defined.
*   **GAP-04: Equipment Specifications:** Specific models, brands, or technical specifications for the sawmill, vacuum presses, and molding machinery are not detailed.
```
