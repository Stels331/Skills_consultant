---
id: case_20260317_001__layer_2_requirements
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
created_at: 2026-03-17T18:45:48.574949+00:00
updated_at: 2026-03-17T18:45:48.574949+00:00
---
```markdown
---
id: layer_2_requirements
artifact_type: layer_model
layer: 2
workspace_id: case_20260317_001
status: draft
---
# Layer 2: Requirements Model

## 1. Stakeholders & Needs
*   **Sales Manager**: Needs fast and reliable order evaluations (feasibility, volume, price, deadlines) to negotiate contracts and close deals with clients. [Source: `raw/Технический директор_input.md` - "Менеджер із продажів знаходить клієнта..."]
*   **Technical Director (TD)**: Needs to minimize time spent on non-converting pre-sales estimates to focus on core operational duties (production, urgent tasks, supply, equipment setup) which directly impact their KPIs. [Source: `raw/Технический директор_input.md` - "Технічний директор часто висловлює невдоволення..."]
*   **Clients**: Need prompt responses and acceptable terms for their manufacturing requests. [Source: `raw/Технический директор_input.md` - "Через затримки клієнти незадоволені..."]
*   **Company Management**: Needs to prevent client churn to competitors, protect company reputation, and improve the conversion rate of estimates to actual orders. [Source: `raw/Технический директор_input.md` - "частина з них переходить до конкурентів, а репутація компанії погіршується"]

## 2. Functional Requirements (FR)
*   **FR1 (Order Estimation)**: The system/process must evaluate incoming manufacturing requests to determine feasibility, work volume, price, and deadlines. [Source: `raw/Технический директор_input.md` - "оцінити замовлення: виконуваність, обсяги, ціну та терміни"]
*   **FR2 (Request Routing)**: The system/process must support the transfer of request data from Sales to the estimating entity. [Source: `raw/Технический директор_input.md` - "менеджер передає заявку технічному директору"]
*   **FR3 (Estimate Delivery)**: The system/process must return the completed evaluation back to the Sales Manager for client negotiation. [Source: `raw/Технический директор_input.md` - "повернути оцінку менеджеру із продажів"]

## 3. Non-Functional Requirements (NFR)
*   **NFR1 (Performance/Speed)**: The estimation process must be completed significantly faster than the current 7–10 day delay.
    *   *GAP*: The exact target SLA (Service Level Agreement) for estimation turnaround time is not defined.
*   **NFR2 (Reliability/Completeness)**: 100% of submitted requests must be processed and evaluated (resolving the issue where requests are currently ignored). [Source: `raw/Технический директор_input.md` - "частину заявок технічний директор може взагалі не опрацювати"]

## 4. Business Constraints
*   **C1 (KPI Misalignment)**: The Technical Director's KPIs are strictly tied to production volume and product quality, creating a disincentive to prioritize pre-sales estimation. [Source: `raw/Технический директор_input.md` - "у техничного директора в KPI показники повязані з обсягу виробництва та якості"]
*   **C2 (Regulatory/Role Constraint)**: Current internal standards, regulations, and job descriptions explicitly mandate that the Technical Director must participate in contract preparation and order estimation. [Source: `raw/Технический директор_input.md` - "існує внутрішній стандарт/регламент... зазначено, що технічний директор бере участь"]

## 5. Explicit Gaps
*   **GAP 1**: What is the acceptable target turnaround time (SLA) for providing an estimate to the client (e.g., 24 hours, 48 hours)?
*   **GAP 2**: Can the estimation process be standardized, templated, or automated, or does every request require unique engineering judgment from the Technical Director?
*   **GAP 3**: Is there organizational flexibility to amend the Technical Director's job description (Constraint C2) or reassign the estimation task to a dedicated role (e.g., Presales Engineer, Estimator)?
*   **GAP 4**: What is the current vs. target conversion rate of estimates to actual orders?
```
