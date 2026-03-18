---
id: case_20260317_001__layer_4_allocation_model
artifact_type: allocation_model_layer
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
created_at: 2026-03-17T18:46:23.014354+00:00
updated_at: 2026-03-17T18:46:23.014354+00:00
---
```markdown
---
id: layer_4_allocation_model
artifact_type: layer_model
stage: analysis
state: draft
parent_refs: ["case_20260317_001__normalized_case"]
source_refs: ["raw/Технический директор_input.md:L1"]
---

# Layer 4: Allocation Model

## 1. Actors and Roles
*   **Менеджер із продажів (Sales Manager)**
    *   *Allocated Responsibilities:* Finding clients, receiving requests, transferring requests to the Technical Director, negotiating contracts with clients based on estimates, launching orders into production. [raw/Технический директор_input.md:L1]
*   **Технічний директор (Technical Director)**
    *   *Allocated Responsibilities:* Estimating orders (feasibility, scope, price, deadlines), production management, urgent tasks, supply, equipment setup, and other operational issues. [raw/Технический директор_input.md:L1]
    *   *Allocated KPIs:* Production volume, product quality. [raw/Технический директор_input.md:L1]
    *   *Allocated Regulations:* Job description and internal standards mandate participation in contract preparation and order estimation. [raw/Технический директор_input.md:L1]
*   **Клієнт (Client)**
    *   *Allocated Responsibilities:* Submitting requests, reviewing estimates/terms, approving or canceling orders. [raw/Технический директор_input.md:L1]

## 2. IT Systems and Applications
*   **GAP:** No IT systems, software, CRM, or ERP tools are explicitly mentioned for managing requests, estimates, or production. It is unclear how data is transferred between the Sales Manager and the Technical Director.

## 3. Data and Artifacts
*   **Заявка на виготовлення продукції (Production Request)**
    *   *Source:* Client -> Sales Manager -> Technical Director. [raw/Технический директор_input.md:L1]
*   **Оцінка замовлення (Order Estimate)**
    *   *Contains:* Feasibility, scope, price, deadlines.
    *   *Source:* Technical Director -> Sales Manager. [raw/Технический директор_input.md:L1]
*   **Договір (Contract)**
    *   *Source:* Sales Manager <-> Client. [raw/Технический директор_input.md:L1]
*   **Замовлення у виробництво (Production Order)**
    *   *Source:* Sales Manager -> Production. [raw/Технический директор_input.md:L1]

## 4. Locations and Physical Resources
*   **GAP:** No specific physical locations, office setups, or manufacturing facilities are detailed, other than the general context of a "small manufacturing company" and "equipment setup". [raw/Технический директор_input.md:L1]
```
