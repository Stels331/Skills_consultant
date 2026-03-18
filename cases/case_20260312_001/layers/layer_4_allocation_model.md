---
id: case_20260312_001__layer_4_allocation_model
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
created_at: 2026-03-12T10:12:05.788830+00:00
updated_at: 2026-03-12T10:12:05.788830+00:00
---
```markdown
---
id: layer_4_allocation_model
artifact_type: layer_model
layer: 4
title: "Layer 4: Allocation Model"
description: "Mapping of functions to roles, systems, and physical resources."
---

# Layer 4: Allocation Model

## 1. Roles and Actors Allocation
*   **Менеджер із продажів (Sales Manager)**
    *   *Allocated Functions:* Finding clients, receiving requests, transferring requests to the Technical Director, negotiating contracts with clients based on evaluations, and launching orders into production.
    *   *Source:* `["Менеджер із продажів знаходить клієнта та приймає від нього заявку...", "Далі менеджер передає заявку технічному директору.", "На підставі цієї оцінки менеджер погоджує з клієнтом договір і запускає замовлення у виробництво."]`
*   **Технічний директор (Technical Director)**
    *   *Allocated Functions:* Evaluating orders (feasibility, volumes, price, deadlines), returning evaluations to the Sales Manager, managing production, handling urgent tasks, supply, and equipment setup.
    *   *Source:* `["Технічний директор має оцінити замовлення: виконуваність, обсяги, ціну та терміни...", "він завантажений виробництвом, терміновими задачами, постачанням, налаштуванням обладнання..."]`
*   **Клієнт (Client)**
    *   *Allocated Functions:* Submitting requests, reviewing terms (price, deadlines), and approving/canceling orders.
    *   *Source:* `["клієнту можуть не підійти ціна, терміни або інші умови, тому замовлення скасовується."]`

## 2. IT Systems and Tools Allocation
*   **GAP:** The case does not specify any IT systems, CRM, ERP, or communication tools used by the Sales Manager or Technical Director to register requests, transfer data, or track the status of evaluations.

## 3. Physical and Spatial Allocation
*   **GAP:** No information is provided regarding the physical locations of the sales department versus the production facilities, or how physical proximity might affect the communication between the Sales Manager and the Technical Director.

## 4. Organizational Rules and Incentive Allocation
*   **Technical Director KPIs:** Performance incentives are strictly allocated to production volume and product quality, creating a misalignment with the requested sales evaluation tasks.
    *   *Source:* `["у техничного директора в KPI показники повязані з обсягу виробництва та якості продукції."]`
*   **Regulatory Allocation:** The responsibility for order evaluation is formally allocated to the Technical Director via internal standards/regulations and job descriptions, despite the conflicting KPI structure.
    *   *Source:* `["існує внутрішній стандарт/регламент, а також відповідні положення в посадовій інструкції, де зазначено, що технічний директор бере участь у підготовці контракту та в оцінці замовлення."]`
```
