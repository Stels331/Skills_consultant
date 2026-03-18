---
id: case_20260312_001__layer_3_functional_model
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
created_at: 2026-03-12T10:11:50.925109+00:00
updated_at: 2026-03-12T10:11:50.925109+00:00
---
```yaml
---
id: case_20260312_001__layer_3_functional_model
artifact_type: layer_model
layer: 3
title: "Layer 3: Functional Model"
workspace_id: case_20260312_001
status: draft
created_at: 2026-03-12T10:10:50.181490+00:00
updated_at: 2026-03-12T10:10:50.181490+00:00
---
```

# Layer 3: Functional Model

## 1. Key Business Functions & Processes

### 1.1 Sales Process (Процес продажів)
*   **F1.1 Client Acquisition & Request Intake:** Receiving the initial manufacturing request from the client.
    *   *Traceability:* `[raw/Технический директор_input.md:L1] "Менеджер із продажів знаходить клієнта та приймає від нього заявку на виготовлення продукції."`
*   **F1.2 Order Evaluation (Оцінювання замовлення):** Assessing the request to determine feasibility, work volume, price, and deadlines.
    *   *Traceability:* `[raw/Технический директор_input.md:L1] "Технічний директор має оцінити замовлення: виконуваність, обсяги, ціну та терміни..."`
*   **F1.3 Contract Negotiation:** Agreeing on terms with the client based on the evaluation.
    *   *Traceability:* `[raw/Технический директор_input.md:L1] "На підставі цієї оцінки менеджер погоджує з клієнтом договір..."`
*   **F1.4 Production Launch:** Transferring the finalized order into the manufacturing phase.
    *   *Traceability:* `[raw/Технический директор_input.md:L1] "...і запускає замовлення у виробництво."`

### 1.2 Production & Operations Management (Управління виробництвом)
*   **F2.1 Core Production Management:** Overseeing manufacturing processes to meet volume and quality KPIs.
*   **F2.2 Supply Management:** Handling procurement and supply chain tasks.
*   **F2.3 Equipment Maintenance:** Setting up and configuring manufacturing equipment.
*   **F2.4 Urgent Issue Resolution:** Handling day-to-day operational emergencies.
    *   *Traceability for F2.1 - F2.4:* `[raw/Технический директор_input.md:L1] "...завантажений виробництвом, терміновими задачами, постачанням, налаштуванням обладнання та іншими операційними питаннями."`

## 2. Information Flows & Data Objects

*   **D1. Client Request (Заявка):** Flows from Client -> Sales Manager -> Technical Director.
*   **D2. Evaluation Data (Оцінка):** Contains feasibility, volume, price, and deadline data. Flows from Technical Director -> Sales Manager.
    *   *Bottleneck:* This flow is currently delayed by 7–10 days or dropped entirely. `[raw/Технический директор_input.md:L1] "відповіді клієнту надаються із затримкою 7–10 днів, а частину заявок технічний директор може взагалі не опрацювати."`
*   **D3. Contract/Offer (Договір):** Flows from Sales Manager -> Client.

## 3. Identified Gaps (GAP)

*   **GAP 3.1 (Information Systems):** The case does not specify any IT systems, software, or tools (e.g., CRM, ERP, spreadsheets, email) used to capture requests, route them between Sales and the Technical Director, or track evaluation statuses.
*   **GAP 3.2 (Evaluation Methodology):** There is no description of the functional steps, algorithms, or reference data the Technical Director uses to calculate price, volume, and deadlines (e.g., standard costings, capacity planning tools).
*   **GAP 3.3 (Rejection Handling):** It is unclear if there is a formalized functional step for capturing the reasons why clients reject the evaluated offers (price vs. time vs. other conditions) to feed back into the evaluation model.
